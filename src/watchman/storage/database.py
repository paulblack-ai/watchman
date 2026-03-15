"""SQLite database initialization and connection management."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite


async def migrate_phase2(db_path: Path) -> None:
    """Apply Phase 2 schema migration: add score and review columns to cards.

    This migration is idempotent — running it multiple times is safe.
    Each ALTER TABLE is wrapped in try/except to handle duplicate column errors.

    Args:
        db_path: Path to the SQLite database file.
    """
    new_columns = [
        "ALTER TABLE cards ADD COLUMN relevance_score REAL",
        "ALTER TABLE cards ADD COLUMN score_breakdown TEXT",
        "ALTER TABLE cards ADD COLUMN top_dimension TEXT",
        "ALTER TABLE cards ADD COLUMN review_state TEXT DEFAULT 'pending' CHECK(review_state IN ('pending', 'approved', 'rejected', 'snoozed'))",
        "ALTER TABLE cards ADD COLUMN reviewed_at TEXT",
        "ALTER TABLE cards ADD COLUMN snooze_until TEXT",
        "ALTER TABLE cards ADD COLUMN slack_message_ts TEXT",
        "ALTER TABLE cards ADD COLUMN slack_channel_id TEXT",
    ]

    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cards_review_state ON cards(review_state)",
        "CREATE INDEX IF NOT EXISTS idx_cards_snooze_until ON cards(snooze_until)",
    ]

    async with aiosqlite.connect(str(db_path)) as db:
        for statement in new_columns:
            try:
                await db.execute(statement)
            except Exception:
                # Column already exists — migration is idempotent
                pass

        for statement in new_indexes:
            await db.execute(statement)

        await db.commit()


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

    # Apply Phase 2 schema migration (idempotent)
    await migrate_phase2(db_path)

    # Apply Phase 3 schema migration (idempotent)
    await migrate_phase3(db_path)

    # Apply Phase 4 schema migration (idempotent)
    await migrate_phase4(db_path)

    # Apply Notion schema migration (idempotent)
    await migrate_notion(db_path)


async def migrate_phase3(db_path: Path) -> None:
    """Apply Phase 3 schema migration: add enrichment columns to cards.

    This migration is idempotent -- running it multiple times is safe.
    Each ALTER TABLE is wrapped in try/except to handle duplicate column errors.

    Args:
        db_path: Path to the SQLite database file.
    """
    new_columns = [
        "ALTER TABLE cards ADD COLUMN enrichment_state TEXT DEFAULT 'pending' CHECK(enrichment_state IN ('pending', 'in_progress', 'complete', 'failed', 'skipped'))",
        "ALTER TABLE cards ADD COLUMN enrichment_data TEXT",
        "ALTER TABLE cards ADD COLUMN enrichment_error TEXT",
        "ALTER TABLE cards ADD COLUMN enriched_at TEXT",
    ]

    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cards_enrichment_state ON cards(enrichment_state)",
    ]

    async with aiosqlite.connect(str(db_path)) as db:
        for statement in new_columns:
            try:
                await db.execute(statement)
            except Exception:
                # Column already exists -- migration is idempotent
                pass

        for statement in new_indexes:
            await db.execute(statement)

        await db.commit()


async def migrate_phase4(db_path: Path) -> None:
    """Apply Phase 4 schema migration: add Gate 2 and output columns to cards.

    This migration is idempotent -- running it multiple times is safe.
    Each ALTER TABLE is wrapped in try/except to handle duplicate column errors.

    Args:
        db_path: Path to the SQLite database file.
    """
    new_columns = [
        "ALTER TABLE cards ADD COLUMN gate2_state TEXT DEFAULT 'pending' CHECK(gate2_state IN ('pending', 'gate2_approved', 'gate2_rejected'))",
        "ALTER TABLE cards ADD COLUMN gate2_reviewed_at TEXT",
        "ALTER TABLE cards ADD COLUMN gate2_slack_ts TEXT",
        "ALTER TABLE cards ADD COLUMN enrichment_attempt_count INTEGER DEFAULT 1",
        "ALTER TABLE cards ADD COLUMN output_path TEXT",
    ]

    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cards_gate2_state ON cards(gate2_state)",
    ]

    async with aiosqlite.connect(str(db_path)) as db:
        for statement in new_columns:
            try:
                await db.execute(statement)
            except Exception:
                # Column already exists -- migration is idempotent
                pass

        for statement in new_indexes:
            await db.execute(statement)

        await db.commit()


async def migrate_notion(db_path: Path) -> None:
    """Apply Notion schema migration: add notion_page_id column to cards.

    This migration is idempotent -- running it multiple times is safe.
    The ALTER TABLE is wrapped in try/except to handle duplicate column errors.

    Args:
        db_path: Path to the SQLite database file.
    """
    new_columns = [
        "ALTER TABLE cards ADD COLUMN notion_page_id TEXT",
    ]

    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_cards_notion_page_id ON cards(notion_page_id)",
    ]

    async with aiosqlite.connect(str(db_path)) as db:
        for statement in new_columns:
            try:
                await db.execute(statement)
            except Exception:
                # Column already exists -- migration is idempotent
                pass

        for statement in new_indexes:
            await db.execute(statement)

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
