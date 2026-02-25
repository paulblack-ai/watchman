"""APScheduler job definitions for automated collection."""

import asyncio
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
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


def run_scoring_job(db_path: Path, rubric_path: Path) -> None:
    """Sync wrapper that runs async scoring via asyncio.run().

    Called by APScheduler's thread pool. Scores all unscored,
    non-duplicate signal cards in the database.

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.
    """
    # Import here to avoid circular imports at module load time
    from watchman.scoring.scorer import score_unscored_cards  # noqa: PLC0415

    try:
        scored = asyncio.run(score_unscored_cards(db_path, rubric_path))
        logger.info("Scoring job complete: %d cards scored", scored)
    except Exception:
        logger.exception("Scoring job failed")


def schedule_scoring_job(
    scheduler: BackgroundScheduler, db_path: Path, rubric_path: Path
) -> None:
    """Register a dedicated 30-minute interval scoring job with the scheduler.

    Args:
        scheduler: The APScheduler BackgroundScheduler to add the job to.
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.
    """
    scheduler.add_job(
        run_scoring_job,
        trigger=IntervalTrigger(minutes=30),
        args=[db_path, rubric_path],
        id="score-unscored-cards",
        replace_existing=True,
    )
    logger.info("Scheduled scoring job every 30 minutes")


def schedule_delivery_job(
    scheduler: BackgroundScheduler, db_path: Path, rubric_path: Path
) -> None:
    """Register a daily 9 AM delivery job with the scheduler.

    The job calls deliver_daily_review_sync which posts the top-scored
    signal cards to the configured Slack channel.

    Args:
        scheduler: The APScheduler BackgroundScheduler to add the job to.
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.
    """
    from watchman.slack.delivery import deliver_daily_review_sync  # noqa: PLC0415

    scheduler.add_job(
        deliver_daily_review_sync,
        trigger=CronTrigger(hour=9, minute=0),
        args=[db_path, rubric_path],
        id="deliver-daily-review",
        replace_existing=True,
    )
    logger.info("Scheduled daily review delivery job at 09:00 AM")


def setup_scheduler(
    sources: list[SourceConfig], db_path: Path, rubric_path: Path | None = None
) -> BackgroundScheduler:
    """Create and configure APScheduler with jobs for each enabled source.

    If rubric_path is provided, also schedules a dedicated 30-minute scoring job.

    Args:
        sources: List of enabled source configurations.
        db_path: Path to the SQLite database.
        rubric_path: Optional path to rubric YAML; if provided, adds scoring job.

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

    if rubric_path is not None:
        schedule_scoring_job(scheduler, db_path, rubric_path)

    return scheduler
