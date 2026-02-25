"""Block Kit builder functions for Slack signal card messages."""
from __future__ import annotations

from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.models.signal_card import SignalCard
from watchman.scoring.models import RubricScore

# Human-readable labels for each rubric dimension
DIMENSION_LABELS: dict[str, str] = {
    "taxonomy_fit": "strong taxonomy fit",
    "novel_capability": "novel capability",
    "adoption_traction": "strong adoption traction",
    "credibility": "high credibility",
}

TIER_BADGES: dict[int, str] = {
    1: ":star: Tier 1",
    2: ":large_blue_circle: Tier 2",
    3: ":white_circle: Tier 3",
}


def _format_score_line(score: RubricScore) -> str:
    """Format composite score and top dimension into a single display line.

    Args:
        score: RubricScore with composite_score and top_dimension.

    Returns:
        Formatted string like "8.2 -- strong taxonomy fit".
    """
    composite = f"{score.composite_score:.1f}"
    label = DIMENSION_LABELS.get(score.top_dimension, score.top_dimension)
    return f"{composite} -- {label}"


def build_signal_card_blocks(card: SignalCard, score: RubricScore) -> list[dict]:
    """Build Block Kit blocks for an unreviewed signal card.

    Creates a reviewable card with the card title (as a link), score line,
    source context, and four action buttons: Approve, Reject, Snooze 30d,
    and Details.

    Args:
        card: SignalCard to display.
        score: RubricScore for the card.

    Returns:
        List of Slack Block Kit block dicts.
    """
    card_id = str(card.id)
    tier_badge = TIER_BADGES.get(card.tier, f"Tier {card.tier}")
    date_str = card.date.strftime("%b %d, %Y")
    score_line = _format_score_line(score)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{card.url}|{card.title}>*\n:bar_chart: {score_line}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{tier_badge}  |  {card.source_name}  |  {date_str}",
                }
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_card",
                    "value": card_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject_card",
                    "value": card_id,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Snooze 30d",
                        "emoji": True,
                    },
                    "action_id": "snooze_card",
                    "value": card_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Details", "emoji": True},
                    "action_id": "details_card",
                    "value": card_id,
                },
            ],
        },
        {"type": "divider"},
    ]
    return blocks


def build_confirmed_card_blocks(card: SignalCard, action: str) -> list[dict]:
    """Build Block Kit blocks for a card after a review action was taken.

    Shows the card title and the result of the action. No action buttons
    are included (removed after the human acts).

    Args:
        card: SignalCard that was reviewed.
        action: One of "approved", "rejected", or "snoozed".

    Returns:
        List of Slack Block Kit block dicts (no action buttons).
    """
    action_display = {
        "approved": ":white_check_mark: Approved",
        "rejected": ":x: Rejected",
        "snoozed": ":alarm_clock: Snoozed for 30 days",
    }.get(action, action)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{card.url}|{card.title}>*\n{action_display}",
            },
        },
        {"type": "divider"},
    ]
    return blocks


def build_details_blocks(card: SignalCard, score: RubricScore) -> list[dict]:
    """Build Block Kit blocks showing the full 4-dimension rubric breakdown.

    Intended for use as an ephemeral message or appended to the card.

    Args:
        card: SignalCard being reviewed.
        score: RubricScore with per-dimension scores and rationales.

    Returns:
        List of Slack Block Kit block dicts with detailed rubric breakdown.
    """
    dimensions = [
        ("taxonomy_fit", "Taxonomy Fit", score.taxonomy_fit),
        ("novel_capability", "Novel Capability", score.novel_capability),
        ("adoption_traction", "Adoption Traction", score.adoption_traction),
        ("credibility", "Credibility", score.credibility),
    ]

    dimension_lines = []
    for _key, label, dim_score in dimensions:
        dimension_lines.append(
            f"*{label}:* {dim_score.score:.1f}/10\n_{dim_score.rationale}_"
        )

    breakdown_text = "\n\n".join(dimension_lines)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":mag: *Score Breakdown: <{card.url}|{card.title}>*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": breakdown_text,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Composite score: *{score.composite_score:.1f}*",
                }
            ],
        },
    ]
    return blocks


