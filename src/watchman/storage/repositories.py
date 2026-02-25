"""Repository classes for database CRUD operations.

All queries use parameterized statements to prevent SQL injection.
"""

from datetime import datetime, timedelta, timezone

import aiosqlite

from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.models.raw_item import RawItem
from watchman.models.signal_card import SignalCard
from watchman.scoring.models import RubricScore


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

    async def save_score(self, card_id: int, score: RubricScore) -> None:
        """Persist a rubric score for a signal card.

        Args:
            card_id: ID of the card to update.
            score: RubricScore with composite score, per-dimension scores, and top dimension.
        """
        await self.db.execute(
            """UPDATE cards
               SET relevance_score = ?,
                   score_breakdown = ?,
                   top_dimension = ?
               WHERE id = ?""",
            (
                score.composite_score,
                score.model_dump_json(),
                score.top_dimension,
                card_id,
            ),
        )
        await self.db.commit()

    async def find_unscored(self) -> list[SignalCard]:
        """Find all non-duplicate cards that have not been scored yet.

        Returns:
            List of SignalCard instances without a relevance_score.
        """
        async with self.db.execute(
            """SELECT * FROM cards
               WHERE relevance_score IS NULL
               AND duplicate_of IS NULL
               ORDER BY created_at ASC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_card(row) for row in rows]

    async def find_top_scored_today(self, limit: int) -> list[SignalCard]:
        """Find the top-scored pending cards for today's review digest.

        Includes:
        - Cards created today with pending review state and a score
        - Snoozed cards whose snooze_until has passed

        Results are ordered by relevance_score DESC, tier ASC (lower tier = higher quality).

        Args:
            limit: Maximum number of cards to return.

        Returns:
            List of SignalCard instances ordered by score.
        """
        async with self.db.execute(
            """SELECT * FROM cards
               WHERE relevance_score IS NOT NULL
               AND (
                   (review_state = 'pending'
                    AND date(created_at) = date('now'))
                   OR
                   (review_state = 'snoozed'
                    AND snooze_until <= datetime('now'))
               )
               ORDER BY relevance_score DESC, tier ASC
               LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_card(row) for row in rows]

    async def count_scored_today(self) -> int:
        """Count all scored cards created today.

        Used for the "Showing X of Y" footer in the digest.

        Returns:
            Count of scored cards from today.
        """
        async with self.db.execute(
            """SELECT COUNT(*) FROM cards
               WHERE relevance_score IS NOT NULL
               AND date(created_at) = date('now')"""
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def set_review_state(
        self,
        card_id: int,
        state: str,
        slack_ts: str | None = None,
        slack_channel: str | None = None,
    ) -> None:
        """Update the review state of a card.

        Args:
            card_id: ID of the card to update.
            state: New review state (pending/approved/rejected/snoozed).
            slack_ts: Slack message timestamp, if applicable.
            slack_channel: Slack channel ID, if applicable.
        """
        await self.db.execute(
            """UPDATE cards
               SET review_state = ?,
                   reviewed_at = datetime('now'),
                   slack_message_ts = COALESCE(?, slack_message_ts),
                   slack_channel_id = COALESCE(?, slack_channel_id)
               WHERE id = ?""",
            (state, slack_ts, slack_channel, card_id),
        )
        await self.db.commit()

    async def find_approved_unenriched(self) -> list[SignalCard]:
        """Find all approved cards that have not been enriched yet.

        Returns:
            List of SignalCard instances with review_state='approved'
            and enrichment_state='pending'.
        """
        async with self.db.execute(
            """SELECT * FROM cards
               WHERE review_state = 'approved'
               AND enrichment_state = 'pending'
               ORDER BY reviewed_at ASC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_card(row) for row in rows]

    async def save_enrichment(self, card_id: int, entry: IcebreakerToolEntry) -> None:
        """Persist a successful enrichment result for a card.

        Args:
            card_id: ID of the card to update.
            entry: Validated IcebreakerToolEntry with extracted tool data.
        """
        await self.db.execute(
            """UPDATE cards
               SET enrichment_state = 'complete',
                   enrichment_data = ?,
                   enriched_at = datetime('now')
               WHERE id = ?""",
            (entry.model_dump_json(), card_id),
        )
        await self.db.commit()

    async def save_enrichment_error(self, card_id: int, error: str) -> None:
        """Record an enrichment failure for a card.

        Args:
            card_id: ID of the card to update.
            error: Error message describing the failure.
        """
        await self.db.execute(
            """UPDATE cards
               SET enrichment_state = 'failed',
                   enrichment_error = ?
               WHERE id = ?""",
            (error, card_id),
        )
        await self.db.commit()

    async def set_enrichment_state(self, card_id: int, state: str) -> None:
        """Update the enrichment state of a card.

        Args:
            card_id: ID of the card to update.
            state: New enrichment state (pending/in_progress/complete/failed/skipped).
        """
        await self.db.execute(
            "UPDATE cards SET enrichment_state = ? WHERE id = ?",
            (state, card_id),
        )
        await self.db.commit()

    async def snooze_card(self, card_id: int, days: int = 30) -> None:
        """Snooze a card for a given number of days.

        Sets review_state to 'snoozed' and snooze_until to now + days.

        Args:
            card_id: ID of the card to snooze.
            days: Number of days to snooze for (default 30).
        """
        snooze_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        await self.db.execute(
            """UPDATE cards
               SET review_state = 'snoozed',
                   snooze_until = ?
               WHERE id = ?""",
            (snooze_until, card_id),
        )
        await self.db.commit()

    @staticmethod
    def _row_to_card(row: aiosqlite.Row) -> SignalCard:
        """Convert a database row to a SignalCard instance.

        Handles both old rows (missing Phase 2 columns) and new rows gracefully.
        """
        # Helper to safely get optional columns
        def safe_get(key: str, default=None):
            try:
                return row[key]
            except (IndexError, KeyError):
                return default

        reviewed_at_raw = safe_get("reviewed_at")
        snooze_until_raw = safe_get("snooze_until")
        enriched_at_raw = safe_get("enriched_at")

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
            # Phase 2 fields
            relevance_score=safe_get("relevance_score"),
            score_breakdown=safe_get("score_breakdown"),
            top_dimension=safe_get("top_dimension"),
            review_state=safe_get("review_state") or "pending",
            reviewed_at=(
                datetime.fromisoformat(reviewed_at_raw) if reviewed_at_raw else None
            ),
            snooze_until=(
                datetime.fromisoformat(snooze_until_raw) if snooze_until_raw else None
            ),
            slack_message_ts=safe_get("slack_message_ts"),
            slack_channel_id=safe_get("slack_channel_id"),
            # Phase 3 fields
            enrichment_state=safe_get("enrichment_state") or "pending",
            enrichment_data=safe_get("enrichment_data"),
            enrichment_error=safe_get("enrichment_error"),
            enriched_at=(
                datetime.fromisoformat(enriched_at_raw) if enriched_at_raw else None
            ),
            # Phase 4 fields
            gate2_state=safe_get("gate2_state") or "pending",
            gate2_reviewed_at=(
                datetime.fromisoformat(safe_get("gate2_reviewed_at"))
                if safe_get("gate2_reviewed_at")
                else None
            ),
            gate2_slack_ts=safe_get("gate2_slack_ts"),
            enrichment_attempt_count=safe_get("enrichment_attempt_count") or 1,
            output_path=safe_get("output_path"),
        )


    async def set_gate2_state(
        self, card_id: int, state: str, slack_ts: str | None = None
    ) -> None:
        """Update the Gate 2 review state of a card.

        Args:
            card_id: ID of the card to update.
            state: New Gate 2 state (pending/gate2_approved/gate2_rejected).
            slack_ts: Slack message timestamp, if applicable.
        """
        await self.db.execute(
            """UPDATE cards
               SET gate2_state = ?,
                   gate2_reviewed_at = datetime('now'),
                   gate2_slack_ts = COALESCE(?, gate2_slack_ts)
               WHERE id = ?""",
            (state, slack_ts, card_id),
        )
        await self.db.commit()

    async def save_output_path(self, card_id: int, path: str) -> None:
        """Record the output file path for a Gate 2 approved card.

        Args:
            card_id: ID of the card to update.
            path: File path of the written JSON output.
        """
        await self.db.execute(
            "UPDATE cards SET output_path = ? WHERE id = ?",
            (path, card_id),
        )
        await self.db.commit()

    async def increment_enrichment_attempt(self, card_id: int) -> int:
        """Increment and return the enrichment attempt count for a card.

        Args:
            card_id: ID of the card to update.

        Returns:
            Updated enrichment attempt count.
        """
        await self.db.execute(
            "UPDATE cards SET enrichment_attempt_count = enrichment_attempt_count + 1 WHERE id = ?",
            (card_id,),
        )
        await self.db.commit()
        async with self.db.execute(
            "SELECT enrichment_attempt_count FROM cards WHERE id = ?", (card_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def find_enriched_pending_gate2(self) -> list[SignalCard]:
        """Find cards with enrichment complete but not yet reviewed at Gate 2.

        Returns:
            List of SignalCard instances pending Gate 2 review.
        """
        async with self.db.execute(
            """SELECT * FROM cards
               WHERE enrichment_state = 'complete'
               AND gate2_state = 'pending'
               ORDER BY enriched_at ASC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_card(row) for row in rows]


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
