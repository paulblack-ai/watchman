"""Per-source health tracking with consecutive zero detection."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from watchman.health.alerter import send_health_alert
from watchman.storage.database import get_connection
from watchman.storage.repositories import HealthRepository

logger = logging.getLogger(__name__)


async def record_collection_result(
    db_path: Path,
    source_name: str,
    source_type: str,
    items_found: int,
    error: str | None = None,
) -> None:
    """Record a collection run result and trigger alerts if needed.

    Args:
        db_path: Path to the SQLite database.
        source_name: Name of the source that was collected.
        source_type: Type of the source (rss/api/scrape).
        items_found: Number of items found in this run.
        error: Error message if the run failed.
    """
    async with get_connection(db_path) as db:
        repo = HealthRepository(db)
        await repo.record_run(source_name, items_found, error)

        if items_found == 0:
            consecutive_zeros = await repo.get_consecutive_zeros(source_name)
            if consecutive_zeros >= 2:
                await check_and_alert(
                    source_name=source_name,
                    source_type=source_type,
                    consecutive_zeros=consecutive_zeros,
                )


async def check_and_alert(
    source_name: str,
    source_type: str,
    consecutive_zeros: int,
) -> None:
    """Check if alert should be sent and send it.

    Per user decision:
    - Alert once on first detection (consecutive_zeros == 2)
    - Subsequent failures roll into daily digest (don't re-alert individually)

    Args:
        source_name: Name of the failing source.
        source_type: Type of the source (rss/api/scrape).
        consecutive_zeros: Current consecutive zero-yield run count.
    """
    token = os.environ.get("SLACK_BOT_TOKEN")
    user_id = os.environ.get("SLACK_PAUL_USER_ID")

    if not token or not user_id:
        logger.warning(
            "Slack credentials not configured, skipping health alert for '%s'",
            source_name,
        )
        return

    # Only send individual alert on first detection (== 2)
    # Subsequent failures go into daily digest
    if consecutive_zeros == 2:
        success = send_health_alert(
            token=token,
            user_id=user_id,
            source_name=source_name,
            source_type=source_type,
            consecutive_zeros=consecutive_zeros,
        )
        if success:
            logger.info("Sent health alert for '%s'", source_name)
        else:
            logger.warning("Failed to send health alert for '%s'", source_name)
    else:
        logger.debug(
            "Source '%s' at %d consecutive zeros (will be in daily digest)",
            source_name,
            consecutive_zeros,
        )


async def get_daily_digest(db_path: Path) -> list[dict]:
    """Get all sources currently failing for the daily digest.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        List of dicts with source_name, consecutive_zeros, last_error.
    """
    async with get_connection(db_path) as db:
        repo = HealthRepository(db)
        return await repo.get_failing_sources()
