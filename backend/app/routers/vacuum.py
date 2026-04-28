from fastapi import APIRouter, Depends

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.vacuum import VacuumOverrideCreate, VacuumScheduleEntry
from app.services.vacuum_scheduler import get_weekly_schedule

router = APIRouter(prefix="/vacuum", tags=["vacuum"])


@router.get("/schedule", response_model=list[VacuumScheduleEntry])
async def get_schedule(start: str, end: str, db=Depends(get_db)):
    return await get_weekly_schedule(db, start, end)


@router.put("/overrides/{date}", status_code=204)
async def set_override(
    date: str, body: VacuumOverrideCreate, db=Depends(get_db), _=Depends(require_auth)
):
    await db.execute(
        """
        INSERT INTO vacuum_overrides (date, clean_time, deleted) VALUES (?, ?, 0)
        ON CONFLICT(date) DO UPDATE SET clean_time=excluded.clean_time, deleted=0
        """,
        (date, body.clean_time),
    )
    await db.commit()


@router.delete("/overrides/{date}", status_code=204)
async def delete_cleaning(date: str, db=Depends(get_db), _=Depends(require_auth)):
    await db.execute(
        """
        INSERT INTO vacuum_overrides (date, clean_time, deleted) VALUES (?, NULL, 1)
        ON CONFLICT(date) DO UPDATE SET clean_time=NULL, deleted=1
        """,
        (date,),
    )
    await db.commit()


@router.post("/overrides/{date}/restore", status_code=204)
async def restore_default(date: str, db=Depends(get_db), _=Depends(require_auth)):
    await db.execute("DELETE FROM vacuum_overrides WHERE date = ?", (date,))
    await db.commit()
