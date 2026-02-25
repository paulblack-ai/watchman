"""Tests for the view_more_signals action handler."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from watchman.models.signal_card import SignalCard
from watchman.scoring.models import DimensionScore, RubricScore
from watchman.slack.actions import _handle_view_more_signals
from watchman.slack.blocks import build_review_footer


def _make_score() -> RubricScore:
    """Create a valid RubricScore for testing."""
    dim = DimensionScore(score=7.0, rationale="test rationale")
    return RubricScore(
        taxonomy_fit=dim,
        novel_capability=dim,
        adoption_traction=dim,
        credibility=dim,
        composite_score=7.0,
        top_dimension="taxonomy_fit",
    )


def _make_card(card_id: int, *, has_score: bool = True) -> SignalCard:
    """Create a minimal SignalCard for testing."""
    score = _make_score() if has_score else None
    return SignalCard(
        id=card_id,
        title=f"Test Card {card_id}",
        source_name="TestSource",
        date=datetime.now(timezone.utc),
        url=f"https://example.com/{card_id}",
        tier=1,
        summary="Test summary",
        collector_type="rss",
        url_hash=f"hash{card_id}",
        content_fingerprint=f"fp{card_id}",
        duplicate_of=None,
        seen_count=1,
        created_at=datetime.now(timezone.utc),
        relevance_score=7.0 if has_score else None,
        score_breakdown=score.model_dump_json() if score else None,
        top_dimension="taxonomy_fit" if has_score else None,
    )


def _make_body(offset: int, remaining: int) -> dict:
    """Create a fake Slack action body payload."""
    return {
        "actions": [{"value": json.dumps({"offset": offset, "remaining": remaining})}],
        "channel": {"id": "C123"},
        "user": {"id": "U123"},
        "message": {"ts": "1234.5678"},
    }


@patch("watchman.slack.actions.get_connection")
def test_handle_view_more_posts_next_batch(mock_get_conn):
    """Clicking View More posts the next batch of cards plus a footer."""
    cards = [_make_card(6), _make_card(7), _make_card(8)]
    total = 13

    mock_db = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.find_next_scored_batch.return_value = cards
    mock_repo.count_scored_today.return_value = total
    mock_repo.set_review_state.return_value = None

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_db
    mock_get_conn.return_value = mock_ctx

    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "9999.0000"}

    body = _make_body(offset=5, remaining=8)

    with patch("watchman.slack.actions.CardRepository", return_value=mock_repo):
        _handle_view_more_signals(body, client)

    # 3 card posts + 1 footer = 4 calls
    assert client.chat_postMessage.call_count == 4

    # Last call is the footer
    footer_call = client.chat_postMessage.call_args_list[-1]
    footer_blocks = footer_call.kwargs.get("blocks") or footer_call[1].get("blocks")

    # total_shown = 5 + 3 = 8, total = 13, so button should appear
    has_button = any(
        block.get("type") == "actions" for block in footer_blocks
    )
    assert has_button, "Footer should have View More button when cards remain"


@patch("watchman.slack.actions.get_connection")
def test_handle_view_more_final_page_no_button(mock_get_conn):
    """When all cards have been shown, footer has no View More button."""
    cards = [_make_card(6), _make_card(7)]
    total = 7  # offset=5 + 2 cards = 7 == total

    mock_db = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.find_next_scored_batch.return_value = cards
    mock_repo.count_scored_today.return_value = total
    mock_repo.set_review_state.return_value = None

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_db
    mock_get_conn.return_value = mock_ctx

    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "9999.0000"}

    body = _make_body(offset=5, remaining=2)

    with patch("watchman.slack.actions.CardRepository", return_value=mock_repo):
        _handle_view_more_signals(body, client)

    # 2 card posts + 1 footer = 3 calls
    assert client.chat_postMessage.call_count == 3

    footer_call = client.chat_postMessage.call_args_list[-1]
    footer_blocks = footer_call.kwargs.get("blocks") or footer_call[1].get("blocks")

    has_button = any(
        block.get("type") == "actions" for block in footer_blocks
    )
    assert not has_button, "Footer should NOT have View More button on final page"


@patch("watchman.slack.actions.get_connection")
def test_handle_view_more_skips_cards_without_score(mock_get_conn):
    """Cards with no score_breakdown are silently skipped."""
    cards = [_make_card(6, has_score=True), _make_card(7, has_score=False)]
    total = 7

    mock_db = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.find_next_scored_batch.return_value = cards
    mock_repo.count_scored_today.return_value = total
    mock_repo.set_review_state.return_value = None

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_db
    mock_get_conn.return_value = mock_ctx

    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "9999.0000"}

    body = _make_body(offset=5, remaining=2)

    with patch("watchman.slack.actions.CardRepository", return_value=mock_repo):
        _handle_view_more_signals(body, client)

    # 1 card post (skipped the one without score) + 1 footer = 2 calls
    assert client.chat_postMessage.call_count == 2
