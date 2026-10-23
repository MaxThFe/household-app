"""Shopping list -> Picnic cart: the cached mappings, the questions, the order.

A mapping belongs to an item name and holds for every recipe, unless the
household answered "only for this recipe", which stores it under that
recipe's id instead. Items without a mapping are run through the LLM in a
background job; what it can't settle becomes a question in the app, and
answered questions are kept so a re-run knows what was said.
"""

import asyncio
import json
import logging

import aiosqlite

from app.core.config import settings
from app.services import picnic_client
from app.services.picnic_mapper import Chosen, NotOnPicnic, map_item
from app.services.picnic_packs import pack_count

logger = logging.getLogger(__name__)

# Custom stores (the pharmacy, the market) are not Picnic's business.
PICNIC_STORES = ("", "supermarket", "household")
CONCURRENCY = 4

_llm = None
_job: dict = {"running": False, "total": 0, "done": 0, "error": None}
_job_task: asyncio.Task | None = None


def item_key(name: str) -> str:
    return " ".join(name.lower().split())


def llm_configured() -> bool:
    return bool(settings.openai_api_key)


def _client():
    global _llm
    if _llm is None:
        from openai import AsyncOpenAI

        _llm = AsyncOpenAI(api_key=settings.openai_api_key)
    return _llm


async def _shopping_rows(db) -> list[aiosqlite.Row]:
    placeholders = ",".join("?" * len(PICNIC_STORES))
    async with db.execute(
        f"""
        SELECT si.id, si.name, si.quantity, si.unit, si.source_recipe_id,
               r.name AS recipe_name
        FROM shopping_items si
        LEFT JOIN recipes r ON si.source_recipe_id = r.id
        WHERE si.store IN ({placeholders})
        ORDER BY si.name
        """,
        PICNIC_STORES,
    ) as cursor:
        return await cursor.fetchall()


async def _mappings(db) -> dict[tuple[str, int], dict]:
    async with db.execute("SELECT * FROM picnic_mappings") as cursor:
        return {(r["item_key"], r["recipe_id"]): dict(r) for r in await cursor.fetchall()}


def lookup(mappings: dict, key: str, recipe_id: int | None) -> dict | None:
    """The recipe's own mapping if it has one, else the item's."""
    if recipe_id and (key, recipe_id) in mappings:
        return mappings[(key, recipe_id)]
    return mappings.get((key, 0))


async def _open_question_keys(db) -> set[str]:
    async with db.execute(
        "SELECT DISTINCT item_key FROM picnic_questions WHERE status = 'open'"
    ) as cursor:
        return {r["item_key"] for r in await cursor.fetchall()}


async def pending_items(db) -> list[dict]:
    """Items on the list with no mapping and no question waiting for an answer."""
    mappings = await _mappings(db)
    waiting = await _open_question_keys(db)
    pending: dict[str, dict] = {}
    for row in await _shopping_rows(db):
        key = item_key(row["name"])
        if key in waiting or lookup(mappings, key, row["source_recipe_id"]):
            continue
        entry = pending.setdefault(key, {"key": key, "name": row["name"], "recipes": {}, "manual": False})
        if row["source_recipe_id"]:
            entry["recipes"][row["source_recipe_id"]] = row["recipe_name"] or ""
        else:
            entry["manual"] = True
    return list(pending.values())


async def save_mapping(
    db, key: str, recipe_id: int, product: dict | None, source: str
) -> None:
    """Store a product for the item, or with product None, 'not from Picnic'."""
    product = product or {}
    await db.execute(
        """
        INSERT INTO picnic_mappings
            (item_key, recipe_id, status, product_id, product_name, unit_quantity,
             price, image_id, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT (item_key, recipe_id) DO UPDATE SET
            status = excluded.status, product_id = excluded.product_id,
            product_name = excluded.product_name, unit_quantity = excluded.unit_quantity,
            price = excluded.price, image_id = excluded.image_id,
            source = excluded.source, updated_at = excluded.updated_at
        """,
        (
            key, recipe_id, "mapped" if product else "skip",
            product.get("product_id"), product.get("name"), product.get("unit_quantity", ""),
            product.get("price"), product.get("image_id"), source,
        ),
    )


async def _prior_qa(db, key: str) -> list[tuple[str, str]]:
    async with db.execute(
        """SELECT question, answer FROM picnic_questions
           WHERE item_key = ? AND status = 'answered' AND answer IS NOT NULL
           ORDER BY id""",
        (key,),
    ) as cursor:
        return [(r["question"], r["answer"]) for r in await cursor.fetchall()]


