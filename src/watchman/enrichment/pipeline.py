"""Enrichment pipeline: scrape, extract, validate, and store tool entries."""

import logging
from pathlib import Path

from watchman.enrichment.extractor import enrich_card
from watchman.enrichment.scraper import scrape_url
from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)


async def _load_card_by_id(repo: CardRepository, card_id: int):  # noqa: ANN201
    """Load a card by ID using a direct DB query.

    Args:
        repo: CardRepository with an active DB connection.
        card_id: ID of the card to fetch.

    Returns:
        SignalCard if found, None otherwise.
    """
    async with repo.db.execute(
        "SELECT * FROM cards WHERE id = ?", (card_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return CardRepository._row_to_card(row)


async def enrich_approved_card(
    card_id: int, db_path: Path
) -> IcebreakerToolEntry | None:
    """Enrich an approved signal card with structured tool information.

    This is the main entry point called when a card is approved in Gate 1.
    Guards against enriching non-approved cards (ENRCH-01 safety).

    Args:
        card_id: ID of the approved card to enrich.
        db_path: Path to the SQLite database.

    Returns:
        Validated IcebreakerToolEntry if enrichment succeeds, None otherwise.
    """
    async with get_connection(db_path) as db:
        repo = CardRepository(db)

        card = await _load_card_by_id(repo, card_id)
        if card is None:
            logger.warning("Card %d not found for enrichment", card_id)
            return None

        if card.review_state != "approved":
            logger.warning(
                "Card %d has review_state='%s', skipping enrichment (only approved cards)",
                card_id,
                card.review_state,
            )
            return None

        try:
            await repo.set_enrichment_state(card_id, "in_progress")

            # Scrape the tool's webpage (may return None)
            page_content = await scrape_url(card.url)

            # Extract structured data using Claude Sonnet
            entry = await enrich_card(
                card.title, card.url, card.summary, page_content
            )

            # Persist validated enrichment result
            await repo.save_enrichment(card_id, entry)
            logger.info(
                "Enrichment complete for card %d: %s", card_id, card.title[:60]
            )
            return entry

        except Exception as e:
            await repo.save_enrichment_error(card_id, str(e))
            logger.exception(
                "Enrichment failed for card %d (%s)", card_id, card.title[:60]
            )
            return None


async def enrich_pending_approved(db_path: Path) -> int:
    """Batch-enrich all approved but unenriched cards.

    Used as a fallback job to catch cards where immediate enrichment
    failed or was skipped. Processes sequentially (rate-limit friendly).

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Number of cards successfully enriched in this run.
    """
    enriched_count = 0

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        unenriched = await repo.find_approved_unenriched()

        if not unenriched:
            logger.info("No approved unenriched cards found -- skipping enrichment run")
            return 0

        logger.info("Found %d approved unenriched cards", len(unenriched))

    # Process each card with its own connection (matches score_unscored_cards pattern)
    for card in unenriched:
        result = await enrich_approved_card(card.id, db_path)
        if result is not None:
            enriched_count += 1

    logger.info(
        "Enrichment run complete: %d/%d cards enriched",
        enriched_count,
        len(unenriched),
    )
    return enriched_count
