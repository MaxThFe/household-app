from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.shopping import (
    MarketInfo,
    SectionInfo,
    SectionOrderUpdate,
    ShoppingItemCreate,
    ShoppingItemUpdate,
    ShoppingItemResponse,
    ShoppingListResponse,
)
from app.services import sections as sections_service

router = APIRouter(prefix="/shopping", tags=["shopping"])


@router.get("", response_model=ShoppingListResponse)
async def get_shopping_list(db=Depends(get_db)):
    async with db.execute(
        """
        SELECT
            MIN(si.id) as id,
            si.name,
            SUM(si.quantity) as quantity,
            si.unit,
            si.store,
            MIN(si.source_recipe_id) as source_recipe_id,
            MIN(si.source_meal_id) as source_meal_id,
            MAX(si.is_manual) as is_manual,
            MIN(si.added_at) as added_at,
            REPLACE(GROUP_CONCAT(DISTINCT r.name), ',', ' + ') as source_names
        FROM shopping_items si
        LEFT JOIN recipes r ON si.source_recipe_id = r.id
        GROUP BY si.name, si.unit, si.store
        ORDER BY si.store, si.name
        """
    ) as cursor:
        rows = await cursor.fetchall()

    categories: dict[str, list[ShoppingItemResponse]] = {}
    for row in rows:
        item = ShoppingItemResponse.model_validate(dict(row))
        item.section = sections_service.classify(item.name)
        cat = item.store if item.store else "supermarket"
        categories.setdefault(cat, []).append(item)

    # Ensure default categories always appear (in order)
    ordered: dict[str, list[ShoppingItemResponse]] = {}
    for default_cat in ("supermarket", "household"):
        ordered[default_cat] = categories.pop(default_cat, [])
    # Append any custom categories
    for cat in sorted(categories):
        ordered[cat] = categories[cat]

    return ShoppingListResponse(
        categories=ordered,
        sections=[
            SectionInfo(slug=slug, label=label)
            for slug, label in sections_service.SECTIONS
        ],
        markets=[
            MarketInfo(slug=slug, label=label) for slug, label in sections_service.MARKETS
        ],
        section_orders=await sections_service.load_orders(db),
    )


@router.post("", response_model=ShoppingItemResponse, status_code=201)
async def add_shopping_item(
    body: ShoppingItemCreate, db=Depends(get_db), _=Depends(require_auth)
):
    cursor = await db.execute(
        "INSERT INTO shopping_items (name, quantity, unit, store, is_manual) VALUES (?, ?, ?, ?, 1)",
        (body.name, body.quantity, body.unit, body.store),
    )
    item_id = cursor.lastrowid
    await db.commit()
    async with db.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)) as cur:
        item = await cur.fetchone()

    response = ShoppingItemResponse.model_validate(dict(item))
    response.section = sections_service.classify(response.name)
    return response


# IMPORTANT: literal routes ("sections/order", "checked") must be registered
# BEFORE the "/{item_id}" routes to avoid routing conflicts
@router.put("/sections/order", status_code=204)
async def set_section_order(
    body: SectionOrderUpdate, db=Depends(get_db), _=Depends(require_auth)
):
    if body.market not in sections_service.MARKET_SLUGS:
        raise HTTPException(status_code=400, detail="Unknown market")

    order = [s for s in body.order if s in sections_service.SECTION_SLUGS]
    await db.execute(
        "DELETE FROM shopping_section_order WHERE market = ?", (body.market,)
    )
    await db.executemany(
        "INSERT INTO shopping_section_order (market, section, position) VALUES (?, ?, ?)",
        [(body.market, section, i) for i, section in enumerate(order)],
    )
    await db.commit()


@router.patch("/{item_id}", response_model=ShoppingItemResponse)
async def update_shopping_item(
    item_id: int, body: ShoppingItemUpdate, db=Depends(get_db), _=Depends(require_auth)
):
    async with db.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")

    updates = body.model_dump(exclude_unset=True)
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [item_id]
        await db.execute(f"UPDATE shopping_items SET {set_clause} WHERE id = ?", values)
        await db.commit()

    async with db.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)) as cursor:
        updated = await cursor.fetchone()

    response = ShoppingItemResponse.model_validate(dict(updated))
    response.section = sections_service.classify(response.name)
    return response


@router.delete("/checked", status_code=204)
async def delete_checked_items(
    ids: list[int] = Query(default=[]), db=Depends(get_db), _=Depends(require_auth)
):
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    await db.execute(f"DELETE FROM shopping_items WHERE id IN ({placeholders})", ids)
    await db.commit()


@router.delete("/{item_id}", status_code=204)
async def delete_shopping_item(item_id: int, db=Depends(get_db), _=Depends(require_auth)):
    async with db.execute(
        "SELECT name, unit, store FROM shopping_items WHERE id = ?", (item_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.execute(
        "DELETE FROM shopping_items WHERE name = ? AND unit = ? AND store = ?",
        (row["name"], row["unit"], row["store"]),
    )
    await db.commit()