async def map_and_save(
    db,
    key: str,
    name: str,
    recipe_names: list[str],
    mapping_recipe_id: int = 0,
    question_recipe_id: int = 0,
    extra_qa: list[tuple[str, str]] = (),
) -> str:
    """Ask the LLM about one item and cache what it decides.

    The LLM's own choice holds for every recipe unless the household scoped
    the answer it is acting on (mapping_recipe_id). question_recipe_id is the
    recipe a question can later be scoped to. Returns mapped/skipped/asked.
    """
    prior = await _prior_qa(db, key) + list(extra_qa)
    outcome = await map_item(
        _client(), settings.openai_model, picnic_client.search, name, recipe_names, prior
    )
    if isinstance(outcome, Chosen):
        await save_mapping(db, key, mapping_recipe_id, outcome.product, "llm")
        result = "mapped"
    elif isinstance(outcome, NotOnPicnic):
        await save_mapping(db, key, mapping_recipe_id, None, "llm")
        result = "skipped"
    else:
        await db.execute(
            """INSERT INTO picnic_questions
                   (item_key, recipe_id, recipe_names, question, candidates)
               VALUES (?, ?, ?, ?, ?)""",
            (key, question_recipe_id or mapping_recipe_id, ", ".join(recipe_names),
             outcome.question, json.dumps(outcome.candidates, ensure_ascii=False)),
        )
        result = "asked"
    await db.commit()
    return result


# --- background mapping job ---------------------------------------------------

def job_status() -> dict:
    return dict(_job)


def start_mapping() -> dict:
    global _job_task
    if not _job["running"]:
        _job.update(running=True, total=0, done=0, error=None)
        _job_task = asyncio.create_task(_run_mapping())
    return job_status()


async def _run_mapping() -> None:
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            db.row_factory = aiosqlite.Row
            items = await pending_items(db)
            _job["total"] = len(items)
            semaphore = asyncio.Semaphore(CONCURRENCY)

            async def one(item: dict) -> None:
                async with semaphore:
                    # A question can only be scoped to a recipe when the item
                    # comes from exactly one recipe and nowhere else.
                    recipe_id = 0
                    if len(item["recipes"]) == 1 and not item["manual"]:
                        recipe_id = next(iter(item["recipes"]))
                    try:
                        await map_and_save(
                            db, item["key"], item["name"], list(item["recipes"].values()),
                            question_recipe_id=recipe_id,
                        )
                    except picnic_client.PicnicNotConnected:
                        raise
                    except Exception:
                        logger.exception("Picnic mapping failed for %r", item["name"])
                    _job["done"] += 1

            await asyncio.gather(*(one(item) for item in items))
    except picnic_client.PicnicNotConnected as exc:
        _job["error"] = str(exc)
    except Exception as exc:
        logger.exception("Picnic mapping job failed")
        _job["error"] = str(exc)
    finally:
        _job["running"] = False


# --- the order ------------------------------------------------------------------

async def order_preview(db) -> dict:
    mappings = await _mappings(db)
    lines: dict[str, dict] = {}
    unmapped: set[str] = set()
    skipped: set[str] = set()
    for row in await _shopping_rows(db):
        mapping = lookup(mappings, item_key(row["name"]), row["source_recipe_id"])
        if mapping is None:
            unmapped.add(row["name"])
            continue
        if mapping["status"] != "mapped":
            skipped.add(row["name"])
            continue
        line = lines.setdefault(mapping["product_id"], {
            "product_id": mapping["product_id"],
            "name": mapping["product_name"],
            "unit_quantity": mapping["unit_quantity"] or "",
            "price": mapping["price"],
            "image_url": picnic_client.image_url(mapping["image_id"]),
            "count": 0,
            "items": [],
        })
        line["count"] += pack_count(row["quantity"], row["unit"])
        if row["name"] not in line["items"]:
            line["items"].append(row["name"])
    return {
        "lines": sorted(lines.values(), key=lambda l: l["name"] or ""),
        "unmapped": sorted(unmapped),
        "skipped": sorted(skipped),
    }


async def place_in_cart(user: str, lines: list[tuple[str, int]]) -> list[dict]:
    """Add each product to this user's Picnic cart. Never checks out."""
    results = []
    for product_id, count in lines:
        try:
            await picnic_client.add_product(user, product_id, count)
            results.append({"product_id": product_id, "ok": True, "error": None})
        except picnic_client.PicnicNotConnected:
            raise
        except Exception as exc:
            logger.exception("Adding %s to the Picnic cart failed", product_id)
            results.append({"product_id": product_id, "ok": False, "error": str(exc)})
    return results

