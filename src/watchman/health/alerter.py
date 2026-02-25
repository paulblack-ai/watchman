"""Slack DM alerting for source health issues."""
from __future__ import annotations

import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# Suggested actions by source type
ACTION_SUGGESTIONS: dict[str, str] = {
    "rss": "Check if the feed URL has changed or the site is down",
    "api": "Check if the API key has expired or the endpoint has moved",
    "scrape": "Check if the page structure or CSS selectors have changed",
}


def send_health_alert(
    token: str,
    user_id: str,
    source_name: str,
    source_type: str,
    consecutive_zeros: int,
) -> bool:
    """Send a health alert as a Slack DM to Paul.

    Args:
        token: Slack bot OAuth token.
        user_id: Paul's Slack user ID for DM delivery.
        source_name: Name of the failing source.
        source_type: Type of the source (rss/api/scrape).
        consecutive_zeros: Number of consecutive zero-yield runs.

    Returns:
        True if message sent successfully, False otherwise.
    """
    suggestion = ACTION_SUGGESTIONS.get(
        source_type, "Check the source configuration"
    )

    message = (
        f"*Source Health Alert*\n\n"
        f"Source *{source_name}* has returned zero results "
        f"for {consecutive_zeros} consecutive runs.\n\n"
        f"*Suggested action:* {suggestion}"
    )

    try:
        client = WebClient(token=token)
        client.chat_postMessage(channel=user_id, text=message)
        return True
    except SlackApiError:
        logger.exception("Failed to send Slack health alert for '%s'", source_name)
        return False


def send_daily_digest(
    token: str,
    user_id: str,
    failing_sources: list[dict],
) -> bool:
    """Send a daily digest of all failing sources as a Slack DM.

    Args:
        token: Slack bot OAuth token.
        user_id: Paul's Slack user ID for DM delivery.
        failing_sources: List of dicts with source_name, consecutive_zeros, last_error.

    Returns:
        True if message sent successfully, False otherwise.
    """
    if not failing_sources:
        return True

    lines = ["*Daily Source Health Digest*\n"]
    for source in failing_sources:
        name = source["source_name"]
        zeros = source["consecutive_zeros"]
        error = source.get("last_error") or "No error details"
        lines.append(f"- *{name}*: {zeros} consecutive zero runs ({error})")

    lines.append(f"\n_{len(failing_sources)} source(s) need attention._")

    message = "\n".join(lines)

    try:
        client = WebClient(token=token)
        client.chat_postMessage(channel=user_id, text=message)
        return True
    except SlackApiError:
        logger.exception("Failed to send daily health digest")
        return False
