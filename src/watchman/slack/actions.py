"""Action handlers for Slack review buttons: approve, reject, snooze, details."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from slack_bolt import App

from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.output.writer import write_tool_entry
from watchman.scoring.models import RubricScore
from watchman.slack.blocks import (
    build_confirmed_card_blocks,
    build_details_blocks,
    build_gate2_confirmed_blocks,
    build_review_footer,
    build_signal_card_blocks,
)
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    """Get the database path from the environment or use the default."""
    return Path(os.environ.get("WATCHMAN_DB_PATH", "watchman.db"))


def register_actions(app: App) -> None:
    """Register all Slack action handlers on the Bolt App.

    Registers handlers for: approve_card, reject_card, snooze_card, details_card.

    Args:
        app: Configured Bolt App to register handlers on.
    """

    @app.action("approve_card")
    def handle_approve(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Approve button click."""
        ack()
        _handle_review_action(body, client, "approved")

    @app.action("reject_card")
    def handle_reject(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Reject button click."""
        ack()
        _handle_review_action(body, client, "rejected")

    @app.action("snooze_card")
    def handle_snooze(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Snooze 30d button click."""
        ack()
        _handle_snooze_action(body, client)

    @app.action("details_card")
    def handle_details(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Details button click."""
        ack()
        _handle_details_action(body, client)


def _handle_review_action(body: dict, client, state: str) -> None:  # noqa: ANN001
    """Approve or reject a card: update DB and replace Slack message.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
        state: New review state ("approved" or "rejected").
    """
    action = body["actions"][0]
    card_id = int(action["value"])
    message = body.get("message", {})
    channel_id = body["channel"]["id"]
    message_ts = message.get("ts", "")

    db_path = _get_db_path()

    async def _update() -> None:
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.set_review_state(
                card_id,
                state,
                slack_ts=message_ts,
                slack_channel=channel_id,
            )
            card = await _load_card_by_id(repo, card_id)
            if card is None:
                raise ValueError(f"Card {card_id} not found after state update")
            return card

    try:
        card = asyncio.run(_update())
        confirmed_blocks = build_confirmed_card_blocks(card, state)
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=confirmed_blocks,
            text=f"Card {state}",
        )
        logger.info("Card %d %s", card_id, state)

        # Trigger enrichment on approval (ENRCH-01)
        if state == "approved":
            try:
                from watchman.enrichment.pipeline import enrich_approved_card  # noqa: PLC0415

                asyncio.run(enrich_approved_card(card_id, db_path))
                logger.info("Enrichment completed for card %d", card_id)
            except Exception:
                logger.exception(
                    "Enrichment failed for card %d (will retry via fallback job)",
                    card_id,
                )
    except Exception:
        logger.exception("Failed to %s card %d", state, card_id)
        _post_error_ephemeral(
            client,
            body,
            f"Failed to {state} the card. Please try again.",
        )


def _handle_snooze_action(body: dict, client) -> None:  # noqa: ANN001
    """Snooze a card for 30 days and update the Slack message.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
    """
    action = body["actions"][0]
    card_id = int(action["value"])
    message = body.get("message", {})
    channel_id = body["channel"]["id"]
    message_ts = message.get("ts", "")

    db_path = _get_db_path()

    async def _update() -> None:
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.snooze_card(card_id, days=30)
            card = await _load_card_by_id(repo, card_id)
            if card is None:
                raise ValueError(f"Card {card_id} not found after snooze")
            return card

    try:
        card = asyncio.run(_update())
        confirmed_blocks = build_confirmed_card_blocks(card, "snoozed")
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=confirmed_blocks,
            text="Card snoozed for 30 days",
        )
        logger.info("Card %d snoozed for 30 days", card_id)
    except Exception:
        logger.exception("Failed to snooze card %d", card_id)
        _post_error_ephemeral(
            client,
            body,
            "Failed to snooze the card. Please try again.",
        )


def _handle_details_action(body: dict, client) -> None:  # noqa: ANN001
    """Show a 4-dimension score breakdown as an ephemeral message.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
    """
    action = body["actions"][0]
    card_id = int(action["value"])
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    db_path = _get_db_path()

    async def _load():  # noqa: ANN202
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            card = await _load_card_by_id(repo, card_id)
            return card

    try:
        card = asyncio.run(_load())
        if card is None:
            raise ValueError(f"Card {card_id} not found")

        if card.score_breakdown is None:
            raise ValueError(f"Card {card_id} has no score breakdown")

        score = RubricScore.model_validate_json(card.score_breakdown)
        details_blocks = build_details_blocks(card, score)

        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=details_blocks,
            text=f"Score details for: {card.title}",
        )
        logger.info("Posted details for card %d to user %s", card_id, user_id)
    except Exception:
        logger.exception("Failed to show details for card %d", card_id)
        _post_error_ephemeral(
            client,
            body,
            "Failed to load card details. Please try again.",
        )


async def _load_card_by_id(repo: CardRepository, card_id: int):  # noqa: ANN201
    """Load a card by ID using a linear scan (no direct find_by_id query).

    Fetches cards from the repository in a minimal way. Since CardRepository
    doesn't expose find_by_id, we use a direct DB query via the connection.

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


def _post_error_ephemeral(client, body: dict, message: str) -> None:  # noqa: ANN001
    """Post an ephemeral error message to the acting user.

    Args:
        client: Slack WebClient for API calls.
        body: Slack action payload (for channel and user IDs).
        message: Error message to display.
    """
    try:
        client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=body["user"]["id"],
            text=message,
        )
    except Exception:
        logger.exception("Failed to post ephemeral error message")


def register_gate2_actions(app: App) -> None:
    """Register Gate 2 Slack action handlers on the Bolt App.

    Registers handlers for: approve_gate2, reject_gate2, re_enrich.

    Args:
        app: Configured Bolt App to register handlers on.
    """

    @app.action("approve_gate2")
    def handle_approve_gate2(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Gate 2 Approve button click."""
        ack()
        _handle_gate2_approve(body, client)

    @app.action("reject_gate2")
    def handle_reject_gate2(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Gate 2 Reject button click."""
        ack()
        _handle_gate2_reject(body, client)

    @app.action("re_enrich")
    def handle_re_enrich(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the Re-enrich button click."""
        ack()
        _handle_re_enrich_action(body, client)


def _handle_gate2_approve(body: dict, client) -> None:  # noqa: ANN001
    """Approve at Gate 2: update state, write JSON output, update Slack message.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
    """
    action = body["actions"][0]
    card_id = int(action["value"])
    message = body.get("message", {})
    channel_id = body["channel"]["id"]
    message_ts = message.get("ts", "")

    db_path = _get_db_path()

    async def _update():  # noqa: ANN202
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.set_gate2_state(card_id, "gate2_approved", slack_ts=message_ts)
            card = await _load_card_by_id(repo, card_id)
            if card is None:
                raise ValueError(f"Card {card_id} not found after Gate 2 approval")
            return card

    try:
        card = asyncio.run(_update())

        # Write JSON output file (OUT-03)
        if card.enrichment_data:
            entry = IcebreakerToolEntry.model_validate_json(card.enrichment_data)
            output_path = write_tool_entry(entry, card_id)

            async def _save_path():  # noqa: ANN202
                async with get_connection(db_path) as db:
                    repo = CardRepository(db)
                    await repo.save_output_path(card_id, str(output_path))

            asyncio.run(_save_path())
            logger.info("Gate 2 approved card %d, output: %s", card_id, output_path)

        confirmed_blocks = build_gate2_confirmed_blocks(card, "gate2_approved")
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=confirmed_blocks,
            text="Gate 2: Approved",
        )
    except Exception:
        logger.exception("Failed to approve card %d at Gate 2", card_id)
        _post_error_ephemeral(
            client, body, "Failed to approve the enriched entry. Please try again."
        )


def _handle_gate2_reject(body: dict, client) -> None:  # noqa: ANN001
    """Reject at Gate 2: update state, update Slack message. No output file.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
    """
    action = body["actions"][0]
    card_id = int(action["value"])
    message = body.get("message", {})
    channel_id = body["channel"]["id"]
    message_ts = message.get("ts", "")

    db_path = _get_db_path()

    async def _update():  # noqa: ANN202
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            await repo.set_gate2_state(
                card_id, "gate2_rejected", slack_ts=message_ts
            )
            card = await _load_card_by_id(repo, card_id)
            if card is None:
                raise ValueError(f"Card {card_id} not found after Gate 2 rejection")
            return card

    try:
        card = asyncio.run(_update())
        confirmed_blocks = build_gate2_confirmed_blocks(card, "gate2_rejected")
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=confirmed_blocks,
            text="Gate 2: Rejected",
        )
        logger.info("Gate 2 rejected card %d", card_id)
    except Exception:
        logger.exception("Failed to reject card %d at Gate 2", card_id)
        _post_error_ephemeral(
            client, body, "Failed to reject the enriched entry. Please try again."
        )


def _handle_re_enrich_action(body: dict, client) -> None:  # noqa: ANN001
    """Re-enrich a card: check retry cap, reset state, trigger enrichment.

    Re-enrichment is capped at 2 retries (3 total enrichment attempts per signal).
    After max retries exhausted, posts an ephemeral message instead.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
    """
    action = body["actions"][0]
    card_id = int(action["value"])
    message = body.get("message", {})
    channel_id = body["channel"]["id"]
    message_ts = message.get("ts", "")

    db_path = _get_db_path()

    # Check current attempt count
    async def _check_and_prepare():  # noqa: ANN202
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            card = await _load_card_by_id(repo, card_id)
            if card is None:
                raise ValueError(f"Card {card_id} not found")
            return card

    try:
        card = asyncio.run(_check_and_prepare())

        if (card.enrichment_attempt_count or 1) >= 3:
            _post_error_ephemeral(
                client,
                body,
                "Max re-enrichment attempts reached (3 total). Only Approve or Reject available.",
            )
            return

        # Increment attempt count and reset states for re-enrichment
        async def _reset_for_re_enrich():  # noqa: ANN202
            async with get_connection(db_path) as db:
                repo = CardRepository(db)
                await repo.increment_enrichment_attempt(card_id)
                await repo.set_enrichment_state(card_id, "pending")
                await repo.set_gate2_state(card_id, "pending")

        asyncio.run(_reset_for_re_enrich())

        # Update Slack message to show re-enriching status
        confirmed_blocks = build_gate2_confirmed_blocks(card, "re_enriching")
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=confirmed_blocks,
            text="Sent for re-enrichment",
        )
        logger.info("Re-enrichment triggered for card %d", card_id)

        # Trigger re-enrichment (same as Gate 1 approval flow)
        try:
            from watchman.enrichment.pipeline import enrich_approved_card  # noqa: PLC0415

            asyncio.run(enrich_approved_card(card_id, db_path))
            logger.info("Re-enrichment completed for card %d", card_id)
        except Exception:
            logger.exception(
                "Re-enrichment failed for card %d (will retry via fallback job)",
                card_id,
            )
    except Exception:
        logger.exception("Failed to re-enrich card %d", card_id)
        _post_error_ephemeral(
            client, body, "Failed to trigger re-enrichment. Please try again."
        )


def register_view_more_action(app: App) -> None:
    """Register the 'View More Signals' pagination action handler.

    Responds to the view_more_signals button by fetching and posting the
    next batch of scored cards, then showing an updated footer.

    Args:
        app: Configured Bolt App to register the handler on.
    """

    @app.action("view_more_signals")
    def handle_view_more(ack, body, client, logger):  # noqa: ANN001, ANN202
        """Handle the View More Signals button click."""
        ack()
        _handle_view_more_signals(body, client)


def _handle_view_more_signals(body: dict, client) -> None:  # noqa: ANN001
    """Fetch the next batch of scored cards and post them to the channel.

    Parses offset from the button value, fetches up to PAGE_SIZE cards,
    posts each as a signal card with review buttons, then posts an updated
    footer with a new "View More" button if cards remain.

    Args:
        body: Slack action payload.
        client: Slack WebClient for API calls.
    """
    PAGE_SIZE = 5

    action = body["actions"][0]
    payload = json.loads(action["value"])
    offset = int(payload["offset"])
    channel_id = body["channel"]["id"]

    db_path = _get_db_path()

    async def _fetch_batch():  # noqa: ANN202
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            cards = await repo.find_next_scored_batch(offset=offset, limit=PAGE_SIZE)
            total = await repo.count_scored_today()
            return cards, total

    try:
        cards, total = asyncio.run(_fetch_batch())

        delivered = 0
        for card in cards:
            if card.score_breakdown is None:
                logger.warning("Card %d has no score_breakdown, skipping", card.id)
                continue

            try:
                score = RubricScore.model_validate_json(card.score_breakdown)
            except Exception:
                logger.exception(
                    "Failed to parse score for card %d, skipping", card.id
                )
                continue

            blocks = build_signal_card_blocks(card, score)

            response = client.chat_postMessage(
                channel=channel_id,
                blocks=blocks,
                text=f"Signal: {card.title}",
            )

            # Save slack_message_ts so action handlers can update the message
            message_ts = response.get("ts")

            async def _save_review_state(
                card_id: int, ts: str, ch: str
            ) -> None:
                async with get_connection(db_path) as db:
                    repo = CardRepository(db)
                    await repo.set_review_state(
                        card_id, "pending", slack_ts=ts, slack_channel=ch
                    )

            asyncio.run(_save_review_state(card.id, message_ts, channel_id))
            delivered += 1

        total_shown = offset + delivered
        footer_blocks = build_review_footer(total_shown, total)
        client.chat_postMessage(
            channel=channel_id,
            blocks=footer_blocks,
            text=f"Showing {total_shown} of {total} signals today",
        )

        logger.info(
            "View More: delivered %d cards (offset=%d, total_shown=%d, total=%d)",
            delivered,
            offset,
            total_shown,
            total,
        )
    except Exception:
        logger.exception("Failed to handle view_more_signals action")
        _post_error_ephemeral(
            client,
            body,
            "Failed to load more signals. Please try again.",
        )
