"""Recurrence for household tasks: when a finished chore comes due again.

A recurring task carries a unit ('day' / 'week' / 'month') and a multiplier, so
"once a week" is week × 1 and "every three months" is month × 3. There is no
weekday or day-of-month anchor, and no due date the household ever sees or
sets: the next due date is counted from the day the task was actually *done*,
and it only decides whether the task is back on the board yet.

Counting from the completion day is deliberate. A chore done two days late is
wanted a full period after that, not immediately again — anchoring to the old
due date would leave a skipped week permanently overdue.
"""

import calendar
from datetime import date, timedelta

# Recurrence units, in the order the task page offers them
UNITS: tuple[str, ...] = ("day", "week", "month")

# Upper bound on the multiplier, so "every N" cannot be set to nonsense
MAX_EVERY = 99


def add_months(start: date, months: int) -> date:
    """Shift by whole months, clamping onto the end of a shorter month.

    The 31st plus one month is the 30th (or the 28th/29th in February), which
    keeps a monthly chore on month-end rather than drifting into the next one.
    """
    index = start.month - 1 + months
    year = start.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def next_due(completed_on: date, unit: str, every: int) -> date:
    """The day a task recurring every `every` `unit`s is wanted again."""
    if unit == "day":
        return completed_on + timedelta(days=every)
    if unit == "week":
        return completed_on + timedelta(weeks=every)
    if unit == "month":
        return add_months(completed_on, every)
    raise ValueError(f"unknown recurrence unit: {unit}")
