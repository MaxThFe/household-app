import asyncio
import logging
from datetime import datetime, timezone

import aiosqlite
import httpx
from icalendar import Calendar

from app.core.config import settings

logger = logging.getLogger(__name__)

MARGAUX_COLOR = "#D85A30"


def shift_type(start_time: str | None) -> str:
    """Return shift type label based on start time."""
    if not start_time:
        return "Shift"
    if start_time < "12:00":
        return "Early shift"
    if start_time < "17:00":
        return "Late shift"
    return "Night shift"


async def sync_ics(db: aiosqlite.Connection) -> None:
    if not settings.ics_url:
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(settings.ics_url, timeout=30)
        response.raise_for_status()

    cal = Calendar.from_ical(response.text)
    utc = timezone.utc
    seen_uids: set[str] = set()

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        if not uid:
            continue

        seen_uids.add(uid)
        notes = str(component.get("DESCRIPTION", ""))
        dtstart = component.get("DTSTART").dt
        dtend = component.get("DTEND")

        if isinstance(dtstart, datetime):
            all_day = 0
            if dtstart.tzinfo is not None:
                dtstart = dtstart.astimezone(utc).replace(tzinfo=None)
            date_str = dtstart.date().isoformat()
            start_time_str = dtstart.strftime("%H:%M")

            if dtend:
                dtend_val = dtend.dt
                if isinstance(dtend_val, datetime):
                    if dtend_val.tzinfo is not None:
                        dtend_val = dtend_val.astimezone(utc).replace(tzinfo=None)
                    end_time_str = dtend_val.strftime("%H:%M")
                else:
                    end_time_str = None
            else:
                end_time_str = None
        else:
            all_day = 1
            date_str = dtstart.isoformat()
            start_time_str = None
            end_time_str = None

        stype = shift_type(start_time_str)

        await db.execute(
            """
            INSERT INTO calendar_events (date, title, start_time, end_time, all_day, source, source_uid, color, notes)
            VALUES (?, ?, ?, ?, ?, 'ics', ?, ?, ?)
            ON CONFLICT(source_uid) DO UPDATE SET
                date=excluded.date,
                title=excluded.title,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                all_day=excluded.all_day,
                color=excluded.color,
                notes=excluded.notes
            """,
            (date_str, stype, start_time_str, end_time_str, all_day, uid, MARGAUX_COLOR, ""),
        )

    if seen_uids:
        placeholders = ",".join("?" * len(seen_uids))
        await db.execute(
            f"DELETE FROM calendar_events WHERE source='ics' AND source_uid NOT IN ({placeholders})",
            list(seen_uids),
        )
    else:
        await db.execute("DELETE FROM calendar_events WHERE source='ics'")

    await db.commit()
    logger.info("ICS sync complete: %d events processed", len(seen_uids))


async def run_ics_sync_loop() -> None:
    while True:
        try:
            async with aiosqlite.connect(settings.database_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                db.row_factory = aiosqlite.Row
                await sync_ics(db)
        except Exception:
            logger.exception("ICS sync failed")
        await asyncio.sleep(settings.ics_sync_interval_minutes * 60)
