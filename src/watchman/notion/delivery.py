"""Notion daily review delivery: pushes scored signal cards to a Notion database."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import yaml

from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.notion.client import NotionClient
from watchman.scoring.models import RubricScore
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)


def _load_daily_cap(rubric_path: Path) -> int:
    """Load daily_cap_target from rubric YAML config.

    Args:
        rubric_path: Path to rubric.yaml config file.

    Returns:
        daily_cap_target value (defaults to 5 if not found).
    """
    try:
        with open(rubric_path) as f:
            config = yaml.safe_load(f) or {}
        return int(config.get("daily_cap_target", 5))
    except Exception:
        logger.warning(
            "Could not load rubric config from %s, defaulting cap to 5", rubric_path
        )
        return 5


def _build_review_status_property(status_name: str) -> dict:
    """Build a Notion status property value dict."""
    return {"status": {"name": status_name}}


def _build_select_property(value: str) -> dict:
    """Build a Notion select property value dict."""
    return {"select": {"name": value}}


def _build_number_property(value: float | int | None) -> dict:
    """Build a Notion number property value dict."""
    return {"number": value}


def _build_date_property(iso_date: str) -> dict:
    """Build a Notion date property value dict."""
    return {"date": {"start": iso_date}}


def _build_url_property(url: str) -> dict:
    """Build a Notion url property value dict."""
    return {"url": url}


def _build_title_property(text: str) -> dict:
    """Build a Notion title property value dict."""
    return {"title": [{"text": {"content": text[:2000]}}]}


def _build_heading_block(text: str) -> dict:
    """Build a Notion heading_2 block."""
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": text}}]},
    }


def _build_paragraph_block(text: str) -> dict:
    """Build a Notion paragraph block. Truncates at 2000 chars (Notion limit)."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": text[:2000]}}]},
    }


def _build_card_properties(card, score: RubricScore) -> dict:
    """Build the Notion property dict for a signal card.

    Args:
        card: SignalCard instance.
        score: RubricScore parsed from card.score_breakdown.

    Returns:
        Dict of Notion property values.
    """
    return {
        "Title": _build_title_property(card.title),
        "Source": _build_select_property(card.source_name),
        "Tier": _build_select_property(str(card.tier)),
        "Score": _build_number_property(card.relevance_score),
        "Top Dimension": _build_select_property(score.top_dimension),
        "Review Status": _build_review_status_property("To Review"),
        "Published": _build_date_property(card.date.isoformat()),
        "URL": _build_url_property(card.url),
        "Enrichment": _build_select_property(card.enrichment_state),
        "Gate 2": _build_review_status_property("Not Started"),
        "Attempts": _build_number_property(card.enrichment_attempt_count),
    }


def _build_card_body(card, score: RubricScore) -> list[dict]:
    """Build page body blocks for a signal card.

    Includes summary heading + content, and rubric breakdown.

    Args:
        card: SignalCard instance.
        score: RubricScore parsed from card.score_breakdown.

    Returns:
        List of Notion block dicts.
    """
    blocks: list[dict] = []

    # Summary section
    blocks.append(_build_heading_block("Summary"))
    summary_text = card.summary or "(no summary)"
    blocks.append(_build_paragraph_block(summary_text))

    # Rubric breakdown section
    blocks.append(_build_heading_block("Rubric Breakdown"))
    breakdown_lines = [
        f"Composite Score: {score.composite_score:.2f}",
        f"Top Dimension: {score.top_dimension}",
        "",
        f"Taxonomy Fit: {score.taxonomy_fit.score:.2f} — {score.taxonomy_fit.rationale}",
        f"Novel Capability: {score.novel_capability.score:.2f} — {score.novel_capability.rationale}",
        f"Adoption Traction: {score.adoption_traction.score:.2f} — {score.adoption_traction.rationale}",
        f"Credibility: {score.credibility.score:.2f} — {score.credibility.rationale}",
    ]
    blocks.append(_build_paragraph_block("\n".join(breakdown_lines)))

    return blocks


