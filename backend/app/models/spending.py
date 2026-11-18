from pydantic import BaseModel


class SpendingMonth(BaseModel):
    month: str  # YYYY-MM
    store: str
    total_cents: int
    purchases: int


class PurchaseSummary(BaseModel):
    id: int
    store: str
    person: str | None
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


class SyncSource(BaseModel):
    source: str  # store:account
    store: str
    account: str
    last_attempt: str | None
    last_success: str | None
    error: str | None


class SpendingStatus(BaseModel):
    since: str
    sources: list[SyncSource]
