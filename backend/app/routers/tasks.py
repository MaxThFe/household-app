from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.task import TaskComplete, TaskCreate, TaskResponse, TaskUpdate
from app.services import tasks as tasks_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _fetch(db, task_id: int):
    async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@router.get("", response_model=list[TaskResponse])
async def list_tasks(db=Depends(get_db)):
    """Every task, longest-waiting first.

    A null next_due means "due now", so it sorts as the task's creation day and
    one-offs queue up among the recurring chores by age. Which of these are on
    the board is the client's call — it knows what day it is locally.
    """
    async with db.execute(
        """
        SELECT * FROM tasks
        ORDER BY COALESCE(next_due, date(created_at)), id
        """
    ) as cursor:
        rows = await cursor.fetchall()
    return [TaskResponse.model_validate(dict(row)) for row in rows]


@router.post("", response_model=TaskResponse, status_code=201)
async def add_task(body: TaskCreate, db=Depends(get_db), _=Depends(require_auth)):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")

    # next_due stays null: a task is wanted from the moment it is added, and a
    # recurring one only starts counting once it has been done.
    cursor = await db.execute(
        "INSERT INTO tasks (title, recur_unit, recur_every) VALUES (?, ?, ?)",
        (title, body.recur_unit, body.recur_every),
    )
    await db.commit()
    return TaskResponse.model_validate(dict(await _fetch(db, cursor.lastrowid)))


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int, body: TaskUpdate, db=Depends(get_db), _=Depends(require_auth)
):
    await _fetch(db, task_id)

    updates = body.model_dump(exclude_unset=True)
    if "title" in updates:
        updates["title"] = updates["title"].strip()
        if not updates["title"]:
            raise HTTPException(status_code=400, detail="Title is required")
    # Dropping the recurrence leaves a one-off, which has no schedule to keep.
    if updates.get("recur_unit", "keep") is None:
        updates["next_due"] = None

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        await db.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            list(updates.values()) + [task_id],
        )
        await db.commit()

    return TaskResponse.model_validate(dict(await _fetch(db, task_id)))


@router.post("/{task_id}/complete", status_code=204)
async def complete_task(
    task_id: int,
    body: TaskComplete | None = None,
    db=Depends(get_db),
    _=Depends(require_auth),
):
    """Tick a task off: a one-off is gone, a recurring one goes quiet."""
    row = await _fetch(db, task_id)
    done_on = (body.completed_on if body else None) or date.today()

    if not row["recur_unit"]:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    else:
        due = tasks_service.next_due(done_on, row["recur_unit"], row["recur_every"])
        await db.execute(
            "UPDATE tasks SET next_due = ? WHERE id = ?",
            (due.isoformat(), task_id),
        )
    await db.commit()


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int, db=Depends(get_db), _=Depends(require_auth)):
    await _fetch(db, task_id)
    await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.commit()
