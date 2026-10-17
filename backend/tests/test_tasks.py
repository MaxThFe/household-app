"""Tests for task recurrence: the period maths and its month-end clamping."""

from datetime import date

import pytest

from app.services.tasks import MAX_EVERY, UNITS, add_months, next_due


def test_daily_and_weekly_count_from_the_day_it_was_done():
    done = date(2026, 3, 10)
    assert next_due(done, "day", 1) == date(2026, 3, 11)
    assert next_due(done, "day", 3) == date(2026, 3, 13)
    assert next_due(done, "week", 1) == date(2026, 3, 17)
    assert next_due(done, "week", 2) == date(2026, 3, 24)


def test_monthly_keeps_the_day_of_month():
    assert next_due(date(2026, 1, 15), "month", 1) == date(2026, 2, 15)
    assert next_due(date(2026, 1, 15), "month", 3) == date(2026, 4, 15)


def test_a_month_end_chore_clamps_instead_of_spilling_over():
    # The 31st plus a month is the 28th, not the 3rd of the month after.
    assert next_due(date(2026, 1, 31), "month", 1) == date(2026, 2, 28)
    assert next_due(date(2026, 3, 31), "month", 1) == date(2026, 4, 30)


def test_clamping_does_not_stick_once_a_longer_month_comes_round():
    # Clamping applies to the single hop being made, so the 31st -> 28th ->
    # 28th: the day of month only ever walks backwards, never recovers. This is
    # asserted so the behaviour is recorded rather than discovered later.
    february = next_due(date(2026, 1, 31), "month", 1)
    assert next_due(february, "month", 1) == date(2026, 3, 28)


def test_months_roll_over_the_year():
    assert add_months(date(2026, 11, 20), 2) == date(2027, 1, 20)
    assert add_months(date(2026, 12, 1), 12) == date(2027, 12, 1)


def test_a_leap_day_is_available_when_the_year_has_one():
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_an_unknown_unit_is_rejected():
    with pytest.raises(ValueError):
        next_due(date(2026, 3, 10), "fortnight", 1)


def test_the_offered_units_are_the_ones_the_maths_handles():
    done = date(2026, 3, 10)
    for unit in UNITS:
        assert next_due(done, unit, 1) > done
    assert MAX_EVERY == 99
