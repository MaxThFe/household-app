from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_auth
from app.core.config import settings
from app.core.database import get_db
from app.models.spending import (
    PurchaseDetail,
    PurchaseItem,
    PurchaseSummary,
    SpendingMonth,
    SpendingStatus,
    SyncSource,
)
from app.services import grocery_sync

router = APIRouter(prefix="/spending", tags=["spending"])

# person: a name, or 'shared' for purchases from a shared account.
PERSON_FILTER = "(? IS NULL OR (? = 'shared' AND p.person IS NULL) OR p.person = ?)"


@router.get("/months", response_model=list[SpendingMonth])
async def get_months(person: str | None = None, db=Depends(get_db)):
    async with db.execute(
        f"""SELECT substr(p.purchased_at, 1, 7) AS month, p.store,
                   SUM(p.total_cents) AS total_cents, COUNT(*) AS purchases
            FROM purchases p
            WHERE p.purchased_at >= ? AND {PERSON_FILTER}
            GROUP BY month, p.store ORDER BY month, p.store""",
        (settings.grocery_since, person, person, person),
    ) as cursor:
        return [SpendingMonth(**dict(r)) for r in await cursor.fetchall()]


_SUMMARY_SQL = """
    SELECT p.id, p.store, p.person, p.purchased_at, p.total_cents, p.store_name,
           (SELECT COUNT(*) FROM purchase_items i WHERE i.purchase_id = p.id) AS item_count
    FROM purchases p
"""


@router.get("/purchases", response_model=list[PurchaseSummary])
async def list_purchases(
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    person: str | None = None,
    db=Depends(get_db),
):
    async with db.execute(
        f"""{_SUMMARY_SQL}
            WHERE substr(p.purchased_at, 1, 7) = ? AND p.purchased_at >= ? AND {PERSON_FILTER}
            ORDER BY p.purchased_at DESC""",
        (month, settings.grocery_since, person, person, person),
    ) as cursor:
        return [PurchaseSummary(**dict(r)) for r in await cursor.fetchall()]


@router.get("/purchases/{purchase_id}", response_model=PurchaseDetail)
async def get_purchase(purchase_id: int, db=Depends(get_db)):
    async with db.execute(f"{_SUMMARY_SQL} WHERE p.id = ?", (purchase_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase not found")
    async with db.execute(
        """SELECT line_no, name, product_id, quantity, unit, unit_quantity,
                  unit_price_cents, amount_cents, discount_cents
           FROM purchase_items WHERE purchase_id = ? ORDER BY line_no""",
        (purchase_id,),
    ) as cursor:
        items = [PurchaseItem(**dict(r)) for r in await cursor.fetchall()]
    return PurchaseDetail(**dict(row), items=items)


@router.get("/status", response_model=SpendingStatus)
async def get_status(db=Depends(get_db)):
    async with db.execute("SELECT * FROM grocery_sync_state") as cursor:
        state = {r["source"]: dict(r) for r in await cursor.fetchall()}
    sources = []
    for store, module in grocery_sync.SOURCES.items():
        for account in module.accounts():
            source = f"{store}:{account}"
            row = state.get(source, {})
            sources.append(SyncSource(
                source=source, store=store, account=account,
                last_attempt=row.get("last_attempt"), last_success=row.get("last_success"),
                error=row.get("error"),
            ))
    return SpendingStatus(since=settings.grocery_since, sources=sources)


@router.post("/sync", response_model=SpendingStatus)
async def sync_now(db=Depends(get_db), _=Depends(require_auth)):
    await grocery_sync.sync_all(db)
    return await get_status(db)
