from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.meal import MealCreate, MealResponse, MealUpdate

router = APIRouter(prefix="/meals", tags=["meals"])


def _parse_week(week_str: str) -> tuple[str, str]:
    """Return (monday_iso, sunday_iso) for an ISO week string like '2024-W12'."""
    monday = datetime.strptime(week_str + "-1", "%G-W%V-%u")
    sunday = monday + timedelta(days=6)
    return monday.date().isoformat(), sunday.date().isoformat()


def _compute_attendants(meal_date: str, shift_rows: list) -> int:
    """Return 1 if any ICS event on that date is an evening/late shift, else 2."""
    for row in shift_rows:
        if row["date"] != meal_date:
            continue
        end_time = row["end_time"] or ""
        start_time = row["start_time"] or ""
        if end_time > "18:00" or start_time >= "15:00":
            return 1
    return 2


@router.get("", response_model=list[MealResponse])
async def list_meals(week: str | None = None, db=Depends(get_db)):
    if week:
        try:
            monday, sunday = _parse_week(week)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid week format. Use YYYY-Www")
        async with db.execute(
            """
            SELECT m.*, r.name as recipe_name
            FROM meals m
            LEFT JOIN recipes r ON m.recipe_id = r.id
            WHERE m.date BETWEEN ? AND ?
            ORDER BY m.date
            """,
            (monday, sunday),
        ) as cursor:
            meals = await cursor.fetchall()

        async with db.execute(
            """
            SELECT date, start_time, end_time FROM calendar_events
            WHERE source='ics' AND date BETWEEN ? AND ?
            """,
            (monday, sunday),
        ) as cursor:
            shifts = await cursor.fetchall()
    else:
        async with db.execute(
            """
            SELECT m.*, r.name as recipe_name
            FROM meals m
            LEFT JOIN recipes r ON m.recipe_id = r.id
            ORDER BY m.date
            """
        ) as cursor:
            meals = await cursor.fetchall()
        shifts = []

    result = []
    for meal in meals:
        m = dict(meal)
        m["attendants"] = _compute_attendants(m["date"], [dict(s) for s in shifts])
        result.append(MealResponse.model_validate(m))
    return result


@router.post("", response_model=MealResponse, status_code=201)
async def create_meal(body: MealCreate, db=Depends(get_db), _=Depends(require_auth)):
    try:
        cursor = await db.execute(
            "INSERT INTO meals (date, recipe_id, custom_name, notes) VALUES (?, ?, ?, ?)",
            (body.date, body.recipe_id, body.custom_name, body.notes),
        )
        meal_id = cursor.lastrowid
    except Exception:
        raise HTTPException(status_code=409, detail="A meal already exists for that date")

    if body.ingredient_ids and body.recipe_id:
        for ing_id in body.ingredient_ids:
            async with db.execute(
                "SELECT * FROM ingredients WHERE id = ? AND recipe_id = ?",
                (ing_id, body.recipe_id),
            ) as cur:
                ing = await cur.fetchone()
            if ing:
                await db.execute(
                    """
                    INSERT INTO shopping_items (name, quantity, unit, source_recipe_id, source_meal_id, is_manual)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (ing["name"], ing["quantity"], ing["unit"], body.recipe_id, meal_id),
                )

    await db.commit()

    async with db.execute(
        "SELECT m.*, r.name as recipe_name FROM meals m LEFT JOIN recipes r ON m.recipe_id = r.id WHERE m.id = ?",
        (meal_id,),
    ) as cur:
        meal = await cur.fetchone()

    return MealResponse.model_validate(dict(meal))


@router.patch("/{meal_id}", response_model=MealResponse)
async def update_meal(
    meal_id: int, body: MealUpdate, db=Depends(get_db), _=Depends(require_auth)
):
    async with db.execute("SELECT id FROM meals WHERE id = ?", (meal_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Meal not found")

    updates = body.model_dump(exclude_none=True)
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        await db.execute(
            f"UPDATE meals SET {set_clause} WHERE id=?",
            (*updates.values(), meal_id),
        )
        await db.commit()

    async with db.execute(
        "SELECT m.*, r.name as recipe_name FROM meals m LEFT JOIN recipes r ON m.recipe_id = r.id WHERE m.id = ?",
        (meal_id,),
    ) as cur:
        meal = await cur.fetchone()

    return MealResponse.model_validate(dict(meal))


@router.delete("/{meal_id}", status_code=204)
async def delete_meal(meal_id: int, db=Depends(get_db), _=Depends(require_auth)):
    async with db.execute("SELECT id FROM meals WHERE id = ?", (meal_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Meal not found")
    await db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    await db.commit()
