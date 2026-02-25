"""Watchman entry point: loads config, inits DB, starts scheduler."""

import asyncio
import logging
import time
from pathlib import Path

from watchman.config.loader import get_enabled_sources, load_sources
from watchman.storage.database import init_db


def main() -> None:
    """Start the Watchman signal collection agent.

    Loads source configuration, initializes the database, sets up
    the scheduler, and runs until interrupted with Ctrl+C.
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

    # Import here to avoid circular imports (scheduler imports health which imports storage)
    from watchman.scheduler.jobs import setup_scheduler

    # Set up and start scheduler
    scheduler = setup_scheduler(enabled_sources, db_path)
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
