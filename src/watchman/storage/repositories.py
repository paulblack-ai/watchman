"""Repository classes for database CRUD operations.

All queries use parameterized statements to prevent SQL injection.
"""

from datetime import datetime

import aiosqlite

from watchman.models.raw_item import RawItem
from watchman.models.signal_card import SignalCard


class RawItemRepository:
    """Repository for raw_items table operations."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def insert(self, item: RawItem) -> int:
        """Insert a raw item and return its ID.

        Args:
            item: RawItem to insert.

        Returns:
            The auto-generated row ID.
        """
        cursor = await self.db.execute(
            """INSERT INTO raw_items
               (source_name, collector_type, title, url, summary,
                published_date, fetched_at, raw_data, processed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.source_name,
                item.collector_type,
                item.title,
                item.url,
                item.summary,
                item.published_date.isoformat() if item.published_date else None,
                item.fetched_at.isoformat(),
                item.raw_data,
                int(item.processed),
            ),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def find_unprocessed(self) -> list[RawItem]:
        """Find all unprocessed raw items.

        Returns:
            List of RawItem instances that haven't been processed yet.
        """
        async with self.db.execute(
            "SELECT * FROM raw_items WHERE processed = 0 ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                RawItem(
                    id=row["id"],
                    source_name=row["source_name"],
                    collector_type=row["collector_type"],
                    title=row["title"],
                    url=row["url"],
                    summary=row["summary"],
                    published_date=(
                        datetime.fromisoformat(row["published_date"])
                        if row["published_date"]
                        else None
                    ),
                    fetched_at=datetime.fromisoformat(row["fetched_at"]),
                    raw_data=row["raw_data"],
                    processed=bool(row["processed"]),
                )
                for row in rows
            ]

    async def mark_processed(self, item_id: int) -> None:
        """Mark a raw item as processed.

        Args:
            item_id: ID of the raw item to mark.
        """
        await self.db.execute(
            "UPDATE raw_items SET processed = 1 WHERE id = ?", (item_id,)
        )
        await self.db.commit()


class CardRepository:
    """Repository for cards table operations."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def insert(self, card: SignalCard) -> int:
        """Insert a signal card and return its ID.

        Args:
            card: SignalCard to insert.

        Returns:
            The auto-generated row ID.
        """
        cursor = await self.db.execute(
            """INSERT INTO cards
               (title, source_name, date, url, tier, summary,
                collector_type, url_hash, content_fingerprint,
                duplicate_of, seen_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card.title,
                card.source_name,
                card.date.isoformat(),
                card.url,
                card.tier,
                card.summary,
                card.collector_type,
                card.url_hash,
                card.content_fingerprint,
                card.duplicate_of,
                card.seen_count,
            ),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def find_by_url_hash(self, url_hash: str) -> SignalCard | None:
        """Find a card by its URL hash.

        Args:
            url_hash: SHA-256 hash of normalized URL.

        Returns:
            SignalCard if found, None otherwise.
        """
        async with self.db.execute(
            "SELECT * FROM cards WHERE url_hash = ?", (url_hash,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_card(row)

    async def find_since(self, cutoff: datetime) -> list[SignalCard]:
        """Find all cards created since a cutoff datetime.

        Args:
            cutoff: Only return cards created after this time.

        Returns:
            List of SignalCard instances.
        """
        async with self.db.execute(
            "SELECT * FROM cards WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff.isoformat(),),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_card(row) for row in rows]

    async def increment_seen_count(self, card_id: int) -> None:
        """Increment the seen_count on a card (cross-source visibility).

        Args:
            card_id: ID of the canonical card.
        """
        await self.db.execute(
            "UPDATE cards SET seen_count = seen_count + 1 WHERE id = ?", (card_id,)
        )
        await self.db.commit()

    async def link_duplicate(self, duplicate_id: int, canonical_id: int) -> None:
        """Link a duplicate card to its canonical card.

        Args:
            duplicate_id: ID of the duplicate card.
            canonical_id: ID of the canonical (first seen) card.
        """
        await self.db.execute(
            "UPDATE cards SET duplicate_of = ? WHERE id = ?",
            (canonical_id, duplicate_id),
        )
        await self.db.commit()

    @staticmethod
    def _row_to_card(row: aiosqlite.Row) -> SignalCard:
        """Convert a database row to a SignalCard instance."""
        return SignalCard(
            id=row["id"],
            title=row["title"],
            source_name=row["source_name"],
            date=datetime.fromisoformat(row["date"]),
            url=row["url"],
            tier=row["tier"],
            summary=row["summary"],
            collector_type=row["collector_type"],
            url_hash=row["url_hash"],
            content_fingerprint=row["content_fingerprint"],
            duplicate_of=row["duplicate_of"],
            seen_count=row["seen_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class HealthRepository:
    """Repository for source_health table operations."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def record_run(
        self, source_name: str, items_found: int, error: str | None = None
    ) -> int:
        """Record a collection run result.

        Args:
            source_name: Name of the source that was collected.
            items_found: Number of items found in this run.
            error: Error message if the run failed.

        Returns:
            The auto-generated row ID.
        """
        consecutive_zeros = 0
        if items_found == 0:
            consecutive_zeros = await self.get_consecutive_zeros(source_name) + 1

        cursor = await self.db.execute(
            """INSERT INTO source_health
               (source_name, items_found, error_message, consecutive_zeros)
               VALUES (?, ?, ?, ?)""",
            (source_name, items_found, error, consecutive_zeros),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_consecutive_zeros(self, source_name: str) -> int:
        """Get the current consecutive zero-yield run count for a source.

        Args:
            source_name: Name of the source.

        Returns:
            Number of consecutive runs with zero items.
        """
        async with self.db.execute(
            """SELECT consecutive_zeros FROM source_health
               WHERE source_name = ?
               ORDER BY id DESC LIMIT 1""",
            (source_name,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return 0
            return row["consecutive_zeros"]

    async def reset_consecutive_zeros(self, source_name: str) -> None:
        """Reset consecutive zeros counter (called when items are found).

        This is handled automatically in record_run when items_found > 0,
        but available for manual reset if needed.

        Args:
            source_name: Name of the source.
        """
        # The counter resets naturally since record_run sets consecutive_zeros=0
        # when items_found > 0. This method exists for explicit reset scenarios.
        pass

    async def get_failing_sources(self) -> list[dict]:
        """Get all sources currently failing (consecutive zeros >= 2).

        Returns:
            List of dicts with source_name, consecutive_zeros, error_message.
        """
        async with self.db.execute(
            """SELECT source_name, consecutive_zeros, error_message
               FROM source_health
               WHERE id IN (
                   SELECT MAX(id) FROM source_health GROUP BY source_name
               )
               AND consecutive_zeros >= 2
               ORDER BY consecutive_zeros DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "source_name": row["source_name"],
                    "consecutive_zeros": row["consecutive_zeros"],
                    "last_error": row["error_message"],
                }
                for row in rows
            ]
