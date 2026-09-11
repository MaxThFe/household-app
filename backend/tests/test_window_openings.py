"""Tests for window-opening detection: the slope-break rule and its debounce."""

from app.services.window_openings import (
    COOLDOWN_SECONDS,
    WINDOW_SECONDS,
    detect_window_openings,
)

T0 = 1_755_000_000  # an arbitrary epoch second; only the offsets matter
DROP = 0.6


def series(*segments: tuple[int, float], start: float = 21.0) -> list[tuple[int, float]]:
    """Minute-by-minute points from (minutes, °C per hour) segments."""
    points = [(T0, start)]
    for minutes, per_hour in segments:
        for _ in range(minutes):
            ts, value = points[-1]
            points.append((ts + 60, round(value + per_hour / 60, 4)))
    return points


def minutes_after_start(ts: int) -> int:
    return (ts - T0) // 60


def test_flat_room_then_a_sharp_fall_is_one_opening():
    # Flat for an hour, then -1.5 °C over 20 minutes: -1.5 against 0.0.
    points = series((60, 0.0), (20, -4.5), (60, 0.0))
    events = detect_window_openings(points, DROP)
    assert len(events) == 1
    # Stamped where the fall begins, not where it is first provable.
    assert minutes_after_start(events[0]) == 60


def test_continuous_cool_down_is_not_an_opening():
    # -0.3 °C every 20 minutes for four hours: a real fall, no slope break.
    assert detect_window_openings(series((240, -0.9)), DROP) == []


def test_a_fast_rise_that_flattens_fires():
    # The rule is the slope break alone, with no floor on the fall itself: a
    # room that was warming 0.8 °C per 20 min and stops counts. Asserted so the
    # behaviour is recorded rather than discovered from a chart.
    events = detect_window_openings(series((60, 2.4), (60, 0.0)), DROP)
    assert len(events) == 1


def test_a_long_airing_is_still_one_marker():
    # An hour with the window open keeps satisfying the test; one marker.
    points = series((60, 0.0), (60, -4.5), (60, 4.5))
    assert len(detect_window_openings(points, DROP)) == 1


def test_two_openings_hours_apart_are_both_marked():
    points = series(
        (60, 0.0), (20, -4.5), (180, 0.0), (20, -4.5), (60, 0.0)
    )
    events = detect_window_openings(points, DROP)
    assert [minutes_after_start(ts) for ts in events] == [60, 260]


def test_a_gap_across_the_lookback_marks_nothing():
    # The sensor goes quiet over the fall and comes back colder. Without rows in
    # between there is no slope to compare, so the step is left unmarked.
    points = [(T0 + i * 60, 21.0) for i in range(60)]
    points += [(T0 + 120 * 60 + i * 60, 19.0) for i in range(60)]
    assert detect_window_openings(points, DROP) == []


def test_the_threshold_is_the_boundary():
    # 0.59 °C steeper over the window, then 0.61 °C steeper.
    below = series((60, 0.0), (20, -0.59 * 3), (60, 0.0))
    above = series((60, 0.0), (20, -0.61 * 3), (60, 0.0))
    assert detect_window_openings(below, DROP) == []
    assert len(detect_window_openings(above, DROP)) == 1


def test_a_second_opening_inside_the_cooldown_is_swallowed():
    # Two falls with a short flat between: the debounce keeps the first only.
    points = series((60, 0.0), (20, -4.5), (10, 0.0), (20, -4.5), (60, 0.0))
    events = detect_window_openings(points, DROP)
    assert len(events) == 1
    assert minutes_after_start(events[0]) == 60


def test_cooldown_and_window_are_the_documented_lengths():
    assert WINDOW_SECONDS == 20 * 60
    assert COOLDOWN_SECONDS == 40 * 60
