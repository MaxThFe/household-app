from pydantic import BaseModel, ConfigDict, model_validator


class MealCreate(BaseModel):
    date: str
    recipe_id: int | None = None
    custom_name: str | None = None
    notes: str = ""
    ingredient_ids: list[int] = []

    @model_validator(mode="after")
    def require_recipe_or_custom_name(self) -> "MealCreate":
        if self.recipe_id is None and not self.custom_name:
            raise ValueError("Either recipe_id or custom_name must be provided")
        return self


class MealUpdate(BaseModel):
    notes: str | None = None
    attendants: int | None = None


class MealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: str
    recipe_id: int | None = None
    recipe_name: str | None = None
    custom_name: str | None = None
    notes: str
    attendants: int
