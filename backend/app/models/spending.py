from pydantic import BaseModel


class SpendingMonth(BaseModel):
    month: str  # YYYY-MM
    store: str
    total_cents: int
    purchases: int


class SpendingMonths(BaseModel):
    since: str  # first day counted, YYYY-MM-DD
    months: list[SpendingMonth]


class PurchaseSummary(BaseModel):
    id: int
    store: str
    person: str
    purchased_at: str
    total_cents: int
    store_name: str
    item_count: int


class PurchaseItem(BaseModel):
    line_no: int
    name: str
    product_id: str | None
    quantity: float | None
    unit: str
    unit_quantity: str
    unit_price_cents: int | None
    amount_cents: int | None
    discount_cents: int


class PurchaseDetail(PurchaseSummary):
    items: list[PurchaseItem]


class FailingAccount(BaseModel):
    store: str
    person: str


class SpendingStats(BaseModel):
    """Averages over the complete months since grocery_since; None until
    there is one."""
    per_month_cents: int | None
    per_week_cents: int | None
    runs_per_week: float | None
    runs_per_week_by_person: dict[str, float]
    per_run_cents: int | None
