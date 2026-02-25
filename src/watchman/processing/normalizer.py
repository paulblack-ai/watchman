"""Raw item to signal card normalization."""

import logging
from pathlib import Path

from watchman.models.raw_item import RawItem
from watchman.models.signal_card import SignalCard
from watchman.models.source import SourceConfig
from watchman.processing.deduplicator import handle_duplicate, is_duplicate
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository, RawItemRepository

logger = logging.getLogger(__name__)


def normalize_raw_item(item: RawItem, tier: int) -> SignalCard:
    """Normalize a raw item into a signal card.

    Maps RawItem fields to SignalCard fields, computes URL hash
    and content fingerprint for deduplication.

    Args:
        item: Raw item from a collector.
        tier: Source tier (1, 2, or 3) from source config.

    Returns:
        A SignalCard instance ready for deduplication and storage.
    """
    title = item.title or "Untitled"
    url = item.url or ""
    date = item.published_date or item.fetched_at

    url_hash = SignalCard.compute_url_hash(url)
    content_fingerprint = SignalCard.compute_content_fingerprint(title, date)

    return SignalCard(
        title=title,
        source_name=item.source_name,
        date=date,
        url=url,
        tier=tier,
        summary=item.summary,
        collector_type=item.collector_type,
        url_hash=url_hash,
        content_fingerprint=content_fingerprint,
    )


async def process_unprocessed(
    db_path: Path, source_configs: dict[str, SourceConfig]
) -> int:
    """Process all unprocessed raw items: normalize, deduplicate, store.

    Args:
        db_path: Path to the SQLite database.
        source_configs: Map of source name to SourceConfig for tier lookup.

    Returns:
        Number of new (non-duplicate) cards created.
    """
    new_cards = 0

    async with get_connection(db_path) as db:
        raw_repo = RawItemRepository(db)
        card_repo = CardRepository(db)

        unprocessed = await raw_repo.find_unprocessed()

        if not unprocessed:
            logger.debug("No unprocessed raw items")
            return 0

        logger.info("Processing %d unprocessed raw items", len(unprocessed))

        for item in unprocessed:
            try:
                # Look up tier from source config
                source_cfg = source_configs.get(item.source_name)
                tier = source_cfg.tier if source_cfg else 2  # Default to Tier 2

                # Normalize
                card = normalize_raw_item(item, tier)

                # Deduplicate
                is_dup, canonical = await is_duplicate(card, card_repo)

                if is_dup and canonical:
                    # Insert duplicate card for tracking, then link it
                    dup_id = await card_repo.insert(card)
                    card_with_id = SignalCard(id=dup_id, **card.model_dump(exclude={"id"}))
                    await handle_duplicate(card_with_id, canonical, card_repo)
                    logger.debug(
                        "Duplicate: '%s' matches canonical card %d",
                        card.title,
                        canonical.id,
                    )
                else:
                    # Insert as new canonical card
                    await card_repo.insert(card)
                    new_cards += 1

                # Mark raw item as processed
                await raw_repo.mark_processed(item.id)

            except Exception:
                logger.exception(
                    "Error processing raw item %d: '%s'",
                    item.id,
                    item.title,
                )

    logger.info("Processed items: %d new cards created", new_cards)
    return new_cards
