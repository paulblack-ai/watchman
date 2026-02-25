"""Two-layer signal deduplication: URL hash + content fingerprint."""

import logging
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from watchman.models.signal_card import SignalCard
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)

# Minimum title length for fuzzy matching (avoid false positives on short titles)
MIN_TITLE_LENGTH_FOR_FUZZY = 20

# Title similarity threshold for content fingerprint dedup
TITLE_SIMILARITY_THRESHOLD = 0.85

# Window for content fingerprint dedup
DEDUP_WINDOW_DAYS = 7


def title_similarity(a: str, b: str) -> float:
    """Compute title similarity ratio using SequenceMatcher.

    Args:
        a: First title.
        b: Second title.

    Returns:
        Similarity ratio between 0.0 and 1.0.
    """
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


async def is_duplicate(
    card: SignalCard, repo: CardRepository
) -> tuple[bool, SignalCard | None]:
    """Check if a signal card is a duplicate using two-layer deduplication.

    Layer 1: Exact URL hash match (fast).
    Layer 2: Content fingerprint - title similarity >85% within 7-day window (slower).

    Conservative matching per user decision: better to let some dupes through
    than merge distinct signals.

    Args:
        card: The signal card to check.
        repo: CardRepository for database queries.

    Returns:
        Tuple of (is_duplicate, canonical_card_or_none).
    """
    # Layer 1: Exact URL match
    existing = await repo.find_by_url_hash(card.url_hash)
    if existing:
        return True, existing

    # Layer 2: Content fingerprint (title similarity within 7-day window)
    # Skip fuzzy matching for short titles to avoid false positives
    if len(card.title.strip()) < MIN_TITLE_LENGTH_FOR_FUZZY:
        return False, None

    cutoff = datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)
    recent_cards = await repo.find_since(cutoff)

    for recent in recent_cards:
        # Skip self-comparison
        if recent.url_hash == card.url_hash:
            continue

        # Skip short titles in existing cards too
        if len(recent.title.strip()) < MIN_TITLE_LENGTH_FOR_FUZZY:
            continue

        similarity = title_similarity(card.title, recent.title)
        if similarity > TITLE_SIMILARITY_THRESHOLD:
            # Additional date proximity check (within 1 day)
            if card.date and recent.date:
                date_diff = abs((card.date - recent.date).days)
                if date_diff <= 1:
                    logger.debug(
                        "Content fingerprint match: '%s' (~%.0f%% similar to '%s')",
                        card.title,
                        similarity * 100,
                        recent.title,
                    )
                    return True, recent

    return False, None


async def handle_duplicate(
    duplicate_card: SignalCard,
    canonical_card: SignalCard,
    repo: CardRepository,
) -> None:
    """Link a duplicate card to its canonical card and update seen count.

    Args:
        duplicate_card: The duplicate card (must have an id).
        canonical_card: The canonical (first seen) card.
        repo: CardRepository for database updates.
    """
    if duplicate_card.id is None or canonical_card.id is None:
        logger.warning("Cannot link duplicate: missing card IDs")
        return

    await repo.link_duplicate(duplicate_card.id, canonical_card.id)
    await repo.increment_seen_count(canonical_card.id)

    logger.info(
        "Linked duplicate '%s' (id=%d) to canonical card %d",
        duplicate_card.title,
        duplicate_card.id,
        canonical_card.id,
    )
