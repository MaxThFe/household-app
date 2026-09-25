import asyncio
import logging
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher

import aiosqlite
import httpx
import recurring_ical_events
from icalendar import Calendar

from app.core.config import settings

logger = logging.getLogger(__name__)

MARGAUX_SHIFT_COLOR = "#D85A30"
MARGAUX_GENERAL_COLOR = "#2F8F8A"
# Work events are Max's, so they carry the same colour as his own entries.
MAX_COLOR = "#534AB7"

# Only the part of the work calendar the household is affected by: events
# running into the evening, and whole days away.
WORK_EVENING_FROM = "17:00"
# A deadline is a date, not a day away, so those whole days are dropped. Titles
# are typed by hand, so match the word loosely enough to catch a typo.
DEADLINE_SIMILARITY = 0.85

# Repeating events have no natural end, so the general feed is only expanded
# over this window around today.
GENERAL_DAYS_BACK = 90
GENERAL_DAYS_AHEAD = 365


@dataclass(frozen=True)
class Row:
    uid: str
    date: str
    start_time: str | None
    end_time: str | None
    all_day: int
    title: str
    notes: str


def shift_type(start_time: str | None, summary: str = "") -> str:
    """Return shift type label based on start time and ICS summary code."""
    day_off_codes = {c.strip() for c in settings.day_off_codes.split(",") if c.strip()}
    if summary in day_off_codes:
        return "Day off"
    if not start_time:
        return "Shift"
    if start_time < "12:00":
        return "Early shift"
    if start_time < "17:00":
        return "Late shift"
    return "Night shift"


def _shift_rows(cal: Calendar) -> Iterator[Row]:
    utc = timezone.utc
    for component in cal.walk("VEVENT"):
        uid = str(component.get("UID", ""))
        if not uid:
            continue

        dtstart = component.get("DTSTART").dt
        dtend = component.get("DTEND")

        if isinstance(dtstart, datetime):
            all_day = 0
            if dtstart.tzinfo is not None:
                dtstart = dtstart.astimezone(utc).replace(tzinfo=None)
            date_str = dtstart.date().isoformat()
            start_time_str = dtstart.strftime("%H:%M")
            end_time_str = None

            if dtend:
                dtend_val = dtend.dt
                if isinstance(dtend_val, datetime):
                    if dtend_val.tzinfo is not None:
                        dtend_val = dtend_val.astimezone(utc).replace(tzinfo=None)
                    # The shift feed carries zero-length placeholder events.
                    if (dtend_val - dtstart).total_seconds() / 60 < 10:
                        continue
                    end_time_str = dtend_val.strftime("%H:%M")
        else:
            all_day = 1
            date_str = dtstart.isoformat()
            start_time_str = None
            end_time_str = None

        summary = str(component.get("SUMMARY", ""))
        yield Row(uid, date_str, start_time_str, end_time_str, all_day, shift_type(start_time_str, summary), "")


def _is_yearly(component) -> bool:
    rrule = component.get("RRULE")
    return bool(rrule) and "YEARLY" in rrule.get("FREQ", [])


def _local(value: datetime) -> datetime:
    """Wall-clock time in the household's zone; floating times already are."""
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)


def _general_rows(cal: Calendar, today: date | None = None, prefix: str = "general") -> Iterator[Row]:
    today = today or date.today()
    # Yearly series are birthday and anniversary reminders, not plans. Their
    # one-off changes share the series UID, so drop by UID, not by component.
    yearly = {str(c.get("UID", "")) for c in cal.walk("VEVENT") if _is_yearly(c)}

    window = recurring_ical_events.of(cal).between(
        today - timedelta(days=GENERAL_DAYS_BACK),
        today + timedelta(days=GENERAL_DAYS_AHEAD),
    )
    for occurrence in window:
        uid = str(occurrence.get("UID", ""))
        if not uid or uid in yearly:
            continue
        if str(occurrence.get("STATUS", "")) == "CANCELLED":
            continue
        summary = str(occurrence.get("SUMMARY", "")).strip()

        dtstart = occurrence["DTSTART"].dt
        # Occurrences of one series share a UID; the original start of each
        # occurrence tells them apart and survives it being moved.
        recurrence_id = occurrence.get("RECURRENCE-ID")
        key = (recurrence_id.dt if recurrence_id else dtstart).isoformat()
        row_uid = f"{prefix}:{uid}:{key}"
        notes = str(occurrence.get("DESCRIPTION", ""))
        title = summary or "Busy"

        if not isinstance(dtstart, datetime):
            # An all-day event ends the day before its DTEND; show it on
            # every day it covers, so a holiday is visible all week.
            dtend = occurrence.get("DTEND")
            last_day = dtend.dt - timedelta(days=1) if dtend is not None else dtstart
            day = dtstart
            while True:
                yield Row(f"{row_uid}:{day.isoformat()}", day.isoformat(), None, None, 1, title, notes)
                day += timedelta(days=1)
                if day > last_day:
                    break
            continue

        start = _local(dtstart)
        end_time = None
        if occurrence.get("DTEND") is not None:
            end = occurrence["DTEND"].dt
            if isinstance(end, datetime):
                end_time = _local(end).strftime("%H:%M")
        elif occurrence.get("DURATION") is not None:
            end_time = (start + occurrence["DURATION"].dt).strftime("%H:%M")

        yield Row(row_uid, start.date().isoformat(), start.strftime("%H:%M"), end_time, 0, title, notes)


