import os
from collections.abc import AsyncGenerator

import aiosqlite

from app.core.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    quantity REAL,
    unit TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    custom_name TEXT,
    notes TEXT DEFAULT '',
    attendants INTEGER DEFAULT 2
);

CREATE TABLE IF NOT EXISTS shopping_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    quantity REAL,
    unit TEXT DEFAULT '',
    store TEXT DEFAULT '',
    source_recipe_id INTEGER,
    source_meal_id INTEGER REFERENCES meals(id) ON DELETE CASCADE,
    is_manual INTEGER DEFAULT 0,
    added_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    all_day INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    source_uid TEXT UNIQUE,
    color TEXT DEFAULT '#534AB7',
    notes TEXT DEFAULT ''
);
"""


async def init_db() -> None:
    os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        db.row_factory = aiosqlite.Row
        yield db
