from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.houseplant import HouseplantCreate, HouseplantResponse, HouseplantUpdate

router = APIRouter(prefix="/houseplants", tags=["houseplants"])

MAX_IMAGE_LEN = 200_000

SELECT_COLUMNS = """
    id,
    name,
    watering_frequency_days,
    last_watered_at,
    image_data,
    created_at,
    watering_frequency_days - CAST((julianday('now') - julianday(last_watered_at)) AS INTEGER) AS days_until_due
"""


def _validate_image(image_data: str | None) -> None:
    if image_data is not None and len(image_data) > MAX_IMAGE_LEN:
        raise HTTPException(status_code=413, detail="Image too large")


@router.get("", response_model=list[HouseplantResponse])
async def list_houseplants(db=Depends(get_db)):
    async with db.execute(
        f"SELECT {SELECT_COLUMNS} FROM houseplants ORDER BY days_until_due ASC, name ASC"
    ) as cursor:
        rows = await cursor.fetchall()
    return [HouseplantResponse.model_validate(dict(row)) for row in rows]


@router.post("", response_model=HouseplantResponse, status_code=201)
async def add_houseplant(
    body: HouseplantCreate, db=Depends(get_db), _=Depends(require_auth)
):
    _validate_image(body.image_data)
    cursor = await db.execute(
        "INSERT INTO houseplants (name, watering_frequency_days, image_data) VALUES (?, ?, ?)",
        (body.name, body.watering_frequency_days, body.image_data),
    )
    plant_id = cursor.lastrowid
    await db.commit()
    async with db.execute(
        f"SELECT {SELECT_COLUMNS} FROM houseplants WHERE id = ?", (plant_id,)
    ) as cur:
        row = await cur.fetchone()
    return HouseplantResponse.model_validate(dict(row))


@router.patch("/{plant_id}", response_model=HouseplantResponse)
async def update_houseplant(
    plant_id: int,
    body: HouseplantUpdate,
    db=Depends(get_db),
    _=Depends(require_auth),
):
    async with db.execute(
        "SELECT id FROM houseplants WHERE id = ?", (plant_id,)
    ) as cursor:
        existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Plant not found")

    updates = body.model_dump(exclude_unset=True)
    if "image_data" in updates:
        _validate_image(updates["image_data"])

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [plant_id]
        await db.execute(
            f"UPDATE houseplants SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

    async with db.execute(
        f"SELECT {SELECT_COLUMNS} FROM houseplants WHERE id = ?", (plant_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return HouseplantResponse.model_validate(dict(row))


@router.post("/{plant_id}/water", response_model=HouseplantResponse)
async def water_houseplant(
    plant_id: int, db=Depends(get_db), _=Depends(require_auth)
):
    async with db.execute(
        "SELECT id FROM houseplants WHERE id = ?", (plant_id,)
    ) as cursor:
        existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Plant not found")

    await db.execute(
        "UPDATE houseplants SET last_watered_at = datetime('now') WHERE id = ?",
        (plant_id,),
    )
    await db.commit()

    async with db.execute(
        f"SELECT {SELECT_COLUMNS} FROM houseplants WHERE id = ?", (plant_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return HouseplantResponse.model_validate(dict(row))


@router.delete("/{plant_id}", status_code=204)
async def delete_houseplant(
    plant_id: int, db=Depends(get_db), _=Depends(require_auth)
):
    async with db.execute(
        "SELECT id FROM houseplants WHERE id = ?", (plant_id,)
    ) as cursor:
        existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Plant not found")
    await db.execute("DELETE FROM houseplants WHERE id = ?", (plant_id,))
    await db.commit()