def _reads_as_deadline(title: str) -> bool:
    """True if a word of the title is "deadline", however it is spelled."""
    return any(
        SequenceMatcher(None, word, "deadline").ratio() >= DEADLINE_SIMILARITY
        for word in re.findall(r"[a-z]+", title.lower())
    )


def _runs_into_the_evening(row: Row) -> bool:
    if row.start_time is None:
        return False
    if row.start_time >= WORK_EVENING_FROM:
        return True
    if row.end_time is None:
        return False
    # An end before the start is the morning after, so the evening is covered.
    return row.end_time > WORK_EVENING_FROM or row.end_time < row.start_time


def _work_rows(cal: Calendar, today: date | None = None) -> Iterator[Row]:
    """The work calendar, minus the events the household is unaffected by."""
    for row in _general_rows(cal, today, prefix="work"):
        if row.all_day:
            if not _reads_as_deadline(row.title):
                yield row
        elif _runs_into_the_evening(row):
            yield row


@dataclass(frozen=True)
class IcsFeed:
    """One ICS feed, owning its own rows in calendar_events via `source`."""

    source: str
    url: str
    color: str
    rows: Callable[[Calendar], Iterator[Row]]


def _feeds() -> list[IcsFeed]:
    feeds = []
    if settings.ics_url:
        feeds.append(IcsFeed("ics", settings.ics_url, MARGAUX_SHIFT_COLOR, _shift_rows))
    if settings.ics_general_url:
        feeds.append(IcsFeed("ics_general", settings.ics_general_url, MARGAUX_GENERAL_COLOR, _general_rows))
    if settings.ics_work_url:
        feeds.append(IcsFeed("ics_work", settings.ics_work_url, MAX_COLOR, _work_rows))
    return feeds


async def _sync_feed(db: aiosqlite.Connection, feed: IcsFeed) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(feed.url, timeout=30)
        response.raise_for_status()

    cal = Calendar.from_ical(response.text)
    seen_uids: set[str] = set()

    for row in feed.rows(cal):
        seen_uids.add(row.uid)
        await db.execute(
            """
            INSERT INTO calendar_events (date, title, start_time, end_time, all_day, source, source_uid, color, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_uid) DO UPDATE SET
                date=excluded.date,
                title=excluded.title,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                all_day=excluded.all_day,
                color=excluded.color,
                notes=excluded.notes
            """,
            (row.date, row.title, row.start_time, row.end_time, row.all_day, feed.source, row.uid, feed.color, row.notes),
        )

    if seen_uids:
        placeholders = ",".join("?" * len(seen_uids))
        await db.execute(
            f"DELETE FROM calendar_events WHERE source=? AND source_uid NOT IN ({placeholders})",
            [feed.source, *seen_uids],
        )
    else:
        await db.execute("DELETE FROM calendar_events WHERE source=?", (feed.source,))

    await db.commit()
    logger.info("ICS sync complete for %s: %d events processed", feed.source, len(seen_uids))


async def sync_ics(db: aiosqlite.Connection) -> None:
    for feed in _feeds():
        try:
            await _sync_feed(db, feed)
        except Exception:
            # One unreachable feed should not take the other down with it.
            logger.exception("ICS sync failed for %s", feed.source)


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
