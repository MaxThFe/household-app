"""Tests for the Picnic order: pack counts, the LLM mapping loop, the cache."""

import asyncio
import json
from types import SimpleNamespace

import aiosqlite

from app.core.database import SCHEMA_SQL
from app.services import picnic
from app.services.picnic_mapper import Chosen, Question, map_item
from app.services.picnic_packs import pack_count

MINCE_500 = {"product_id": "s1", "name": "Rundergehakt", "unit_quantity": "500 gram", "price": 549, "image_id": "i1"}
MINCE_1KG = {"product_id": "s2", "name": "Rundergehakt", "unit_quantity": "1 kilo", "price": 999, "image_id": "i2"}


# --- pack counts ------------------------------------------------------------------

def test_quantity_counts_packs_but_a_measuring_unit_does_not():
    assert pack_count(None, "") == 1
    assert pack_count(2, "") == 2
    assert pack_count(500, "g") == 1


# --- the mapping loop ---------------------------------------------------------------

def _call(name, **arguments):
    return SimpleNamespace(type="function_call", name=name, call_id=f"c-{name}", arguments=json.dumps(arguments))


class FakeLLM:
    """Plays back one scripted list of output items per turn."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []
        self.responses = self

    async def create(self, **kwargs):
        self.requests.append({**kwargs, "input": list(kwargs["input"])})
        output = self.turns.pop(0)
        text = " ".join(o.text for o in output if o.type == "message")
        return SimpleNamespace(output=output, output_text=text)


async def fake_search(query):
    return [MINCE_500, MINCE_1KG]


def run(coro):
    return asyncio.run(coro)


def test_a_clear_item_ends_on_the_chosen_product():
    llm = FakeLLM([[_call("search_picnic", query="rundergehakt")], [_call("choose_product", product_id="s2")]])
    outcome = run(map_item(llm, "m", fake_search, "minced meat"))
    assert outcome == Chosen(MINCE_1KG)
    # The search results went back to the model as the tool's output.
    sent = llm.requests[1]["input"][-1]
    assert sent["type"] == "function_call_output" and "s1" in sent["output"]


def test_an_unclear_item_becomes_a_question_with_the_offered_products():
    llm = FakeLLM([
        [_call("search_picnic", query="gehakt")],
        [_call("ask_user", question="500 g or 1 kg?", candidate_product_ids=["s1", "s2", "made-up"])],
    ])
    outcome = run(map_item(llm, "m", fake_search, "minced meat"))
    assert outcome == Question("500 g or 1 kg?", [MINCE_500, MINCE_1KG])


# --- the cache ----------------------------------------------------------------------

async def _db():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA_SQL)
    await db.execute("INSERT INTO recipes (id, name) VALUES (1, 'Lasagne'), (2, 'Chili')")
    await db.executemany(
        "INSERT INTO shopping_items (name, quantity, unit, store, source_recipe_id) VALUES (?, ?, ?, ?, ?)",
        [
            ("Minced meat", 2, "", "supermarket", 1),
            ("minced meat", None, "", "supermarket", 2),
            ("Cream", None, "", "supermarket", 1),
            ("Plaster", None, "", "pharmacy", None),
        ],
    )
    return db


def test_mapped_items_are_not_sent_to_the_llm_again():
    async def scenario():
        db = await _db()
        pending = {item["key"] for item in await picnic.pending_items(db)}
        assert pending == {"minced meat", "cream"}  # the pharmacy is not Picnic's

        await picnic.save_mapping(db, "minced meat", 0, MINCE_500, "llm")
        await db.execute(
            "INSERT INTO picnic_questions (item_key, question) VALUES ('cream', 'Which cream?')"
        )
        assert await picnic.pending_items(db) == []

    run(scenario())


def test_a_recipe_override_wins_and_packs_add_up_per_product():
    async def scenario():
        db = await _db()
        await picnic.save_mapping(db, "minced meat", 0, MINCE_500, "llm")
        await picnic.save_mapping(db, "minced meat", 2, MINCE_1KG, "user")
        await picnic.save_mapping(db, "cream", 0, None, "user")
        preview = await picnic.order_preview(db)
        counts = {line["product_id"]: line["count"] for line in preview["lines"]}
        assert counts == {"s1": 2, "s2": 1}
        assert preview["skipped"] == ["Cream"]
        assert preview["unmapped"] == []

    run(scenario())

