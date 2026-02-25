"""Watchman entry point: loads config, inits DB, starts Slack, and starts scheduler."""

import asyncio
import logging
import os
import time
from pathlib import Path

from watchman.config.loader import get_enabled_sources, load_sources
from watchman.storage.database import init_db


def main() -> None:
    """Start the Watchman signal collection agent.

    Loads source configuration, initializes the database, optionally starts
    the Slack Socket Mode listener (when tokens are configured), sets up the
    scheduler with collection, scoring, and delivery jobs, and runs until
    interrupted with Ctrl+C.

    Graceful degradation: if SLACK_BOT_TOKEN or SLACK_APP_TOKEN are missing,
    Slack features are disabled but all other functionality continues normally.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("watchman")

    # Determine paths
    db_path = Path("watchman.db")
    config_path = Path("src/watchman/config/sources.yaml")
    rubric_path = Path("src/watchman/config/rubric.yaml")

    # Load source registry
    logger.info("Loading source registry from %s", config_path)
    registry = load_sources(config_path)
    enabled_sources = get_enabled_sources(registry)

    # Log tier breakdown
    tier_counts = {1: 0, 2: 0, 3: 0}
    for source in enabled_sources:
        tier_counts[source.tier] += 1

    logger.info(
        "Loaded %d sources (%d enabled): Tier 1=%d, Tier 2=%d, Tier 3=%d",
        len(registry.sources),
        len(enabled_sources),
        tier_counts[1],
        tier_counts[2],
        tier_counts[3],
    )

    # Initialize database
    logger.info("Initializing database at %s", db_path)
    asyncio.run(init_db(db_path))

    # Slack integration (graceful degradation when tokens are missing)
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    slack_app_token = os.environ.get("SLACK_APP_TOKEN")
    slack_enabled = bool(slack_token and slack_app_token)

    if slack_enabled:
        # Import here to avoid import-time side effects when Slack is not configured
        from watchman.slack.app import create_slack_app, start_socket_mode  # noqa: PLC0415

        slack_app = create_slack_app()
        start_socket_mode(slack_app)
        logger.info("Slack listener started")
    else:
        logger.warning(
            "SLACK_BOT_TOKEN/SLACK_APP_TOKEN not set, Slack features disabled"
        )
        slack_app = None

    # Import scheduler after DB init to avoid circular imports
    from watchman.scheduler.jobs import (  # noqa: PLC0415
        schedule_delivery_job,
        schedule_enrichment_job,
        schedule_scoring_job,
        setup_scheduler,
    )

    # Set up scheduler with collection jobs and scoring job
    scheduler = setup_scheduler(enabled_sources, db_path, rubric_path)

    # Add enrichment fallback job (runs regardless of Slack)
    schedule_enrichment_job(scheduler, db_path)

    # Add daily delivery job only when Slack is configured
    if slack_enabled:
        schedule_delivery_job(scheduler, db_path, rubric_path)

    scheduler.start()

    logger.info(
        "Watchman started with %d scheduled jobs. Press Ctrl+C to stop.",
        len(scheduler.get_jobs()),
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Watchman...")
        scheduler.shutdown()
        logger.info("Watchman stopped.")


if __name__ == "__main__":
    main()
