from typing import Literal

from pydantic import BaseModel


class PicnicProduct(BaseModel):
    product_id: str
    name: str
    unit_quantity: str = ""
    price: int | None = None  # cents
    image_url: str | None = None


class PicnicStatus(BaseModel):
    # Whether the asking user has their own Picnic login (needed to order),
    # and whether anyone does (needed to match items to products).
    connected: bool
    any_connected: bool
    llm_configured: bool
    running: bool
    total: int
    done: int
    error: str | None = None
    open_questions: int
    pending_items: int


class PicnicQuestion(BaseModel):
    id: int
    item_key: str
    recipe_id: int
    recipe_names: str
    question: str
    candidates: list[PicnicProduct]


class PicnicAnswer(BaseModel):
    product_id: str | None = None
    text: str | None = None
    skip: bool = False
    # "recipe" stores the answer for the question's recipe only.
    scope: Literal["global", "recipe"] = "global"


class PicnicAnswerResult(BaseModel):
    result: Literal["mapped", "skipped", "asked"]


class PicnicMapping(BaseModel):
    id: int
    item_key: str
    recipe_id: int
    recipe_name: str | None = None
    status: Literal["mapped", "skip"]
    product: PicnicProduct | None = None
    source: str
    updated_at: str


class PicnicOrderLine(BaseModel):
    product_id: str
    name: str
    unit_quantity: str = ""
    price: int | None = None
    image_url: str | None = None
    count: int
    items: list[str]


class PicnicOrderPreview(BaseModel):
    lines: list[PicnicOrderLine]
    unmapped: list[str]
    skipped: list[str]


class PicnicOrderItem(BaseModel):
    product_id: str
    count: int


class PicnicOrderRequest(BaseModel):
    lines: list[PicnicOrderItem]


class PicnicOrderResult(BaseModel):
    product_id: str
    ok: bool
    error: str | None = None
