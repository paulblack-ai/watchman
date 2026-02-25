"""One-shot script: wipe DB, collect last 2 weeks, normalize, score, deliver to Slack."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


async def run_full_pipeline() -> None:
    """Execute the full pipeline: wipe -> collect -> normalize -> score -> deliver."""
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env")

    from watchman.collectors import get_collector
    from watchman.config.loader import get_enabled_sources, load_sources
    from watchman.processing.normalizer import process_unprocessed
    from watchman.scoring.scorer import score_unscored_cards
    from watchman.slack.delivery import deliver_daily_review
    from watchman.storage.database import get_connection, init_db

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("reset_and_collect")

    db_path = Path("watchman.db")
    config_path = Path("src/watchman/config/sources.yaml")
    rubric_path = Path("src/watchman/config/rubric.yaml")

    # Step 1: Wipe all data
    logger.info("=== Step 1: Wiping all existing data ===")
    async with get_connection(db_path) as db:
        await db.execute("DELETE FROM cards")
        await db.execute("DELETE FROM raw_items")
        await db.execute("DELETE FROM source_health")
        await db.commit()
    logger.info("All tables cleared")

    # Step 2: Re-init DB (ensures schema is current)
    logger.info("=== Step 2: Re-initializing database schema ===")
    await init_db(db_path)
    logger.info("Schema verified")

    # Step 3: Collect from all enabled sources (last 2 weeks only)
    logger.info("=== Step 3: Collecting from all sources (last 14 days) ===")
    registry = load_sources(config_path)
    enabled = get_enabled_sources(registry)
    total_items = 0

    for source in enabled:
        try:
            collector = get_collector(source, db_path)
            count = await collector.run(max_age_days=14)
            total_items += count
            logger.info("  %s: %d items", source.name, count)
        except Exception:
            logger.exception("  %s: FAILED", source.name)

    logger.info("Collection complete: %d total items from %d sources", total_items, len(enabled))

    # Step 4: Normalize raw items into signal cards
    logger.info("=== Step 4: Normalizing raw items into signal cards ===")
    source_configs = {s.name: s for s in registry.sources}
    new_cards = await process_unprocessed(db_path, source_configs)
    logger.info("Normalization complete: %d new cards", new_cards)

    # Step 5: Score all cards
    logger.info("=== Step 5: Scoring signal cards ===")
    scored = await score_unscored_cards(db_path, rubric_path)
    logger.info("Scoring complete: %d cards scored", scored)

    # Step 6: Deliver to Slack
    logger.info("=== Step 6: Delivering to Slack ===")
    try:
        delivered = await deliver_daily_review(db_path, rubric_path)
        logger.info("Delivery complete: %d cards sent to Slack", delivered)
    except Exception:
        logger.exception("Delivery failed (check SLACK_BOT_TOKEN and SLACK_CHANNEL_ID)")

    # Summary
    logger.info("=== PIPELINE COMPLETE ===")
    logger.info("  Raw items collected: %d", total_items)
    logger.info("  Signal cards created: %d", new_cards)
    logger.info("  Cards scored: %d", scored)


if __name__ == "__main__":
    asyncio.run(run_full_pipeline())
