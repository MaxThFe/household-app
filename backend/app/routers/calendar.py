from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_auth
from app.core.database import get_db
from app.models.calendar import CalendarEventCreate, CalendarEventResponse, CalendarEventUpdate
from app.services.ics_sync import sync_ics

router = APIRouter(prefix="/calendar", tags=["calendar"])

ICS_SOURCES = {"ics", "google"}


@router.get("", response_model=list[CalendarEventResponse])
async def list_events(month: str | None = None, db=Depends(get_db)):
    async with db:
        if month:
            async with db.execute(
                "SELECT * FROM calendar_events WHERE date LIKE ? ORDER BY date, start_time",
                (f"{month}%",),
            ) as cursor:
                events = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM calendar_events ORDER BY date, start_time"
            ) as cursor:
                events = await cursor.fetchall()
    return [CalendarEventResponse.model_validate(dict(e)) for e in events]


@router.post("", response_model=CalendarEventResponse, status_code=201)
async def create_event(
    body: CalendarEventCreate, db=Depends(get_db), _=Depends(require_auth)
):
    async with db:
        cursor = await db.execute(
            """
            INSERT INTO calendar_events (date, title, start_time, end_time, all_day, source, color, notes)
            VALUES (?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (body.date, body.title, body.start_time, body.end_time, body.all_day, body.color, body.notes),
        )
        event_id = cursor.lastrowid
        await db.commit()
        async with db.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ) as cur:
            event = await cur.fetchone()
    return CalendarEventResponse.model_validate(dict(event))


@router.patch("/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: int, body: CalendarEventUpdate, db=Depends(get_db), _=Depends(require_auth)
):
    async with db:
        async with db.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ) as cursor:
            event = await cursor.fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event["source"] in ICS_SOURCES:
            raise HTTPException(status_code=403, detail="Cannot modify ICS-synced events")

        updates = body.model_dump(exclude_none=True)
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            await db.execute(
                f"UPDATE calendar_events SET {set_clause} WHERE id=?",
                (*updates.values(), event_id),
            )
            await db.commit()

        async with db.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ) as cur:
            event = await cur.fetchone()
    return CalendarEventResponse.model_validate(dict(event))


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: int, db=Depends(get_db), _=Depends(require_auth)):
    async with db:
        async with db.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ) as cursor:
            event = await cursor.fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event["source"] in ICS_SOURCES:
            raise HTTPException(status_code=403, detail="Cannot delete ICS-synced events")
        await db.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
        await db.commit()


@router.post("/sync", status_code=204)
async def trigger_sync(db=Depends(get_db), _=Depends(require_auth)):
    async with db:
        await sync_ics(db)
