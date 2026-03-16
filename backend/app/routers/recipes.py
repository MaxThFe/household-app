from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.recipe import RecipeCreate, RecipeResponse, RecipeUpdate

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeResponse])
async def list_recipes(search: str = "", tag: str = "", db=Depends(get_db)):
    query = "SELECT * FROM recipes WHERE 1=1"
    params: list = []
    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    if tag:
        query += " AND (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag},%")
    query += " ORDER BY name"

    async with db.execute(query, params) as cursor:
        recipes = await cursor.fetchall()

    result = []
    for recipe in recipes:
        async with db.execute(
            "SELECT * FROM ingredients WHERE recipe_id = ?", (recipe["id"],)
        ) as cursor:
            ingredients = await cursor.fetchall()
        r = dict(recipe)
        r["ingredients"] = [dict(i) for i in ingredients]
        result.append(RecipeResponse.model_validate(r))
    return result


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(recipe_id: int, db=Depends(get_db)):
    async with db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)) as cursor:
        recipe = await cursor.fetchone()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    async with db.execute(
        "SELECT * FROM ingredients WHERE recipe_id = ?", (recipe_id,)
    ) as cursor:
        ingredients = await cursor.fetchall()
    r = dict(recipe)
    r["ingredients"] = [dict(i) for i in ingredients]
    return RecipeResponse.model_validate(r)


@router.post("", response_model=RecipeResponse, status_code=201)
async def create_recipe(body: RecipeCreate, db=Depends(get_db), _=Depends(require_auth)):
    cursor = await db.execute(
        "INSERT INTO recipes (name, tags, notes) VALUES (?, ?, ?)",
        (body.name, body.tags, body.notes),
    )
    recipe_id = cursor.lastrowid

    ingredients = []
    for ing in body.ingredients:
        c = await db.execute(
            "INSERT INTO ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
            (recipe_id, ing.name, ing.quantity, ing.unit),
        )
        ingredients.append({"id": c.lastrowid, "recipe_id": recipe_id, **ing.model_dump()})

    await db.commit()

    async with db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)) as cur:
        recipe = await cur.fetchone()

    r = dict(recipe)
    r["ingredients"] = ingredients
    return RecipeResponse.model_validate(r)


@router.patch("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int, body: RecipeUpdate, db=Depends(get_db), _=Depends(require_auth)
):
    async with db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)) as cursor:
        recipe = await cursor.fetchone()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    updates = body.model_dump(exclude_none=True, exclude={"ingredients"})
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        await db.execute(
            f"UPDATE recipes SET {set_clause} WHERE id=?",
            (*updates.values(), recipe_id),
        )

    if body.ingredients is not None:
        await db.execute("DELETE FROM ingredients WHERE recipe_id=?", (recipe_id,))
        for ing in body.ingredients:
            await db.execute(
                "INSERT INTO ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
                (recipe_id, ing.name, ing.quantity, ing.unit),
            )

    await db.commit()

    async with db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)) as cur:
        recipe = await cur.fetchone()
    async with db.execute(
        "SELECT * FROM ingredients WHERE recipe_id = ?", (recipe_id,)
    ) as cur:
        ingredients = await cur.fetchall()

    r = dict(recipe)
    r["ingredients"] = [dict(i) for i in ingredients]
    return RecipeResponse.model_validate(r)


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(recipe_id: int, db=Depends(get_db), _=Depends(require_auth)):
    async with db.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)) as cursor:
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")
    await db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    await db.commit()
