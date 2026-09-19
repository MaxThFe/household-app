"""Tests for the general calendar feed."""

import time
from datetime import date

from icalendar import Calendar

from app.services.ics_sync import _general_rows

FEED = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:choir\r
SUMMARY:Choir\r
DTSTART:20240101T180000Z\r
DTEND:20240101T200000Z\r
RRULE:FREQ=WEEKLY;BYDAY=MO\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:birthday\r
SUMMARY:Verjaardag Judith\r
DTSTART;VALUE=DATE:20190920\r
RRULE:FREQ=YEARLY\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_old_weekly_series_shows_this_week_in_local_time_without_birthdays(monkeypatch):
    # The container runs on Berlin time.
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    try:
        rows = list(_general_rows(Calendar.from_ical(FEED), today=date(2026, 9, 19)))
    finally:
        monkeypatch.undo()
        time.tzset()

    this_week = [r for r in rows if "2026-09-19" <= r.date <= "2026-09-27"]
    # Started in 2024, still shows up; 18:00 UTC is 20:00 CEST.
    assert [(r.date, r.start_time, r.end_time) for r in this_week] == [("2026-09-21", "20:00", "22:00")]
    # The yearly reminder on 20 Sep is left out.
    assert all(r.title == "Choir" for r in rows)
