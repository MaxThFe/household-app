"""Fetches new receipts from every connected grocery account and stores them.

Runs every grocery_sync_interval_hours. Each account is synced on its own, so
one store breaking (these are all unofficial APIs) leaves the others running;
a failure is logged, and an expired login says to run grocery_setup.py. Only
receipts not stored yet are fetched in full.
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

# (store, account) pairs whose last sync failed, for the page's status pill.
# Kept in memory: the sync runs at startup, so it is known again within
# seconds of a restart.
failing: set[tuple[str, str]] = set()


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
    """Receipts not to fetch: those stored, and those deleted in the app."""
    async with db.execute(
        """SELECT external_id FROM purchases WHERE store = ?
           UNION SELECT external_id FROM deleted_purchases WHERE store = ?""",
        (store, store),
    ) as cursor:
        return {row[0] for row in await cursor.fetchall()}


async def delete_purchase(db: aiosqlite.Connection, purchase_id: int) -> bool:
    """Delete a receipt and its items, and keep the sync from fetching it again."""
    async with db.execute(
        "SELECT store, external_id FROM purchases WHERE id = ?", (purchase_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return False
    await db.execute(
        "INSERT OR IGNORE INTO deleted_purchases (store, external_id) VALUES (?, ?)",
        (row[0], row[1]),
    )
    await db.execute("DELETE FROM purchase_items WHERE purchase_id = ?", (purchase_id,))
    await db.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
    await db.commit()
    return True


async def sync_account(db: aiosqlite.Connection, store: str, account: str) -> int:
    """Fetch and store one account's new receipts; returns how many."""
    receipts = await SOURCES[store].fetch(account, await _known_ids(db, store))
    added = 0
    for receipt in receipts:
        added += await store_receipt(db, receipt)
    await db.commit()
    if added:
        logger.info("Grocery sync %s:%s: %d new", store, account, added)
    return added


async def sync_all(db: aiosqlite.Connection) -> int:
    async with _lock:
        added = 0
        for store, module in SOURCES.items():
            for account in module.accounts():
                try:
                    added += await sync_account(db, store, account)
                    failing.discard((store, account))
                    continue
                except NotConnected as exc:
                    logger.warning("Grocery sync %s:%s: %s", store, account, exc)
                except Exception:
                    logger.exception("Grocery sync %s:%s failed", store, account)
                await db.rollback()
                failing.add((store, account))
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
