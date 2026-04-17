import asyncio
import logging
from datetime import date, datetime, timedelta

import aiosqlite

from app.core.config import settings
from app.services.roborock import is_authenticated, start_cleaning

logger = logging.getLogger(__name__)

SHIFT_TIME_MAP = {
    "Early shift": "vacuum_early_shift_time",
    "Late shift": "vacuum_late_shift_time",
}


def _resolve_clean_time(
    shift_today: str | None, shift_yesterday: str | None
) -> str | None:
    # A night shift on day D means she works overnight D → D+1, so the
    # "coming home from night shift" slot belongs on the NEXT day.
    if shift_yesterday == "Night shift":
        return settings.vacuum_night_shift_time
    if shift_today == "Night shift":
        return None
    attr = SHIFT_TIME_MAP.get(shift_today or "", "vacuum_day_off_time")
    return getattr(settings, attr)


async def _get_shift_title(
    db: aiosqlite.Connection, date_str: str
) -> str | None:
    row = await db.execute_fetchall(
        "SELECT title FROM calendar_events WHERE date = ? AND source = 'ics' LIMIT 1",
        (date_str,),
    )
    return row[0]["title"] if row else None


async def get_cleaning_time_for_date(
    db: aiosqlite.Connection, date_str: str
) -> str | None:
    row = await db.execute_fetchall(
        "SELECT clean_time, deleted FROM vacuum_overrides WHERE date = ?",
        (date_str,),
    )
    if row:
        if row[0]["deleted"]:
            return None
        if row[0]["clean_time"]:
            return row[0]["clean_time"]

    shift_today = await _get_shift_title(db, date_str)
    prev_date = (date.fromisoformat(date_str) - timedelta(days=1)).isoformat()
    shift_yesterday = await _get_shift_title(db, prev_date)
    return _resolve_clean_time(shift_today, shift_yesterday)


async def get_weekly_schedule(
    db: aiosqlite.Connection, start: str, end: str
) -> list[dict]:
    prev_start = (date.fromisoformat(start) - timedelta(days=1)).isoformat()

    shifts = {}
    rows = await db.execute_fetchall(
        "SELECT date, title FROM calendar_events WHERE date >= ? AND date <= ? AND source = 'ics'",
        (prev_start, end),
    )
    for r in rows:
        shifts[r["date"]] = r["title"]

    overrides = {}
    override_rows = await db.execute_fetchall(
        "SELECT date, clean_time, deleted FROM vacuum_overrides WHERE date >= ? AND date <= ?",
        (start, end),
    )
    for r in override_rows:
        overrides[r["date"]] = {"clean_time": r["clean_time"], "deleted": r["deleted"]}

    current = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    schedule = []

    while current <= end_date:
        d = current.isoformat()
        prev_d = (current - timedelta(days=1)).isoformat()
        shift_type = shifts.get(d)
        shift_yesterday = shifts.get(prev_d)
        override = overrides.get(d)

        if override and override["deleted"]:
            schedule.append({
                "date": d,
                "shift_type": shift_type,
                "clean_time": None,
                "is_default": False,
            })
        elif override and override["clean_time"]:
            schedule.append({
                "date": d,
                "shift_type": shift_type,
                "clean_time": override["clean_time"],
                "is_default": False,
            })
        else:
            schedule.append({
                "date": d,
                "shift_type": shift_type,
                "clean_time": _resolve_clean_time(shift_type, shift_yesterday),
                "is_default": True,
            })

        current += timedelta(days=1)

    return schedule


async def run_vacuum_scheduler_loop() -> None:
    triggered_date: str | None = None
    triggered_time: str | None = None

    while True:
        try:
            if not is_authenticated():
                await asyncio.sleep(60)
                continue

            now = datetime.now()
            today = now.date().isoformat()
            current_time = now.strftime("%H:%M")

            if triggered_date == today and triggered_time == current_time:
                await asyncio.sleep(60)
                continue

            async with aiosqlite.connect(settings.database_path) as db:
                db.row_factory = aiosqlite.Row
                cleaning_time = await get_cleaning_time_for_date(db, today)

            if cleaning_time and current_time == cleaning_time:
                logger.info("Triggering vacuum cleaning at %s", current_time)
                await start_cleaning()
                triggered_date = today
                triggered_time = current_time

        except Exception:
            logger.exception("Vacuum scheduler error")

        await asyncio.sleep(60)
