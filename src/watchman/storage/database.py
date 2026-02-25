"""SQLite database initialization and connection management."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite


async def init_db(db_path: Path) -> None:
    """Initialize the SQLite database with all tables and indexes.

    Creates the database file if it doesn't exist, enables WAL mode
    for concurrent read/write, and creates all required tables.

    Args:
        db_path: Path to the SQLite database file.
    """
    async with aiosqlite.connect(str(db_path)) as db:
        # Enable WAL mode for concurrent read/write
        await db.execute("PRAGMA journal_mode=WAL")

        # Create raw_items table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS raw_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                collector_type TEXT NOT NULL,
                title TEXT,
                url TEXT,
                summary TEXT,
                published_date TEXT,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
                raw_data TEXT,
                processed INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Create cards table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_name TEXT NOT NULL,
                date TEXT NOT NULL,
                url TEXT NOT NULL,
                tier INTEGER NOT NULL CHECK(tier IN (1, 2, 3)),
                summary TEXT,
                collector_type TEXT NOT NULL,
                url_hash TEXT NOT NULL UNIQUE,
                content_fingerprint TEXT,
                duplicate_of INTEGER REFERENCES cards(id),
                seen_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Create source_health table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS source_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                run_at TEXT NOT NULL DEFAULT (datetime('now')),
                items_found INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                consecutive_zeros INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Create indexes
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_url_hash ON cards(url_hash)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_date ON cards(date)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_created_at ON cards(created_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_raw_items_processed ON raw_items(processed)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_health_name ON source_health(source_name)"
        )

        await db.commit()


@asynccontextmanager
async def get_connection(db_path: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Get an async SQLite connection with row_factory configured.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        aiosqlite.Connection with row_factory set to sqlite3.Row.
    """
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
