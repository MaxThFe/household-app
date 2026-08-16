"""Samples the live BLE readings into the history store, and queries them back.

The sensors advertise every few seconds; we poll the live readings once a minute
instead, so the SD card sees one commit per tick rather than one per
advertisement.
"""

import asyncio
import logging
from datetime import datetime

import aiosqlite

from app.core import timeseries
from app.services.ble_sensors import get_readings, sensor_rooms

logger = logging.getLogger(__name__)

# Metrics we keep history for, and the unit each is reported in.
METRICS: dict[str, str] = {"temperature": "°C", "humidity": "%"}

# One sample per minute. The chart resolution and the ~60 MB/year on disk are
# both sized around this, so it is a constant rather than a knob.
SAMPLE_INTERVAL_SECONDS = 60

DEFAULT_MAX_POINTS = 500
MAX_POINTS_CEILING = 5000


async def series_id(db: aiosqlite.Connection, room: str, metric: str) -> int:
    """Row id for a (room, metric) pair, inserting it the first time."""
    await db.execute(
        "INSERT OR IGNORE INTO series (room, metric, unit) VALUES (?, ?, ?)",
        (room, metric, METRICS.get(metric, "")),
    )
    async with db.execute(
        "SELECT id FROM series WHERE room = ? AND metric = ?", (room, metric)
    ) as cur:
        row = await cur.fetchone()
    return row["id"]


async def list_series(db: aiosqlite.Connection) -> list[dict]:
    """Series for the currently configured rooms, in configured order.

    The config stays the only place that decides which rooms exist; the table
    just accumulates their history. A room dropped or renamed in .env therefore
    disappears from the app while its old rows stay on disk.
    """
    rooms = list(sensor_rooms().values())
    async with db.execute(
        "SELECT s.room, s.metric, s.unit, "
        "       MIN(r.ts) AS first_ts, MAX(r.ts) AS last_ts "
        "FROM series s LEFT JOIN readings r ON r.series_id = s.id "
        "GROUP BY s.id ORDER BY s.id"
    ) as cur:
        found = [dict(row) for row in await cur.fetchall()]
    return sorted(
        (s for s in found if s["room"] in rooms),
        key=lambda s: rooms.index(s["room"]),
    )


async def sample_once(db: aiosqlite.Connection) -> int:
    """Write one sample per live reading. Returns how many rows were written.

    Rows are stamped with the advertisement time rather than the poll time, so
    re-reading a sensor that has not broadcast since collides with the primary
    key and is ignored. That keeps the dedupe in the schema instead of a second
    copy of per-sensor state, and leaves a real gap when a sensor goes quiet.
    """
    rows: list[tuple[int, int, float]] = []

    for reading in get_readings():
        if reading["stale"] or not reading["last_seen"]:
            continue
        ts = int(datetime.fromisoformat(reading["last_seen"]).timestamp())
        for metric in METRICS:
            value = reading.get(metric)
            if value is None:
                continue
            rows.append((await series_id(db, reading["room"], metric), ts, value))

    written = 0
    if rows:
        cur = await db.executemany(
            "INSERT OR IGNORE INTO readings (series_id, ts, value) VALUES (?, ?, ?)",
            rows,
        )
        written = cur.rowcount
    await db.commit()
    return written


async def fetch_history(
    db: aiosqlite.Connection,
    room: str,
    metric: str,
    start: int,
    end: int,
    max_points: int = DEFAULT_MAX_POINTS,
) -> dict:
    """Points for one series between two epoch seconds.

    Raw rows unless there are more than max_points of them, in which case they
    are averaged into equal time buckets. The raw rows are never modified.
    """
    async with db.execute(
        "SELECT id, unit FROM series WHERE room = ? AND metric = ?", (room, metric)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return {"room": room, "metric": metric, "unit": "", "bucketed": False, "points": []}

    params = {"sid": row["id"], "start": start, "end": end}
    where = "FROM readings WHERE series_id = :sid AND ts >= :start AND ts < :end"

    async with db.execute(f"SELECT COUNT(*) AS n {where}", params) as cur:
        bucketed = (await cur.fetchone())["n"] > max_points

    if bucketed:
        params["b"] = max(1, -(-(end - start) // max_points))
        sql = f"SELECT (ts / :b) * :b AS ts, ROUND(AVG(value), 2) AS value {where} GROUP BY 1 ORDER BY 1"
    else:
        sql = f"SELECT ts, value {where} ORDER BY ts"

    async with db.execute(sql, params) as cur:
        points = [[r["ts"], r["value"]] for r in await cur.fetchall()]

    return {
        "room": room,
        "metric": metric,
        "unit": row["unit"],
        "bucketed": bucketed,
        "points": points,
    }


async def run_sensor_sampler_loop() -> None:
    if not sensor_rooms():
        logger.info("No BLE sensors configured, history sampler disabled")
        return

    while True:
        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)
        try:
            db = await timeseries.connect()
            try:
                await sample_once(db)
            finally:
                await db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Sensor history sample failed")
