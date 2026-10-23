import json

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.picnic import (
    PicnicAnswer,
    PicnicAnswerResult,
    PicnicMapping,
    PicnicOrderPreview,
    PicnicOrderRequest,
    PicnicOrderResult,
    PicnicProduct,
    PicnicQuestion,
    PicnicStatus,
)
from app.services import picnic, picnic_client

router = APIRouter(prefix="/picnic", tags=["picnic"])


def _product(data: dict) -> PicnicProduct:
    return PicnicProduct(
        product_id=data["product_id"],
        name=data.get("name") or "",
        unit_quantity=data.get("unit_quantity") or "",
        price=data.get("price"),
        image_url=picnic_client.image_url(data.get("image_id")),
    )


def _require_ready() -> None:
    if not picnic.llm_configured():
        raise HTTPException(status_code=503, detail="HT_OPENAI_API_KEY is not set")
    if not picnic_client.connected_users():
        raise HTTPException(status_code=503, detail="Nobody is logged in to Picnic — run picnic_setup.py")


@router.get("/status", response_model=PicnicStatus)
async def get_status(db=Depends(get_db), x_user: str | None = Header(default=None)):
    async with db.execute(
        "SELECT COUNT(*) FROM picnic_questions WHERE status = 'open'"
    ) as cursor:
        (open_questions,) = await cursor.fetchone()
    return PicnicStatus(
        connected=bool(x_user) and picnic_client.is_authenticated(x_user),
        any_connected=bool(picnic_client.connected_users()),
        llm_configured=picnic.llm_configured(),
        open_questions=open_questions,
        pending_items=len(await picnic.pending_items(db)),
        **picnic.job_status(),
    )


@router.post("/resolve", response_model=PicnicStatus)
async def resolve(db=Depends(get_db), user=Depends(require_auth)):
    _require_ready()
    picnic.start_mapping()
    return await get_status(db, user)


@router.get("/questions", response_model=list[PicnicQuestion])
async def get_questions(db=Depends(get_db)):
    async with db.execute(
        "SELECT * FROM picnic_questions WHERE status = 'open' ORDER BY item_key"
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        PicnicQuestion(
            id=r["id"], item_key=r["item_key"], recipe_id=r["recipe_id"],
            recipe_names=r["recipe_names"] or "", question=r["question"],
            candidates=[_product(c) for c in json.loads(r["candidates"] or "[]")],
        )
        for r in rows
    ]


@router.post("/questions/{question_id}/answer", response_model=PicnicAnswerResult)
async def answer_question(
    question_id: int, body: PicnicAnswer, db=Depends(get_db), _=Depends(require_auth)
):
    async with db.execute(
        "SELECT * FROM picnic_questions WHERE id = ? AND status = 'open'", (question_id,)
    ) as cursor:
        question = await cursor.fetchone()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    if body.scope == "recipe" and not question["recipe_id"]:
        raise HTTPException(status_code=400, detail="This question is not tied to one recipe")
    recipe_id = question["recipe_id"] if body.scope == "recipe" else 0

    async def close(answer: str) -> None:
        await db.execute(
            "UPDATE picnic_questions SET status = 'answered', answer = ? WHERE id = ?",
            (answer, question_id),
        )

    if body.skip:
        await picnic.save_mapping(db, question["item_key"], recipe_id, None, "user")
        await close("Not from Picnic.")
        await db.commit()
        return PicnicAnswerResult(result="skipped")

    if body.product_id:
        candidates = {c["product_id"]: c for c in json.loads(question["candidates"] or "[]")}
        product = candidates.get(body.product_id)
        if not product:
            raise HTTPException(status_code=400, detail="Not one of the offered products")
        await picnic.save_mapping(db, question["item_key"], recipe_id, product, "user")
        await close(f"{product['name']} ({product.get('unit_quantity', '')})")
        await db.commit()
        return PicnicAnswerResult(result="mapped")

    if not (body.text and body.text.strip()):
        raise HTTPException(status_code=400, detail="Pick a product, skip, or type an answer")
    _require_ready()
    await close(body.text.strip())
    await db.commit()
    # The answer is now part of the item's history, which map_and_save reads.
    names = [n for n in (question["recipe_names"] or "").split(", ") if n]
    try:
        result = await picnic.map_and_save(
            db, question["item_key"], question["item_key"], names,
            mapping_recipe_id=recipe_id, question_recipe_id=question["recipe_id"],
        )
    except picnic_client.PicnicNotConnected as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return PicnicAnswerResult(result=result)


@router.get("/mappings", response_model=list[PicnicMapping])
async def get_mappings(db=Depends(get_db)):
    async with db.execute(
        """SELECT m.*, r.name AS recipe_name FROM picnic_mappings m
           LEFT JOIN recipes r ON m.recipe_id = r.id
           ORDER BY m.item_key, m.recipe_id"""
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        PicnicMapping(
            id=r["id"], item_key=r["item_key"], recipe_id=r["recipe_id"],
            recipe_name=r["recipe_name"], status=r["status"], source=r["source"],
            updated_at=r["updated_at"],
            product=_product({**dict(r), "name": r["product_name"]}) if r["status"] == "mapped" else None,
        )
        for r in rows
    ]


@router.post("/mappings/{mapping_id}/reask", response_model=PicnicAnswerResult)
async def reask_mapping(mapping_id: int, db=Depends(get_db), _=Depends(require_auth)):
    """The cached product is wrong: forget it and let the LLM ask instead."""
    _require_ready()
    async with db.execute("SELECT * FROM picnic_mappings WHERE id = ?", (mapping_id,)) as cursor:
        mapping = await cursor.fetchone()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.execute("DELETE FROM picnic_mappings WHERE id = ?", (mapping_id,))
    await db.commit()
    rejected = mapping["product_name"] or "not ordering it from Picnic"
    try:
        return PicnicAnswerResult(result=await picnic.map_and_save(
            db, mapping["item_key"], mapping["item_key"], [],
            mapping_recipe_id=mapping["recipe_id"], question_recipe_id=mapping["recipe_id"],
            extra_qa=[(
                f"Is '{rejected}' right for {mapping['item_key']}?",
                "No. Ask us which product we mean, with a few alternatives.",
            )],
        ))
    except picnic_client.PicnicNotConnected as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.delete("/mappings/{mapping_id}", status_code=204)
async def delete_mapping(mapping_id: int, db=Depends(get_db), _=Depends(require_auth)):
    await db.execute("DELETE FROM picnic_mappings WHERE id = ?", (mapping_id,))
    await db.commit()


@router.get("/order-preview", response_model=PicnicOrderPreview)
async def get_order_preview(db=Depends(get_db)):
    return await picnic.order_preview(db)


@router.post("/order", response_model=list[PicnicOrderResult])
async def place_order(body: PicnicOrderRequest, user=Depends(require_auth)):
    """Into the cart of whoever is ordering."""
    if not picnic_client.is_authenticated(user):
        raise HTTPException(status_code=503, detail=f"{user} has no Picnic login — run picnic_setup.py")
    lines = [(line.product_id, line.count) for line in body.lines if line.count > 0]
    try:
        return await picnic.place_in_cart(user, lines)
    except picnic_client.PicnicNotConnected as exc:
        raise HTTPException(status_code=503, detail=str(exc))
