"""Daily review queue delivery job: posts scored signal cards to Slack."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yaml
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from watchman.scoring.models import RubricScore
from watchman.slack.blocks import build_review_footer, build_signal_card_blocks
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)


def _load_daily_cap(rubric_path: Path) -> int:
    """Load the daily_cap_target from the rubric YAML config.

    Args:
        rubric_path: Path to rubric.yaml config file.

    Returns:
        daily_cap_target value (defaults to 5 if not found).
    """
    try:
        with open(rubric_path, "r") as f:
            config = yaml.safe_load(f) or {}
        return int(config.get("daily_cap_target", 5))
    except Exception:
        logger.warning("Could not load rubric config from %s, defaulting cap to 5", rubric_path)
        return 5


async def deliver_daily_review(db_path: Path, rubric_path: Path) -> int:
    """Deliver today's top-scored signal cards to the Slack review channel.

    Selects the top N cards by score (including re-queued snoozed cards),
    posts each as a Block Kit card with approve/reject/snooze/details buttons,
    and finishes with a footer showing "Showing X of Y signals today".

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config (for daily_cap_target).

    Returns:
        Number of cards delivered.

    Raises:
        EnvironmentError: If SLACK_BOT_TOKEN or SLACK_CHANNEL_ID are not set.
    """
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")

    if not slack_token:
        raise EnvironmentError("SLACK_BOT_TOKEN environment variable is not set")
    if not channel_id:
        raise EnvironmentError("SLACK_CHANNEL_ID environment variable is not set")

    cap = _load_daily_cap(rubric_path)
    client = WebClient(token=slack_token)

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        cards = await repo.find_top_scored_today(limit=cap)
        total_today = await repo.count_scored_today()

    if not cards:
        logger.info("No scored cards available for delivery today")
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

        blocks = build_signal_card_blocks(card, score)

        try:
            response = client.chat_postMessage(
                channel=channel_id,
                blocks=blocks,
                text=f"Signal: {card.title}",
            )
        except SlackApiError:
            logger.exception("Failed to post card %d to Slack", card.id)
            continue

        # Save slack_message_ts and channel so action handlers can update the message
        message_ts = response.get("ts")
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.set_review_state(
                card.id,
                "pending",
                slack_ts=message_ts,
                slack_channel=channel_id,
            )

        logger.info(
            "Delivered card %d '%s' (score=%.1f)",
            card.id,
            card.title,
            card.relevance_score or 0.0,
        )
        delivered += 1

    # Post the footer
    footer_blocks = build_review_footer(delivered, total_today)
    try:
        client.chat_postMessage(
            channel=channel_id,
            blocks=footer_blocks,
            text=f"Showing {delivered} of {total_today} signals today",
        )
    except SlackApiError:
        logger.exception("Failed to post review footer to Slack")

    logger.info("Daily review complete: delivered %d of %d cards", delivered, total_today)
    return delivered


def deliver_daily_review_sync(db_path: Path, rubric_path: Path) -> None:
    """Synchronous wrapper around deliver_daily_review for APScheduler.

    APScheduler runs jobs in a thread pool (not async context), so this
    wrapper calls asyncio.run() to bridge the sync/async boundary.

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.
    """
    import asyncio

    try:
        count = asyncio.run(deliver_daily_review(db_path, rubric_path))
        logger.info("Delivery job complete: %d cards sent", count)
    except Exception:
        logger.exception("Daily delivery job failed")
