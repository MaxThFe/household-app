"""Tests for the sensor history store: sampling rules and range queries."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core import timeseries
from app.core.config import settings
from app.services import sensor_history
from app.services.sensor_history import fetch_history, sample_once, series_id

T0 = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def seen_at(minutes: int) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat(timespec="seconds")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "sensors.db")
    monkeypatch.setattr(settings, "timeseries_path", path)
    return path


@pytest.fixture
def readings(monkeypatch):
    """Swap the live BLE readings for a list the test controls."""
    box: list[dict] = []
    monkeypatch.setattr(sensor_history, "get_readings", lambda: box)
    return box


def reading(room="Kitchen", *, temperature=21.0, humidity=45.0, last_seen=None, stale=False):
    last_seen = seen_at(0) if last_seen is None else last_seen
    return {
        "room": room,
        "temperature": temperature,
        "humidity": humidity,
        "last_seen": last_seen,
        "stale": stale,
    }


async def count_rows(db) -> int:
    async with db.execute("SELECT COUNT(*) AS n FROM readings") as cur:
        return (await cur.fetchone())["n"]


@pytest.mark.asyncio
async def test_series_upsert_is_idempotent(db_path):
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        first = await series_id(db, "Kitchen", "temperature")
        assert await series_id(db, "Kitchen", "temperature") == first
        assert await series_id(db, "Kitchen", "humidity") != first
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sample_writes_one_row_per_metric(db_path, readings):
    readings.append(reading())
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        assert await sample_once(db) == 2  # temperature + humidity
        assert await count_rows(db) == 2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sample_skips_stale_readings(db_path, readings):
    readings.append(reading(stale=True))
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        assert await sample_once(db) == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sample_skips_unchanged_last_seen(db_path, readings):
    readings.append(reading(last_seen=seen_at(0)))
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        assert await sample_once(db) == 2
        # Sensor has gone quiet: same advertisement time, so the primary key
        # collides and nothing new is recorded.
        assert await sample_once(db) == 0

        readings[0] = reading(last_seen=seen_at(1), temperature=22.0)
        assert await sample_once(db) == 2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sample_uses_advertisement_time_not_poll_time(db_path, readings):
    readings.append(reading(last_seen=seen_at(0)))
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        await sample_once(db)
        async with db.execute("SELECT DISTINCT ts FROM readings") as cur:
            stamps = [r["ts"] for r in await cur.fetchall()]
        assert stamps == [int(T0.timestamp())]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_short_range_returns_raw_points(db_path):
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        sid = await series_id(db, "Kitchen", "temperature")
        await db.executemany(
            "INSERT INTO readings (series_id, ts, value) VALUES (?, ?, ?)",
            [(sid, 1000 + i * 60, 20.0 + i) for i in range(100)],
        )
        await db.commit()

        result = await fetch_history(db, "Kitchen", "temperature", 0, 10_000, max_points=500)
        assert result["bucketed"] is False
        assert len(result["points"]) == 100
        assert result["points"][0] == [1000, 20.0]
        assert result["unit"] == "°C"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_long_range_buckets_within_max_points(db_path):
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        sid = await series_id(db, "Kitchen", "temperature")
        await db.executemany(
            "INSERT INTO readings (series_id, ts, value) VALUES (?, ?, ?)",
            [(sid, i * 60, 20.0) for i in range(2000)],
        )
        await db.commit()

        result = await fetch_history(db, "Kitchen", "temperature", 0, 120_000, max_points=100)
        assert result["bucketed"] is True
        assert len(result["points"]) <= 100
        # Averaging a constant series must not shift the value.
        assert all(value == 20.0 for _, value in result["points"])

        # The raw rows are untouched by a bucketed read.
        assert await count_rows(db) == 2000
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_unknown_series_returns_empty(db_path):
    await timeseries.init_timeseries_db()
    db = await timeseries.connect()
    try:
        result = await fetch_history(db, "Nowhere", "temperature", 0, 10_000)
        assert result["points"] == []
    finally:
        await db.close()
