"""Tests for the grocery receipts: parsing each store's shape, and storing."""

import asyncio
from datetime import datetime

import aiosqlite

from app.core.database import SCHEMA_SQL
from app.services import grocery_ah, grocery_lidl, grocery_picnic, grocery_sync
from app.services.grocery_common import euros_to_cents, extract_code, local_iso, parse_datetime, parse_quantity


# --- money and dates -------------------------------------------------------------

def test_amounts_in_every_format_the_stores_use():
    assert euros_to_cents(2.19) == 219
    assert euros_to_cents("2,19") == 219
    assert euros_to_cents("1.234,56") == 123456
    assert euros_to_cents("-0,21") == -21
    assert euros_to_cents("1,10-") == -110
    assert euros_to_cents(None) is None


def test_a_dotted_weight_is_kilos_not_thousands():
    assert parse_quantity("0.792") == 0.792
    assert parse_quantity("0,792") == 0.792
    assert parse_quantity("1.000") == 1.0


def test_times_are_stored_in_local_time():
    assert local_iso(parse_datetime("2026-03-14T14:22:00Z")) == "2026-03-14T15:22:00"
    assert local_iso(parse_datetime("2026-03-14T15:22:00")) == "2026-03-14T15:22:00"


def test_code_from_the_app_link_or_bare():
    assert extract_code("appie://login-exit?code=abc-123&state=x") == "abc-123"
    assert extract_code("com.lidlplus.app://callback?code=F00D&scope=openid") == "F00D"
    assert extract_code("  F00D ") == "F00D"


# --- Picnic ----------------------------------------------------------------------

def _line(article_id, name, price, quantity, promo=None, promo_on_line=False):
    decorators = [{"type": "QUANTITY", "quantity": quantity}]
    promos = [{"type": "PRICE", "display_price": promo}] if promo is not None else []
    return {"price": price, "display_price": price, "decorators": promos if promo_on_line else [], "items": [
        {"id": article_id, "name": name, "unit_quantity": "1 liter",
         "decorators": decorators + ([] if promo_on_line else promos)},
    ]}


def test_picnic_delivery_becomes_one_receipt_per_completed_order():
    delivery = {
        "delivery_id": "d1",
        "slot": {"window_start": "2026-04-18T09:20:00.000+02:00"},
        "delivery_time": {"start": "2026-04-18T09:58:05.103+02:00"},
        "orders": [
            {"id": "o1", "status": "COMPLETED", "total_price": 5833, "checkout_total_price": 5868,
             "items": [_line("s1", "Melk", 178, 2), _line("s2", "Wasmiddel", 2598, 2, promo=1299),
                       _line("s3", "Bananen", 119, 1, promo=107, promo_on_line=True)]},
            {"id": "o2", "status": "CANCELLED", "total_price": 100, "items": []},
        ],
    }
    [receipt] = grocery_picnic.receipts_from_delivery("Max", delivery)
    assert receipt.external_id == "o1"
    assert receipt.person == "Max"
    assert receipt.total_cents == 5868
    assert local_iso(receipt.purchased_at) == "2026-04-18T09:58:05"
    milk, soap, bananas = receipt.items
    assert (milk.product_id, milk.quantity, milk.amount_cents, milk.discount_cents) == ("s1", 2, 178, 0)
    assert (soap.amount_cents, soap.discount_cents) == (2598, 1299)
    assert (bananas.amount_cents, bananas.discount_cents) == (119, 12)


# --- AH --------------------------------------------------------------------------

def test_ah_receipt():
    summary = {"id": "r1", "dateTime": "2026-04-02T17:31:00Z", "totalAmount": {"amount": 23.47}}
    detail = {"id": "r1", "products": [
        {"id": 41234, "quantity": 2, "name": "AH Halfvolle melk", "price": {"amount": 1.19}, "amount": {"amount": 2.38}},
        {"id": 5, "quantity": 1, "name": "Statiegeld", "price": None, "amount": {"amount": 0.15}},
    ], "discounts": [{"name": "Bonus", "amount": {"amount": -0.50}}]}
    receipt = grocery_ah.parse_receipt("Max", summary, detail)
    assert (receipt.total_cents, receipt.person) == (2347, "Max")
    assert local_iso(receipt.purchased_at) == "2026-04-02T19:31:00"
    milk, deposit = receipt.items
    assert (milk.product_id, milk.quantity, milk.unit_price_cents, milk.amount_cents) == ("41234", 2, 119, 238)
    assert deposit.unit_price_cents is None


