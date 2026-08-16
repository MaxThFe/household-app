"""Sensor history store.

A second SQLite file, separate from the app database: it takes a write every
sample interval and is tuned for that, and its raw rows are meant to stay
queryable with sqlite3 outside the app.
"""

import os
from collections.abc import AsyncGenerator

import aiosqlite

from app.core.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS series (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    room   TEXT NOT NULL,
    metric TEXT NOT NULL,
    unit   TEXT NOT NULL DEFAULT '',
    UNIQUE(room, metric)
);

-- WITHOUT ROWID with this primary key clusters the rows, so reading one series
-- over a time range is a contiguous scan and needs no secondary index.
CREATE TABLE IF NOT EXISTS readings (
    series_id INTEGER NOT NULL REFERENCES series(id),
    ts        INTEGER NOT NULL,   -- unix epoch seconds, UTC
    value     REAL    NOT NULL,
    PRIMARY KEY (series_id, ts)
) WITHOUT ROWID;
"""


async def init_timeseries_db() -> None:
    os.makedirs(os.path.dirname(settings.timeseries_path) or ".", exist_ok=True)
    async with aiosqlite.connect(settings.timeseries_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.execute("PRAGMA journal_mode=WAL")
        # Safe under WAL, and far fewer fsyncs on the Pi's SD card.
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.commit()


async def connect() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.timeseries_path)
    await db.execute("PRAGMA synchronous=NORMAL")
    db.row_factory = aiosqlite.Row
    return db


async def get_timeseries_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    db = await connect()
    try:
        yield db
    finally:
        await db.close()
