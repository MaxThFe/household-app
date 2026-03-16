from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.shopping import ShoppingItemCreate, ShoppingItemResponse, ShoppingListResponse

router = APIRouter(prefix="/shopping", tags=["shopping"])


@router.get("", response_model=ShoppingListResponse)
async def get_shopping_list(db=Depends(get_db)):
    async with db.execute(
        """
        SELECT
            MIN(si.id) as id,
            si.name,
            SUM(si.quantity) as quantity,
            si.unit,
            si.store,
            MIN(si.source_recipe_id) as source_recipe_id,
            MIN(si.source_meal_id) as source_meal_id,
            MAX(si.is_manual) as is_manual,
            MIN(si.added_at) as added_at,
            REPLACE(GROUP_CONCAT(DISTINCT r.name), ',', ' + ') as source_names
        FROM shopping_items si
        LEFT JOIN recipes r ON si.source_recipe_id = r.id
        GROUP BY si.name, si.unit, si.store
        ORDER BY si.store, si.name
        """
    ) as cursor:
        rows = await cursor.fetchall()

    supermarket = []
    household = []
    for row in rows:
        item = ShoppingItemResponse.model_validate(dict(row))
        if item.store.lower() in ("", "supermarket"):
            supermarket.append(item)
        else:
            household.append(item)

    return ShoppingListResponse(supermarket=supermarket, household=household)


@router.post("", response_model=ShoppingItemResponse, status_code=201)
async def add_shopping_item(
    body: ShoppingItemCreate, db=Depends(get_db), _=Depends(require_auth)
):
    cursor = await db.execute(
        "INSERT INTO shopping_items (name, quantity, unit, store, is_manual) VALUES (?, ?, ?, ?, 1)",
        (body.name, body.quantity, body.unit, body.store),
    )
    item_id = cursor.lastrowid
    await db.commit()
    async with db.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)) as cur:
        item = await cur.fetchone()
    return ShoppingItemResponse.model_validate(dict(item))


# IMPORTANT: "checked" route must be registered BEFORE "/{item_id}" to avoid routing conflict
@router.delete("/checked", status_code=204)
async def delete_checked_items(
    ids: list[int] = Query(default=[]), db=Depends(get_db), _=Depends(require_auth)
):
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    await db.execute(f"DELETE FROM shopping_items WHERE id IN ({placeholders})", ids)
    await db.commit()


@router.delete("/{item_id}", status_code=204)
async def delete_shopping_item(item_id: int, db=Depends(get_db), _=Depends(require_auth)):
    async with db.execute(
        "SELECT name, unit, store FROM shopping_items WHERE id = ?", (item_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.execute(
        "DELETE FROM shopping_items WHERE name = ? AND unit = ? AND store = ?",
        (row["name"], row["unit"], row["store"]),
    )
    await db.commit()
