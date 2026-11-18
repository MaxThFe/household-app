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
