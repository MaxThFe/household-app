"""Tests for the general calendar feed."""

import time
from datetime import date

from icalendar import Calendar

from app.services.ics_sync import _general_rows, _work_rows

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


WORK_FEED = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:standup\r
SUMMARY:Standup\r
DTSTART:20260921T080000Z\r
DTEND:20260921T083000Z\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:colloquium\r
SUMMARY:Colloquium\r
DTSTART:20260922T140000Z\r
DTEND:20260922T163000Z\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:conference\r
SUMMARY:Conference Utrecht\r
DTSTART;VALUE=DATE:20260923\r
DTEND;VALUE=DATE:20260925\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:deadline\r
SUMMARY:Dealine paper revision\r
DTSTART;VALUE=DATE:20260924\r
DTEND;VALUE=DATE:20260925\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_work_feed_keeps_evenings_and_whole_days_but_not_deadlines(monkeypatch):
    # 16:30 UTC is 18:30 CEST, so the colloquium runs into the evening.
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    try:
        rows = list(_work_rows(Calendar.from_ical(WORK_FEED), today=date(2026, 9, 21)))
    finally:
        monkeypatch.undo()
        time.tzset()

    # The morning standup is gone; the multi-day conference shows on both days;
    # the misspelled deadline is dropped even though it is a whole day.
    assert [(r.date, r.title) for r in rows] == [
        ("2026-09-22", "Colloquium"),
        ("2026-09-23", "Conference Utrecht"),
        ("2026-09-24", "Conference Utrecht"),
    ]