def build_review_footer(showing: int, total: int) -> list[dict]:
    """Build a Block Kit footer showing how many signals are in today's review.

    When total > showing, includes a "View More Signals" action button
    that carries the offset and remaining count as JSON value.

    Args:
        showing: Number of cards shown in this digest.
        total: Total number of scored cards created today.

    Returns:
        List of Slack Block Kit block dicts with the footer context
        and optional view-more button.
    """
    import json

    blocks: list[dict] = [
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":page_facing_up: Showing {showing} of {total} signals today",
                }
            ],
        }
    ]

    remaining = total - showing
    if remaining > 0:
        next_batch = min(remaining, 5)
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"View next {next_batch} signals ({remaining} remaining)",
                            "emoji": True,
                        },
                        "action_id": "view_more_signals",
                        "value": json.dumps(
                            {"offset": showing, "remaining": remaining}
                        ),
                    }
                ],
            }
        )

    return blocks


def build_gate2_card_blocks(
    card: SignalCard, entry: IcebreakerToolEntry, can_re_enrich: bool
) -> list[dict]:
    """Build Block Kit blocks for a Gate 2 enrichment review card.

    Shows enrichment details (name, description, capabilities, pricing, API)
    with approve/reject buttons and optional re-enrich button.
    Differentiated from Gate 1 by :mag: prefix and enrichment detail fields.

    Args:
        card: SignalCard with enrichment data.
        entry: Parsed IcebreakerToolEntry from enrichment.
        can_re_enrich: Whether the re-enrich button should be shown.

    Returns:
        List of Slack Block Kit block dicts.
    """
    card_id = str(card.id)

    capabilities_text = (
        "\n".join(f"- {c}" for c in entry.capabilities[:5])
        if entry.capabilities
        else "_None extracted_"
    )

    pricing_text = entry.pricing or "Unknown"
    api_text = entry.api_surface or "Unknown"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":mag: Gate 2 Review: {entry.name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{card.url}|{card.title}>*\n{entry.description}",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Capabilities:*\n{capabilities_text}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Pricing:* {pricing_text}\n*API:* {api_text}",
                },
            ],
        },
    ]

    if entry.integration_hooks:
        integrations = ", ".join(entry.integration_hooks)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":link: Integrations: {integrations}",
                    }
                ],
            }
        )

    action_buttons: list[dict] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Approve", "emoji": True},
            "style": "primary",
            "action_id": "approve_gate2",
            "value": card_id,
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Reject", "emoji": True},
            "style": "danger",
            "action_id": "reject_gate2",
            "value": card_id,
        },
    ]

    if can_re_enrich:
        action_buttons.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Re-enrich", "emoji": True},
                "action_id": "re_enrich",
                "value": card_id,
            }
        )

    blocks.append({"type": "actions", "elements": action_buttons})
    blocks.append({"type": "divider"})

    return blocks


def build_gate2_confirmed_blocks(card: SignalCard, action: str) -> list[dict]:
    """Build Block Kit blocks for a Gate 2 card after a review action was taken.

    Shows the card title and the result of the action. No action buttons
    are included (removed after the human acts).

    Args:
        card: SignalCard that was reviewed.
        action: One of "gate2_approved", "gate2_rejected", or "re_enriching".

    Returns:
        List of Slack Block Kit block dicts (no action buttons).
    """
    action_display = {
        "gate2_approved": ":white_check_mark: Approved (output written)",
        "gate2_rejected": ":x: Rejected",
        "re_enriching": ":arrows_counterclockwise: Sent for re-enrichment",
    }.get(action, action)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":mag: *<{card.url}|{card.title}>*\n{action_display}",
            },
        },
        {"type": "divider"},
    ]
    return blocks
