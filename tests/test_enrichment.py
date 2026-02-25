"""Tests for the enrichment pipeline: scraper, extractor, and pipeline orchestrator."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from watchman.enrichment.extractor import _build_enrichment_prompt
from watchman.enrichment.scraper import scrape_url
from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.models.signal_card import SignalCard
from watchman.storage.database import init_db, get_connection
from watchman.storage.repositories import CardRepository


@pytest.fixture
def tmp_db(tmp_path: Path):
    """Create a temporary SQLite database with all migrations applied."""
    db_path = tmp_path / "test.db"
    asyncio.run(init_db(db_path))
    return db_path


@pytest.fixture
def sample_card() -> SignalCard:
    """Create a sample signal card for testing."""
    return SignalCard(
        title="TestAI - AI Development Platform",
        source_name="hacker-news",
        date=datetime(2026, 2, 24),
        url="https://testai.example.com",
        tier=2,
        summary="A new AI development platform with REST API and Slack integration",
        collector_type="api",
        url_hash=SignalCard.compute_url_hash("https://testai.example.com"),
        content_fingerprint=SignalCard.compute_content_fingerprint(
            "TestAI - AI Development Platform", datetime(2026, 2, 24)
        ),
        review_state="approved",
        relevance_score=0.85,
    )


def _make_valid_entry_json() -> str:
    """Create a valid IcebreakerToolEntry JSON string for mocking."""
    entry = IcebreakerToolEntry(
        name="TestAI",
        description="An AI development platform",
        capabilities=["code generation", "debugging"],
        pricing="freemium",
        api_surface="REST API with Python SDK",
        integration_hooks=["Slack", "GitHub"],
        source_url="https://testai.example.com",
        discovered_at=datetime(2026, 2, 24),
    )
    return entry.model_dump_json()


# --- Prompt building tests ---


@pytest.mark.unit
def test_build_enrichment_prompt_with_content():
    """Prompt includes card info and page content when content is provided."""
    prompt = _build_enrichment_prompt(
        card_title="TestTool",
        card_url="https://example.com",
        card_summary="A test tool for testing",
        page_content="TestTool is a comprehensive testing platform with features X, Y, Z.",
    )
    assert "TestTool" in prompt
    assert "https://example.com" in prompt
    assert "A test tool for testing" in prompt
    assert "comprehensive testing platform" in prompt
    assert "Do NOT infer or fabricate" in prompt


@pytest.mark.unit
def test_build_enrichment_prompt_fallback():
    """Prompt handles None page_content with fallback messaging."""
    prompt = _build_enrichment_prompt(
        card_title="TestTool",
        card_url="https://example.com",
        card_summary="A test tool",
        page_content=None,
    )
    assert "TestTool" in prompt
    assert "https://example.com" in prompt
    assert "could not be scraped" in prompt


# --- Scraper tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_url_returns_none_on_failure():
    """scrape_url returns None (not raises) on HTTP failure."""
    with patch("watchman.enrichment.scraper.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scrape_url("https://example.com")
        assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_url_returns_none_on_empty_extraction():
    """scrape_url returns None when trafilatura extracts nothing."""
    with (
        patch("watchman.enrichment.scraper.httpx.AsyncClient") as mock_client_cls,
        patch("watchman.enrichment.scraper.trafilatura.extract", return_value=None),
    ):
        mock_response = MagicMock()
        mock_response.text = "<html><body>empty</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scrape_url("https://example.com")
        assert result is None


# --- Extractor tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_card_returns_validated_entry():
    """enrich_card returns a validated IcebreakerToolEntry from mocked API."""
    from watchman.enrichment.extractor import enrich_card

    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = _make_valid_entry_json()
    mock_response.content = [mock_content]

    with patch("watchman.enrichment.extractor.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        entry = await enrich_card(
            card_title="TestAI",
            card_url="https://testai.example.com",
            card_summary="An AI platform",
            page_content="TestAI is an AI development platform.",
        )

        assert isinstance(entry, IcebreakerToolEntry)
        assert entry.name == "TestAI"
        assert entry.source_url == "https://testai.example.com"
        assert len(entry.capabilities) > 0


# --- Pipeline tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrich_approved_card_guards_review_state(tmp_db: Path, sample_card: SignalCard):
    """Pipeline refuses to enrich cards that are not approved."""
    from watchman.enrichment.pipeline import enrich_approved_card

    # Insert a pending (not approved) card
    pending_card = sample_card.model_copy(update={"review_state": "pending"})

    async with get_connection(tmp_db) as db:
        repo = CardRepository(db)
        card_id = await repo.insert(pending_card)

    with patch("watchman.enrichment.pipeline.enrich_card") as mock_enrich:
        result = await enrich_approved_card(card_id, tmp_db)
        assert result is None
        mock_enrich.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrich_approved_card_handles_scrape_failure(tmp_db: Path, sample_card: SignalCard):
    """Pipeline completes enrichment even when scraping fails (fallback)."""
    from watchman.enrichment.pipeline import enrich_approved_card

    async with get_connection(tmp_db) as db:
        repo = CardRepository(db)
        card_id = await repo.insert(sample_card)
        await repo.set_review_state(card_id, "approved")

    mock_entry = IcebreakerToolEntry(
        name="TestAI",
        description="An AI platform",
        capabilities=["code generation"],
        source_url="https://testai.example.com",
        discovered_at=datetime.now(timezone.utc),
    )

    with (
        patch("watchman.enrichment.pipeline.scrape_url", return_value=None) as mock_scrape,
        patch("watchman.enrichment.pipeline.enrich_card", return_value=mock_entry) as mock_enrich,
    ):
        result = await enrich_approved_card(card_id, tmp_db)
        assert result is not None
        assert result.name == "TestAI"
        mock_scrape.assert_called_once()
        # Verify None was passed as page_content (fallback)
        call_args = mock_enrich.call_args
        assert call_args[1].get("page_content") is None or call_args[0][3] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enrichment_state_tracking(tmp_db: Path, sample_card: SignalCard):
    """Pipeline transitions enrichment_state from pending to complete and stores data."""
    from watchman.enrichment.pipeline import enrich_approved_card

    async with get_connection(tmp_db) as db:
        repo = CardRepository(db)
        card_id = await repo.insert(sample_card)
        await repo.set_review_state(card_id, "approved")

    mock_entry = IcebreakerToolEntry(
        name="TestAI",
        description="An AI platform",
        capabilities=["code generation"],
        source_url="https://testai.example.com",
        discovered_at=datetime.now(timezone.utc),
    )

    with (
        patch("watchman.enrichment.pipeline.scrape_url", return_value="page content here"),
        patch("watchman.enrichment.pipeline.enrich_card", return_value=mock_entry),
    ):
        result = await enrich_approved_card(card_id, tmp_db)
        assert result is not None

    # Verify state was updated in database
    async with get_connection(tmp_db) as db:
        repo = CardRepository(db)
        async with db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)) as cur:
            row = await cur.fetchone()
            card = CardRepository._row_to_card(row)
            assert card.enrichment_state == "complete"
            assert card.enrichment_data is not None
            assert card.enriched_at is not None

            # Verify stored data is valid JSON matching the entry
            stored_entry = IcebreakerToolEntry.model_validate_json(card.enrichment_data)
            assert stored_entry.name == "TestAI"
