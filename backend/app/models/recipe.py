from pydantic import BaseModel, ConfigDict, field_validator


class IngredientBase(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = ""

    @field_validator("name")
    @classmethod
    def lowercase_name(cls, v: str) -> str:
        return v.lower()


class IngredientCreate(IngredientBase):
    pass


class IngredientResponse(IngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: int


class RecipeBase(BaseModel):
    name: str
    tags: str = ""
    notes: str = ""


class RecipeCreate(RecipeBase):
    ingredients: list[IngredientCreate] = []


class RecipeUpdate(BaseModel):
    name: str | None = None
    tags: str | None = None
    notes: str | None = None
    ingredients: list[IngredientCreate] | None = None


class RecipeResponse(RecipeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: str
    ingredients: list[IngredientResponse] = []
