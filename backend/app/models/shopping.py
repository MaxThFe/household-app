from pydantic import BaseModel, ConfigDict


class ShoppingItemCreate(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = ""
    store: str = ""


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


class ShoppingListResponse(BaseModel):
    supermarket: list[ShoppingItemResponse] = []
    household: list[ShoppingItemResponse] = []
