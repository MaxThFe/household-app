import os
from collections.abc import AsyncGenerator

import aiosqlite

from app.core.config import settings

SCHEMA_SQL = """
-- Houseplants feature was removed; drop the leftover table.
-- Safe to delete this statement once it has run in production.
DROP TABLE IF EXISTS houseplants;

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

-- Per-supermarket aisle order for the shopping list sections
CREATE TABLE IF NOT EXISTS shopping_section_order (
    market TEXT NOT NULL,
    section TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (market, section)
);

-- Household to-do board. No due dates: a one-off sits on the board until it is
-- ticked off (and is then deleted), a recurring chore goes quiet until
-- next_due comes round. next_due is internal bookkeeping only — null means the
-- task is wanted now, which is also how every task starts out.
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    recur_unit TEXT,
    recur_every INTEGER NOT NULL DEFAULT 1,
    next_due TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Shopping item -> Picnic product, worked out once by the LLM (or picked by
-- hand) and then reused. item_key is the lowercased item name; recipe_id 0 is
-- the mapping for every recipe, any other id overrides it for that recipe.
-- The product is a specific pack (500 g or 1 kg); quantities count packs.
CREATE TABLE IF NOT EXISTS picnic_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT NOT NULL,
    recipe_id INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    product_id TEXT,
    product_name TEXT,
    unit_quantity TEXT DEFAULT '',
    price INTEGER,
    image_id TEXT,
    source TEXT DEFAULT 'llm',
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE (item_key, recipe_id)
);

-- What the LLM could not decide on its own. candidates is a JSON list of
-- product cards to pick from; an answered question is kept as context for
-- the next attempt at that item.
CREATE TABLE IF NOT EXISTS picnic_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT NOT NULL,
    recipe_id INTEGER NOT NULL DEFAULT 0,
    recipe_names TEXT DEFAULT '',
    question TEXT NOT NULL,
    candidates TEXT DEFAULT '[]',
    answer TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vacuum_overrides (
    date TEXT PRIMARY KEY,
    clean_time TEXT,
    deleted INTEGER DEFAULT 0
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
