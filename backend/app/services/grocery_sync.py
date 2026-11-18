"""Fetches new receipts from every connected grocery account and stores them.

Runs every grocery_sync_interval_hours and on demand. Each account is synced
on its own, so one store breaking (these are all unofficial APIs) leaves the
others running; the outcome per account lands in grocery_sync_state for the
app to show. Only receipts not stored yet are fetched in full.
"""

import asyncio
import json
import logging

import aiosqlite

from app.core.config import settings
from app.services import grocery_ah, grocery_lidl, grocery_picnic
from app.services.grocery_common import NotConnected, Receipt, local_iso

logger = logging.getLogger(__name__)

SOURCES = {
    grocery_picnic.STORE: grocery_picnic,
    grocery_ah.STORE: grocery_ah,
    grocery_lidl.STORE: grocery_lidl,
}

# One sync at a time: AH and Lidl rotate refresh tokens, and two syncs racing
# to renew the same one would log the account out.
_lock = asyncio.Lock()


async def store_receipt(db: aiosqlite.Connection, receipt: Receipt) -> bool:
    """Insert one receipt with its items; False if it was already stored."""
    cursor = await db.execute(
        """INSERT INTO purchases
               (store, external_id, person, purchased_at, total_cents, store_name, raw)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (store, external_id) DO NOTHING""",
        (
            receipt.store, receipt.external_id, receipt.person,
            local_iso(receipt.purchased_at), receipt.total_cents, receipt.store_name,
            json.dumps(receipt.raw, ensure_ascii=False),
        ),
    )
    if cursor.rowcount == 0:
        return False
    await db.executemany(
        """INSERT INTO purchase_items
               (purchase_id, line_no, name, product_id, quantity, unit, unit_quantity,
                unit_price_cents, amount_cents, discount_cents)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                cursor.lastrowid, line_no, item.name, item.product_id, item.quantity,
                item.unit, item.unit_quantity, item.unit_price_cents, item.amount_cents,
                item.discount_cents,
            )
            for line_no, item in enumerate(receipt.items, start=1)
        ],
    )
    return True


async def _known_ids(db: aiosqlite.Connection, store: str) -> set[str]:
    async with db.execute("SELECT external_id FROM purchases WHERE store = ?", (store,)) as cursor:
        return {row[0] for row in await cursor.fetchall()}


async def _record(db: aiosqlite.Connection, source: str, error: str | None) -> None:
    await db.execute(
        """INSERT INTO grocery_sync_state (source, last_attempt, last_success, error)
           VALUES (?, datetime('now'), CASE WHEN ? IS NULL THEN datetime('now') END, ?)
           ON CONFLICT (source) DO UPDATE SET
               last_attempt = excluded.last_attempt,
               last_success = COALESCE(excluded.last_success, grocery_sync_state.last_success),
               error = excluded.error""",
        (source, error, error),
    )


async def sync_account(db: aiosqlite.Connection, store: str, account: str) -> int:
    source = f"{store}:{account}"
    module = SOURCES[store]
    try:
        receipts = await module.fetch(account, await _known_ids(db, store))
        added = 0
        for receipt in receipts:
            added += await store_receipt(db, receipt)
        await _record(db, source, None)
        await db.commit()
        if added:
            logger.info("Grocery sync %s: %d new", source, added)
        return added
    except NotConnected as exc:
        error = str(exc)
    except Exception as exc:
        logger.exception("Grocery sync %s failed", source)
        error = f"{type(exc).__name__}: {exc}"
    await db.rollback()
    await _record(db, source, error[:500])
    await db.commit()
    return 0


async def sync_all(db: aiosqlite.Connection) -> int:
    async with _lock:
        added = 0
        for store, module in SOURCES.items():
            for account in module.accounts():
                added += await sync_account(db, store, account)
        return added


async def run_grocery_sync_loop() -> None:
    while True:
        try:
            async with aiosqlite.connect(settings.database_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await sync_all(db)
        except Exception:
            logger.exception("Grocery sync failed")
        await asyncio.sleep(settings.grocery_sync_interval_hours * 3600)
