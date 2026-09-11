"""Finds window openings in a temperature series.

An opened window shows up as a break in the slope, not merely as a fall: the
evening cool-down and the sun leaving a window are continuous, so they move the
temperature without changing how fast it moves. Comparing the last twenty
minutes against the twenty before them separates the two, with no second sensor
and nothing to store.
"""

# The comparison window. Part of the definition of an opening rather than a
# knob: shorter and a draught from cooking qualifies, longer and a short airing
# is averaged away.
WINDOW_SECONDS = 20 * 60

# One airing is one marker, however long the window stays open.
COOLDOWN_SECONDS = 40 * 60

# How far a lookback may miss the moment it wants. Samples land once a minute at
# the advertisement time, so a couple of missed broadcasts are still usable and
# a real gap is not.
TOLERANCE_SECONDS = 180


def _value_at(points: list[tuple[int, float]], index: int, target: int) -> float | None:
    """Value nearest to target, given index is the last sample at or before it.

    None when the nearest sample is further off than the tolerance, i.e. the
    series has a hole where the comparison wants to look.
    """
    best = points[index]
    if index + 1 < len(points) and abs(points[index + 1][0] - target) < abs(best[0] - target):
        best = points[index + 1]
    return best[1] if abs(best[0] - target) <= TOLERANCE_SECONDS else None


def _knee(points: list[tuple[int, float]], index: int, since: int) -> int:
    """When the fall being detected at index started.

    The test only trips once enough of the fall sits inside the window, so the
    tripping sample is some minutes late and the window's own left edge is some
    minutes early. The warmest sample in between is the corner of the curve, and
    the last one at that value is where the descent leaves it.
    """
    at = index
    while index >= 0 and points[index][0] >= since:
        if points[index][1] > points[at][1]:
            at = index
        index -= 1
    return points[at][0]


def detect_window_openings(points: list[tuple[int, float]], drop: float) -> list[int]:
    """Timestamps where a window looks to have been opened, ascending.

    points must be ascending by time. A sample fires when the fall over the last
    WINDOW_SECONDS is at least `drop` steeper than over the WINDOW_SECONDS
    before it. Each event is stamped where the curve turns, so the marker sits
    on the corner rather than somewhere down the slope.
    """
    events: list[int] = []
    # One trailing index per lookback. Both only ever move forward, so the whole
    # scan stays linear instead of searching per sample.
    mid = prev = 0
    firing = False
    last_hit: int | None = None

    for i, (ts, value) in enumerate(points):
        while mid + 1 < len(points) and points[mid + 1][0] <= ts - WINDOW_SECONDS:
            mid += 1
        while prev + 1 < len(points) and points[prev + 1][0] <= ts - 2 * WINDOW_SECONDS:
            prev += 1

        v_mid = _value_at(points, mid, ts - WINDOW_SECONDS)
        v_prev = _value_at(points, prev, ts - 2 * WINDOW_SECONDS)
        if v_mid is None or v_prev is None:
            # A hole over either lookback: nothing to compare, and the run ends
            # rather than carrying across the gap.
            firing = False
            continue

        hit = (value - v_mid) - (v_mid - v_prev) <= -drop
        if hit and not firing and (last_hit is None or ts - last_hit >= COOLDOWN_SECONDS):
            events.append(_knee(points, i, ts - WINDOW_SECONDS))
        # Measured from the end of the last firing run, not its start, so a
        # window that stays open through a pause in the fall is still one event.
        if hit:
            last_hit = ts
        firing = hit

    return events
