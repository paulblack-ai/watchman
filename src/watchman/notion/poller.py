"""Notion status poller: syncs Review Status and Gate 2 changes back to SQLite."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from watchman.notion.client import NotionClient
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)


# Notion -> SQLite state mappings
_REVIEW_STATUS_MAP: dict[str, str] = {
    "Approved": "approved",
    "Rejected": "rejected",
    "Snoozed": "snoozed",
    "To Review": "pending",  # no-op
}

_GATE2_STATUS_MAP: dict[str, str] = {
    "Approved": "gate2_approved",
    "Rejected": "gate2_rejected",
    "To Review": "pending",  # no-op
    "Not Started": "pending",  # no-op
}


def _extract_status_name(page: dict, property_name: str) -> str | None:
    """Extract a status property value from a Notion page dict.

    Args:
        page: Notion page object.
        property_name: Name of the status property.

    Returns:
        Status name string, or None if not present.
    """
    props = page.get("properties", {})
    prop = props.get(property_name, {})
    status = prop.get("status")
    if not status:
        return None
    return status.get("name")


def _extract_notion_page_id(page: dict) -> str:
    """Extract page ID from a Notion page object."""
    return page.get("id", "")


async def _load_card_by_notion_page_id(
    repo: CardRepository, notion_page_id: str
):  # noqa: ANN201
    """Load a card by its Notion page ID.

    Args:
        repo: CardRepository with an active DB connection.
        notion_page_id: Notion page ID to look up.

    Returns:
        SignalCard if found, None otherwise.
    """
    async with repo.db.execute(
        "SELECT * FROM cards WHERE notion_page_id = ?", (notion_page_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return CardRepository._row_to_card(row)


async def poll_notion_status(db_path: Path) -> int:
    """Poll Notion database for status changes and sync back to SQLite.

    Queries Notion for all pages where Review Status is not "To Review" or
    Gate 2 has changed. Maps Notion status values to SQLite states and
    triggers downstream actions (enrichment on approval, JSON write on Gate 2 approval).

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Count of status changes processed.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_db_id = os.environ.get("NOTION_DATABASE_ID")

    if not notion_token or not notion_db_id:
        logger.warning("NOTION_TOKEN/NOTION_DATABASE_ID not set, skipping poll")
        return 0

    client = NotionClient(token=notion_token, database_id=notion_db_id)
    changes_processed = 0

    try:
        # Query pages where Review Status is not "To Review" (user acted on them)
        pages = client.query_database(
            filter={
                "or": [
                    {
                        "property": "Review Status",
                        "status": {"does_not_equal": "To Review"},
                    },
                    {
                        "property": "Gate 2",
                        "status": {"does_not_equal": "Not Started"},
                    },
                ]
            }
        )
    except Exception:
        logger.exception("Failed to query Notion database during poll")
        return 0

    for page in pages:
        notion_page_id = _extract_notion_page_id(page)
        if not notion_page_id:
            continue

        review_status_notion = _extract_status_name(page, "Review Status")
        gate2_status_notion = _extract_status_name(page, "Gate 2")

        # Load matching card from SQLite
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            card = await _load_card_by_notion_page_id(repo, notion_page_id)

        if card is None:
            logger.debug(
                "No card found for Notion page %s, skipping", notion_page_id
            )
            continue

        # --- Process Review Status changes ---
        if review_status_notion and review_status_notion != "To Review":
            new_review_state = _REVIEW_STATUS_MAP.get(review_status_notion)
            if new_review_state and new_review_state != card.review_state:
                logger.info(
                    "Card %d review state: %s -> %s (from Notion)",
                    card.id,
                    card.review_state,
                    new_review_state,
                )
                async with get_connection(db_path) as db:
                    repo = CardRepository(db)
                    await repo.set_review_state(card.id, new_review_state)

                changes_processed += 1

                if new_review_state == "approved":
                    try:
                        from watchman.enrichment.pipeline import (  # noqa: PLC0415
                            enrich_approved_card,
                        )

                        await enrich_approved_card(card.id, db_path)
                        logger.info(
                            "Enrichment triggered for card %d after Notion approval",
                            card.id,
                        )
                    except Exception:
                        logger.exception(
                            "Enrichment failed for card %d (will retry via fallback job)",
                            card.id,
                        )

                elif new_review_state == "snoozed":
                    async with get_connection(db_path) as db:
                        repo = CardRepository(db)
                        await repo.snooze_card(card.id, days=30)

                    # Update Notion page with Snooze Until date
                    try:
                        from datetime import datetime, timedelta, timezone  # noqa: PLC0415

                        snooze_date = (
                            datetime.now(timezone.utc) + timedelta(days=30)
                        ).isoformat()
                        client.update_page(
                            notion_page_id,
                            {
                                "Snooze Until": {
                                    "date": {"start": snooze_date}
                                }
                            },
                        )
                    except Exception:
                        logger.exception(
                            "Failed to update Snooze Until on Notion for card %d",
                            card.id,
                        )

        # --- Process Gate 2 status changes ---
        if gate2_status_notion and gate2_status_notion not in ("Not Started", "To Review"):
            new_gate2_state = _GATE2_STATUS_MAP.get(gate2_status_notion)

            # Reload card state (may have changed during review processing above)
            async with get_connection(db_path) as db:
                repo = CardRepository(db)
                card = await _load_card_by_notion_page_id(repo, notion_page_id)

            if card is None:
                continue

            if new_gate2_state and new_gate2_state != card.gate2_state:
                logger.info(
                    "Card %d gate2 state: %s -> %s (from Notion)",
                    card.id,
                    card.gate2_state,
                    new_gate2_state,
                )
                async with get_connection(db_path) as db:
                    repo = CardRepository(db)
                    await repo.set_gate2_state(card.id, new_gate2_state)

                changes_processed += 1

                if new_gate2_state == "gate2_approved":
                    # Write JSON output file
                    if card.enrichment_data:
                        try:
                            from watchman.models.icebreaker import (  # noqa: PLC0415
                                IcebreakerToolEntry,
                            )
                            from watchman.output.writer import (  # noqa: PLC0415
                                write_tool_entry,
                            )

                            entry = IcebreakerToolEntry.model_validate_json(
                                card.enrichment_data
                            )
                            output_path = write_tool_entry(entry, card.id)

                            async with get_connection(db_path) as db:
                                repo = CardRepository(db)
                                await repo.save_output_path(card.id, str(output_path))

                            logger.info(
                                "Gate 2 approved card %d, output: %s",
                                card.id,
                                output_path,
                            )
                        except Exception:
                            logger.exception(
                                "Failed to write Gate 2 output for card %d", card.id
                            )

                    # Update Notion Enrichment property to reflect final state
                    try:
                        from watchman.notion.delivery import (  # noqa: PLC0415
                            _build_select_property,
                        )

                        client.update_page(
                            notion_page_id,
                            {"Enrichment": _build_select_property("complete")},
                        )
                    except Exception:
                        logger.exception(
                            "Failed to update Enrichment on Notion for card %d",
                            card.id,
                        )

                elif new_gate2_state == "gate2_rejected":
                    try:
                        from watchman.notion.delivery import (  # noqa: PLC0415
                            _build_select_property,
                        )

                        client.update_page(
                            notion_page_id,
                            {"Enrichment": _build_select_property("failed")},
                        )
                    except Exception:
                        logger.exception(
                            "Failed to update Enrichment status after Gate 2 rejection for card %d",
                            card.id,
                        )

    logger.info("Notion poll complete: %d status changes processed", changes_processed)
    return changes_processed


def poll_notion_status_sync(db_path: Path) -> None:
    """Synchronous wrapper around poll_notion_status for APScheduler.

    APScheduler runs jobs in a thread pool (not async context), so this
    wrapper calls asyncio.run() to bridge the sync/async boundary.

    Args:
        db_path: Path to the SQLite database.
    """
    try:
        count = asyncio.run(poll_notion_status(db_path))
        if count > 0:
            logger.info("Notion poll job: %d changes synced", count)
    except Exception:
        logger.exception("Notion poll job failed")