async def deliver_daily_review_notion(db_path: Path, rubric_path: Path) -> int:
    """Deliver today's top-scored signal cards to a Notion database.

    For each card, creates a Notion page row with all required properties and
    page body content (summary, rubric breakdown). Saves notion_page_id back
    to SQLite after creation.

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config (for daily_cap_target).

    Returns:
        Number of cards delivered to Notion.

    Raises:
        EnvironmentError: If NOTION_TOKEN or NOTION_DATABASE_ID are not set.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_db_id = os.environ.get("NOTION_DATABASE_ID")

    if not notion_token:
        raise EnvironmentError("NOTION_TOKEN environment variable is not set")
    if not notion_db_id:
        raise EnvironmentError("NOTION_DATABASE_ID environment variable is not set")

    cap = _load_daily_cap(rubric_path)
    client = NotionClient(token=notion_token, database_id=notion_db_id)

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        cards = await repo.find_top_scored_today(limit=cap)
        total_today = await repo.count_scored_today()

    if not cards:
        logger.info("No scored cards available for Notion delivery today")
        return 0

    delivered = 0

    for card in cards:
        if card.score_breakdown is None:
            logger.warning("Card %d has no score_breakdown, skipping", card.id)
            continue

        try:
            score = RubricScore.model_validate_json(card.score_breakdown)
        except Exception:
            logger.exception("Failed to parse score for card %d, skipping", card.id)
            continue

        # Skip cards already in Notion
        if card.notion_page_id:
            logger.debug("Card %d already has notion_page_id, skipping", card.id)
            delivered += 1
            continue

        try:
            properties = _build_card_properties(card, score)
            children = _build_card_body(card, score)
            page_id = client.create_page(properties, children)

            async with get_connection(db_path) as db:
                repo = CardRepository(db)
                await repo.save_notion_page_id(card.id, page_id)

            logger.info(
                "Delivered card %d '%s' to Notion (score=%.1f)",
                card.id,
                card.title,
                card.relevance_score or 0.0,
            )
            delivered += 1

        except Exception:
            logger.exception(
                "Failed to deliver card %d '%s' to Notion", card.id, card.title
            )

    logger.info(
        "Notion delivery complete: %d of %d cards delivered", delivered, total_today
    )
    return delivered


def deliver_daily_review_notion_sync(db_path: Path, rubric_path: Path) -> None:
    """Synchronous wrapper around deliver_daily_review_notion for APScheduler.

    APScheduler runs jobs in a thread pool (not async context), so this
    wrapper calls asyncio.run() to bridge the sync/async boundary.

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.
    """
    try:
        count = asyncio.run(deliver_daily_review_notion(db_path, rubric_path))
        logger.info("Notion delivery job complete: %d cards sent", count)
    except Exception:
        logger.exception("Notion daily delivery job failed")


async def deliver_gate2_to_notion(card_id: int, db_path: Path) -> None:
    """Deliver a Gate 2 enrichment result to Notion.

    If the card already has a notion_page_id: updates the existing page properties
    (Enrichment=complete, Gate 2=To Review) and appends enrichment content blocks.
    If no notion_page_id (edge case): creates a new page.

    Args:
        card_id: ID of the enriched card.
        db_path: Path to the SQLite database.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_db_id = os.environ.get("NOTION_DATABASE_ID")

    if not notion_token or not notion_db_id:
        logger.warning(
            "NOTION_TOKEN/NOTION_DATABASE_ID not set, skipping Gate 2 Notion delivery for card %d",
            card_id,
        )
        return

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        async with db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)) as cursor:
            row = await cursor.fetchone()
            card = CardRepository._row_to_card(row) if row else None

    if card is None or card.enrichment_data is None:
        logger.warning("Card %d has no enrichment data for Gate 2 Notion delivery", card_id)
        return

    entry = IcebreakerToolEntry.model_validate_json(card.enrichment_data)
    client = NotionClient(token=notion_token, database_id=notion_db_id)

    # Build enrichment content blocks
    enrichment_blocks = [
        _build_heading_block(f"Enrichment: {entry.name}"),
        _build_paragraph_block(entry.description),
    ]

    if entry.capabilities:
        cap_text = "\n".join(f"- {c}" for c in entry.capabilities)
        enrichment_blocks.append(_build_heading_block("Capabilities"))
        enrichment_blocks.append(_build_paragraph_block(cap_text))

    if entry.pricing:
        enrichment_blocks.append(_build_heading_block("Pricing"))
        enrichment_blocks.append(_build_paragraph_block(entry.pricing))

    if entry.api_surface:
        enrichment_blocks.append(_build_heading_block("API Surface"))
        enrichment_blocks.append(_build_paragraph_block(entry.api_surface))

    if entry.integration_hooks:
        hooks_text = "\n".join(f"- {h}" for h in entry.integration_hooks)
        enrichment_blocks.append(_build_heading_block("Integration Hooks"))
        enrichment_blocks.append(_build_paragraph_block(hooks_text))

    try:
        if card.notion_page_id:
            # Update existing page
            client.update_page(
                card.notion_page_id,
                {
                    "Enrichment": _build_select_property("complete"),
                    "Gate 2": _build_review_status_property("To Review"),
                },
            )
            client.update_page_content(card.notion_page_id, enrichment_blocks)
            logger.info(
                "Updated Gate 2 enrichment on Notion page for card %d", card_id
            )
        else:
            # Edge case: create new page with enrichment data
            if card.score_breakdown:
                score = RubricScore.model_validate_json(card.score_breakdown)
                properties = _build_card_properties(card, score)
            else:
                properties = {
                    "Title": _build_title_property(card.title),
                    "Enrichment": _build_select_property("complete"),
                    "Gate 2": _build_review_status_property("To Review"),
                }
            # Override enrichment and gate2 status
            properties["Enrichment"] = _build_select_property("complete")
            properties["Gate 2"] = _build_review_status_property("To Review")

            page_id = client.create_page(properties, enrichment_blocks)
            async with get_connection(db_path) as db:
                repo = CardRepository(db)
                await repo.save_notion_page_id(card_id, page_id)
            logger.info(
                "Created Gate 2 Notion page for card %d (no prior notion_page_id)", card_id
            )

        # Update gate2_state to pending in SQLite
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.set_gate2_state(card_id, "pending")

    except Exception:
        logger.exception("Failed Gate 2 Notion delivery for card %d", card_id)
