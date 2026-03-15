"""Tests for Notion poller: select property reading and query filter syntax."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from watchman.notion.poller import _extract_status_name, poll_notion_status


# ---------------------------------------------------------------------------
# Unit tests for _extract_status_name
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_status_name_from_select_property() -> None:
    """_extract_status_name returns name from a select-type property."""
    page = {
        "properties": {
            "Review Status": {
                "type": "select",
                "select": {"name": "Approved", "id": "abc", "color": "green"},
            }
        }
    }
    assert _extract_status_name(page, "Review Status") == "Approved"


@pytest.mark.unit
def test_extract_status_name_from_status_property_fallback() -> None:
    """_extract_status_name falls back to status type when select is absent."""
    page = {
        "properties": {
            "Gate 2": {
                "type": "status",
                "status": {"name": "Not Started", "id": "def", "color": "default"},
            }
        }
    }
    assert _extract_status_name(page, "Gate 2") == "Not Started"


@pytest.mark.unit
def test_extract_status_name_returns_none_when_property_missing() -> None:
    """_extract_status_name returns None when the named property is absent."""
    page = {"properties": {}}
    assert _extract_status_name(page, "Review Status") is None


@pytest.mark.unit
def test_extract_status_name_returns_none_when_no_select_or_status_value() -> None:
    """_extract_status_name returns None when property has neither select nor status."""
    page = {
        "properties": {
            "Review Status": {
                "type": "text",
                "rich_text": [],
            }
        }
    }
    assert _extract_status_name(page, "Review Status") is None


@pytest.mark.unit
def test_extract_status_name_prefers_select_over_status() -> None:
    """_extract_status_name uses select value when both select and status are present."""
    page = {
        "properties": {
            "Review Status": {
                "type": "select",
                "select": {"name": "Approved"},
                "status": {"name": "To Review"},
            }
        }
    }
    assert _extract_status_name(page, "Review Status") == "Approved"


# ---------------------------------------------------------------------------
# Integration tests for poll_notion_status query filter and downstream actions
# ---------------------------------------------------------------------------


def _make_select_page(
    notion_page_id: str,
    review_status: str = "To Review",
    gate2_status: str = "Not Started",
) -> dict:
    """Build a mock Notion page with select-type Review Status and Gate 2."""
    return {
        "id": notion_page_id,
        "properties": {
            "Review Status": {
                "type": "select",
                "select": {"name": review_status},
            },
            "Gate 2": {
                "type": "select",
                "select": {"name": gate2_status},
            },
        },
    }


@pytest.mark.unit
def test_poll_notion_status_query_uses_select_filter(tmp_path: Path) -> None:
    """poll_notion_status passes select filter syntax to query_database."""
    db_path = tmp_path / "test.db"

    mock_client = MagicMock()
    mock_client.query_database.return_value = []

    with (
        patch("watchman.notion.poller.NotionClient", return_value=mock_client),
        patch.dict(
            "os.environ",
            {"NOTION_TOKEN": "test-token", "NOTION_DATABASE_ID": "test-db-id"},
        ),
    ):
        asyncio.run(poll_notion_status(db_path))

    call_args = mock_client.query_database.call_args
    assert call_args is not None, "query_database was not called"

    filter_arg = call_args.kwargs.get("filter") or call_args.args[0]
    or_conditions = filter_arg["or"]

    # Both conditions must use "select" not "status"
    for condition in or_conditions:
        prop = condition["property"]
        assert "select" in condition, (
            f"Filter for '{prop}' uses wrong key: expected 'select', "
            f"got {list(condition.keys())}"
        )
        assert "status" not in condition, (
            f"Filter for '{prop}' must not contain 'status'"
        )


@pytest.mark.unit
def test_poll_notion_status_approved_triggers_enrichment(tmp_path: Path) -> None:
    """Approved Review Status from select property triggers enrichment pipeline."""
    from datetime import datetime
    from watchman.models.signal_card import SignalCard

    db_path = tmp_path / "test.db"
    from watchman.storage.database import init_db
    asyncio.run(init_db(db_path))

    # Insert a card with notion_page_id
    notion_page_id = "page-approved-123"

    async def _insert() -> int:
        from watchman.storage.database import get_connection
        from watchman.storage.repositories import CardRepository
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            card = SignalCard(
                title="Test Card",
                source_name="test-source",
                date=datetime(2026, 3, 14),
                url="http://example.com/test",
                tier=1,
                summary="Test summary",
                collector_type="rss",
                url_hash="hash-approved-123",
                review_state="pending",
            )
            card_id = await repo.insert(card)
            await db.execute(
                "UPDATE cards SET notion_page_id = ? WHERE id = ?",
                (notion_page_id, card_id),
            )
            await db.commit()
            return card_id

    card_id = asyncio.run(_insert())

    approved_page = _make_select_page(notion_page_id, review_status="Approved")
    mock_client = MagicMock()
    mock_client.query_database.return_value = [approved_page]

    with (
        patch("watchman.notion.poller.NotionClient", return_value=mock_client),
        patch.dict(
            "os.environ",
            {"NOTION_TOKEN": "test-token", "NOTION_DATABASE_ID": "test-db-id"},
        ),
        patch(
            "watchman.enrichment.pipeline.enrich_approved_card",
            new_callable=AsyncMock,
        ) as mock_enrich,
    ):
        changes = asyncio.run(poll_notion_status(db_path))

    assert changes == 1

    # Verify review_state updated to "approved" in SQLite
    async def _check_state() -> str:
        from watchman.storage.database import get_connection
        async with get_connection(db_path) as db:
            async with db.execute(
                "SELECT review_state FROM cards WHERE id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row["review_state"]

    review_state = asyncio.run(_check_state())
    assert review_state == "approved", f"Expected 'approved', got '{review_state}'"


@pytest.mark.unit
def test_poll_notion_status_snoozed_triggers_snooze(tmp_path: Path) -> None:
    """Snoozed Review Status from select property triggers 30-day snooze."""
    from datetime import datetime
    from watchman.models.signal_card import SignalCard

    db_path = tmp_path / "test.db"
    from watchman.storage.database import init_db
    asyncio.run(init_db(db_path))

    notion_page_id = "page-snoozed-456"

    async def _insert() -> int:
        from watchman.storage.database import get_connection
        from watchman.storage.repositories import CardRepository
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            card = SignalCard(
                title="Snoozeable Card",
                source_name="test-source",
                date=datetime(2026, 3, 14),
                url="http://example.com/snoozeable",
                tier=2,
                summary="A card to snooze",
                collector_type="rss",
                url_hash="hash-snoozed-456",
                review_state="pending",
            )
            card_id = await repo.insert(card)
            await db.execute(
                "UPDATE cards SET notion_page_id = ? WHERE id = ?",
                (notion_page_id, card_id),
            )
            await db.commit()
            return card_id

    card_id = asyncio.run(_insert())

    snoozed_page = _make_select_page(notion_page_id, review_status="Snoozed")
    mock_client = MagicMock()
    mock_client.query_database.return_value = [snoozed_page]
    mock_client.update_page.return_value = None

    with (
        patch("watchman.notion.poller.NotionClient", return_value=mock_client),
        patch.dict(
            "os.environ",
            {"NOTION_TOKEN": "test-token", "NOTION_DATABASE_ID": "test-db-id"},
        ),
    ):
        changes = asyncio.run(poll_notion_status(db_path))

    assert changes == 1

    # Verify review_state updated to "snoozed" in SQLite
    async def _check_state() -> str:
        from watchman.storage.database import get_connection
        async with get_connection(db_path) as db:
            async with db.execute(
                "SELECT review_state FROM cards WHERE id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row["review_state"]

    review_state = asyncio.run(_check_state())
    assert review_state == "snoozed", f"Expected 'snoozed', got '{review_state}'"
