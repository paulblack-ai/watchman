"""Enrichment pipeline: scrape, extract, validate, and store tool entries."""

import asyncio
import logging
import os
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
    entry = None

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

        except Exception as e:
            await repo.save_enrichment_error(card_id, str(e))
            logger.exception(
                "Enrichment failed for card %d (%s)", card_id, card.title[:60]
            )
            return None

    # Deliver Gate 2 Slack card outside the DB connection (OUT-01)
    if entry is not None:
        try:
            await async_deliver_gate2_card(card_id, db_path)
        except Exception:
            logger.exception(
                "Gate 2 delivery failed for card %d (card is enriched, delivery will retry)",
                card_id,
            )

    return entry


async def async_deliver_gate2_card(card_id: int, db_path: Path) -> None:
    """Post a Gate 2 review card to Slack after enrichment completes (async).

    Loads the enriched card and its IcebreakerToolEntry, builds a Gate 2
    Block Kit card, and posts it to the configured Slack channel.

    Args:
        card_id: ID of the enriched card.
        db_path: Path to the SQLite database.
    """
    from slack_sdk import WebClient  # noqa: PLC0415

    from watchman.slack.blocks import build_gate2_card_blocks  # noqa: PLC0415

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")

    if not slack_token or not channel_id:
        logger.warning(
            "Slack not configured, skipping Gate 2 delivery for card %d", card_id
        )
        return

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        card = await _load_card_by_id(repo, card_id)

    if card is None or card.enrichment_data is None:
        logger.warning("Card %d has no enrichment data for Gate 2", card_id)
        return

    entry = IcebreakerToolEntry.model_validate_json(card.enrichment_data)
    can_re_enrich = (card.enrichment_attempt_count or 1) < 3

    blocks = build_gate2_card_blocks(card, entry, can_re_enrich=can_re_enrich)

    client = WebClient(token=slack_token)
    try:
        response = await asyncio.to_thread(
            client.chat_postMessage,
            channel=channel_id,
            blocks=blocks,
            text=f"Gate 2 Review: {entry.name}",
        )
        message_ts = response.get("ts")

        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.set_gate2_state(card_id, "pending", slack_ts=message_ts)

        logger.info("Gate 2 card posted for card %d: %s", card_id, entry.name)
    except Exception:
        logger.exception("Failed to post Gate 2 card for card %d", card_id)


def deliver_gate2_card(card_id: int, db_path: Path) -> None:
    """Sync wrapper for async_deliver_gate2_card (for use outside async context)."""
    asyncio.run(async_deliver_gate2_card(card_id, db_path))


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
