"""Abstract base collector and factory registry."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from watchman.models.raw_item import RawItem
from watchman.models.source import SourceConfig
from watchman.storage.database import get_connection
from watchman.storage.repositories import RawItemRepository

logger = logging.getLogger(__name__)

COLLECTOR_REGISTRY: dict[str, type["BaseCollector"]] = {}


def register_collector(source_type: str):
    """Decorator to register a collector class for a source type.

    Args:
        source_type: The source type string (e.g., 'rss', 'api', 'scrape').
    """

    def decorator(cls: type["BaseCollector"]) -> type["BaseCollector"]:
        COLLECTOR_REGISTRY[source_type] = cls
        return cls

    return decorator


def get_collector(source: SourceConfig, db_path: Path) -> "BaseCollector":
    """Factory function to create the correct collector for a source.

    Args:
        source: Source configuration.
        db_path: Path to the SQLite database.

    Returns:
        An instance of the appropriate collector.

    Raises:
        ValueError: If no collector is registered for the source type.
    """
    collector_cls = COLLECTOR_REGISTRY.get(source.type)
    if not collector_cls:
        raise ValueError(f"No collector registered for type: {source.type}")
    return collector_cls(source, db_path)


class BaseCollector(ABC):
    """Abstract base class for all signal collectors.

    Each collector fetches data from a specific source type and
    produces RawItem instances for storage in the database.
    """

    def __init__(self, source: SourceConfig, db_path: Path) -> None:
        self.source = source
        self.db_path = db_path

    @abstractmethod
    async def collect(self) -> list[RawItem]:
        """Fetch raw items from the source.

        Returns:
            List of RawItem instances from this collection run.
        """
        ...

    async def run(self, max_age_days: int | None = None) -> int:
        """Execute collection: fetch items, optionally filter by age, write to database, return count.

        Args:
            max_age_days: If provided, filter out items older than this many days.

        Returns:
            Number of items written to the database.
        """
        try:
            items = await self.collect()
            if not items:
                logger.info(
                    "Source '%s' returned 0 items", self.source.name
                )
                return 0

            # Filter by age if specified
            if max_age_days is not None:
                from datetime import datetime, timedelta, timezone

                cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
                original_count = len(items)
                items = [
                    item for item in items
                    if item.published_date
                    and item.published_date.replace(
                        tzinfo=timezone.utc if item.published_date.tzinfo is None else item.published_date.tzinfo
                    ) >= cutoff
                ]
                filtered = original_count - len(items)
                if filtered > 0:
                    logger.info(
                        "Source '%s': filtered %d items older than %d days (%d remaining)",
                        self.source.name, filtered, max_age_days, len(items),
                    )
                if not items:
                    return 0

            async with get_connection(self.db_path) as db:
                repo = RawItemRepository(db)
                for item in items:
                    await repo.insert(item)

            logger.info(
                "Source '%s' collected %d items", self.source.name, len(items)
            )
            return len(items)

        except Exception:
            logger.exception(
                "Error collecting from source '%s'", self.source.name
            )
            return 0
