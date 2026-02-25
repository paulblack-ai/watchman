"""APScheduler job definitions for automated collection."""

import asyncio
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from watchman.collectors.base import get_collector
from watchman.config.loader import parse_interval
from watchman.health.tracker import record_collection_result
from watchman.models.source import SourceConfig

logger = logging.getLogger(__name__)


def collect_source(source: SourceConfig, db_path: Path) -> None:
    """Sync wrapper that runs an async collector via asyncio.run().

    Called by APScheduler's thread pool. Gets the correct collector
    via factory, runs it, and records health metrics.

    Args:
        source: Source configuration to collect from.
        db_path: Path to the SQLite database.
    """
    try:
        collector = get_collector(source, db_path)
        items_found = asyncio.run(collector.run())

        # Record health metrics
        asyncio.run(
            record_collection_result(
                db_path=db_path,
                source_name=source.name,
                source_type=source.type,
                items_found=items_found,
            )
        )

    except Exception as e:
        logger.exception("Failed to collect from '%s'", source.name)
        # Record failed run
        asyncio.run(
            record_collection_result(
                db_path=db_path,
                source_name=source.name,
                source_type=source.type,
                items_found=0,
                error=str(e),
            )
        )


def setup_scheduler(
    sources: list[SourceConfig], db_path: Path
) -> BackgroundScheduler:
    """Create and configure APScheduler with jobs for each enabled source.

    Args:
        sources: List of enabled source configurations.
        db_path: Path to the SQLite database.

    Returns:
        Configured BackgroundScheduler (not started).
    """
    scheduler = BackgroundScheduler()

    for source in sources:
        if not source.enabled:
            continue

        interval_kwargs = parse_interval(source.frequency)

        scheduler.add_job(
            collect_source,
            trigger=IntervalTrigger(**interval_kwargs),
            args=[source, db_path],
            id=f"collect-{source.name}",
            replace_existing=True,
        )

        logger.info(
            "Scheduled '%s' (%s) every %s",
            source.name,
            source.type,
            source.frequency,
        )

    return scheduler