# --- Lidl ------------------------------------------------------------------------

def _span(n, text, cls="", **data):
    attrs = "".join(f' data-{k.replace("_", "-")}="{v}"' for k, v in data.items())
    return f'<span id="purchase_list_line_{n}" class="{cls}"{attrs}>{text}</span>'


DUTCH_HTML = "<pre>" + "\n".join([
    _span(1, "OMSCHRIJVING                 EUR", "currency"),
    _span(2, "Siroop                3,58 B", "article", art_id="6607485", art_quantity="2",
          unit_price="1,79", art_description="Siroop"),
    _span(3, "  Lidl Plus korting  -0,50", "discount"),
    _span(4, "Bananen               1,10 B", "article", art_id="0080000", art_quantity="0,792",
          unit_price="1,39", art_description="Bananen"),
    _span(5, "  0,792 kg x 1,39 EUR/kg", "article", art_id="0080000", art_quantity="0,792",
          unit_price="1,39", art_description="Bananen"),
    _span(6, "Emballage            -0,25", "deposit"),
]) + "</pre>"


def test_lidl_dutch_html_receipt():
    ticket = {"id": "t1", "date": "2026-05-09T11:02:13", "totalAmount": "3,93",
              "store": {"name": "Delft Papsouwselaan"}, "htmlPrintedReceipt": DUTCH_HTML}
    receipt = grocery_lidl.parse_ticket("Max", ticket)
    assert (receipt.total_cents, receipt.store_name) == (393, "Delft Papsouwselaan")
    syrup, bananas, deposit = receipt.items
    assert (syrup.quantity, syrup.unit_price_cents, syrup.amount_cents, syrup.discount_cents) == (2, 179, 358, 50)
    assert (bananas.quantity, bananas.unit, bananas.amount_cents, bananas.product_id) == (0.792, "kg", 110, "0080000")
    assert (deposit.name, deposit.amount_cents) == ("Emballage", -25)


def test_lidl_items_line_receipt():
    ticket = {"id": "t2", "date": "2026-05-09T11:02:13+02:00", "totalAmount": 2.19, "itemsLine": [
        {"name": "Melk", "quantity": "1", "currentUnitPrice": "2,19", "originalAmount": "2,19",
         "codeInput": "123", "isWeight": False, "discounts": []},
    ]}
    [milk] = grocery_lidl.parse_ticket("Max", ticket).items
    assert (milk.name, milk.amount_cents, milk.product_id) == ("Melk", 219, "123")


# --- storing ---------------------------------------------------------------------

def test_storing_a_receipt_twice_keeps_one():
    async def run():
        async with aiosqlite.connect(":memory:") as db:
            await db.executescript(SCHEMA_SQL)
            summary = {"id": "r1", "dateTime": "2026-04-02T17:31:00Z", "totalAmount": {"amount": 2.38}}
            detail = {"products": [{"id": 1, "quantity": 2, "name": "Melk", "price": {"amount": 1.19},
                                    "amount": {"amount": 2.38}}]}
            receipt = grocery_ah.parse_receipt("Max", summary, detail)
            assert await grocery_sync.store_receipt(db, receipt) is True
            assert await grocery_sync.store_receipt(db, receipt) is False
            async with db.execute("SELECT COUNT(*) FROM purchases") as c:
                assert (await c.fetchone())[0] == 1
            async with db.execute("SELECT COUNT(*) FROM purchase_items") as c:
                assert (await c.fetchone())[0] == 1

    asyncio.run(run())


def test_a_failing_account_records_its_error_and_others_still_run(monkeypatch):
    async def broken(account, known):
        raise RuntimeError("503 from AH")

    async def fine(account, known):
        return [grocery_ah.parse_receipt(account, {"id": "x", "dateTime": "2026-04-02T17:31:00Z",
                                                   "totalAmount": {"amount": 1}}, {"products": []})]

    async def run():
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await db.executescript(SCHEMA_SQL)
            monkeypatch.setattr(grocery_ah, "fetch", broken)
            assert await grocery_sync.sync_account(db, "ah", "Max") == 0
            monkeypatch.setattr(grocery_lidl, "fetch", fine)
            assert await grocery_sync.sync_account(db, "lidl", "Max") == 1
            async with db.execute("SELECT source, last_success, error FROM grocery_sync_state ORDER BY source") as c:
                ah, lidl = await c.fetchall()
            assert ah["error"] == "RuntimeError: 503 from AH" and ah["last_success"] is None
            assert lidl["error"] is None and lidl["last_success"] is not None

    asyncio.run(run())
