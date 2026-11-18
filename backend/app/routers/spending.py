from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_auth

from app.core.config import settings
from app.core.database import get_db
from app.models.spending import (
    PurchaseDetail,
    PurchaseItem,
    PurchaseSummary,
    SpendingMonth,
    SpendingMonths,
    FailingAccount,
    SpendingStats,
)
from app.services import grocery_sync
from app.services.grocery_common import LOCAL_TZ

router = APIRouter(prefix="/spending", tags=["spending"])

PERSON_FILTER = "(? IS NULL OR p.person = ?)"


@router.get("/months", response_model=SpendingMonths)
async def get_months(person: str | None = None, db=Depends(get_db)):
    async with db.execute(
        f"""SELECT substr(p.purchased_at, 1, 7) AS month, p.store,
                   SUM(p.total_cents) AS total_cents, COUNT(*) AS purchases
            FROM purchases p
            WHERE p.purchased_at >= ? AND {PERSON_FILTER}
            GROUP BY month, p.store ORDER BY month, p.store""",
        (settings.grocery_since, person, person),
    ) as cursor:
        rows = [SpendingMonth(**dict(r)) for r in await cursor.fetchall()]
    return SpendingMonths(since=settings.grocery_since, months=rows)


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
        (month, settings.grocery_since, person, person),
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


@router.delete("/purchases/{purchase_id}", status_code=204)
async def delete_purchase(purchase_id: int, db=Depends(get_db), _=Depends(require_auth)):
    if not await grocery_sync.delete_purchase(db, purchase_id):
        raise HTTPException(status_code=404, detail="Purchase not found")


@router.get("/health", response_model=list[FailingAccount])
async def get_health():
    """Accounts whose last sync failed; empty when all is well."""
    return [FailingAccount(store=s, person=p) for s, p in sorted(grocery_sync.failing)]


@router.get("/stats", response_model=SpendingStats)
async def get_stats(db=Depends(get_db)):
    """Household averages, with the runs split per person."""
    # Complete months only: from grocery_since up to the first of this month.
    start = date.fromisoformat(settings.grocery_since)
    end = datetime.now(LOCAL_TZ).date().replace(day=1)
    months = (end.year - start.year) * 12 + end.month - start.month
    weeks = (end - start).days / 7
    if months <= 0:
        return SpendingStats(per_month_cents=None, per_week_cents=None, runs_per_week=None,
                             runs_per_week_by_person={}, per_run_cents=None)
    async with db.execute(
        """SELECT p.person, COUNT(*) AS runs, SUM(p.total_cents) AS cents
            FROM purchases p
            WHERE p.purchased_at >= ? AND p.purchased_at < ?
            GROUP BY p.person""",
        (start.isoformat(), end.isoformat()),
    ) as cursor:
        rows = await cursor.fetchall()
    runs = sum(r["runs"] for r in rows)
    cents = sum(r["cents"] for r in rows)
    return SpendingStats(
        per_month_cents=round(cents / months),
        per_week_cents=round(cents / weeks),
        runs_per_week=round(runs / weeks, 1),
        runs_per_week_by_person={r["person"]: round(r["runs"] / weeks, 1) for r in rows},
        per_run_cents=round(cents / runs) if runs else None,
    )
