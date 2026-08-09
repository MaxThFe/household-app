from pydantic import BaseModel, ConfigDict


class ShoppingItemCreate(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = ""
    store: str = ""


class ShoppingItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    store: str | None = None


class ShoppingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None = None
    unit: str
    store: str
    source_recipe_id: int | None = None
    source_meal_id: int | None = None
    is_manual: int
    added_at: str
    source_names: str | None = None
    section: str = "other"


class SectionInfo(BaseModel):
    slug: str
    label: str


class MarketInfo(BaseModel):
    slug: str
    label: str


class SectionOrderUpdate(BaseModel):
    market: str
    order: list[str]


class ShoppingListResponse(BaseModel):
    categories: dict[str, list[ShoppingItemResponse]] = {}
    sections: list[SectionInfo] = []
    markets: list[MarketInfo] = []
    section_orders: dict[str, list[str]] = {}
