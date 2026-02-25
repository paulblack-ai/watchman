"""Tests for Gate 2 review flow: Block Kit cards, state transitions, retry cap."""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from watchman.models.icebreaker import IcebreakerToolEntry
from watchman.models.signal_card import SignalCard
from watchman.slack.blocks import (
    build_gate2_card_blocks,
    build_gate2_confirmed_blocks,
)
from watchman.storage.database import get_connection, init_db
from watchman.storage.repositories import CardRepository


@pytest.fixture()
def sample_entry() -> IcebreakerToolEntry:
    """Create a sample IcebreakerToolEntry for testing."""
    return IcebreakerToolEntry(
        name="TestTool",
        description="A test tool for AI workflows",
        capabilities=["code generation", "chat", "embeddings"],
        pricing="freemium",
        api_surface="REST API with Python SDK",
        integration_hooks=["Slack", "GitHub"],
        source_url="http://testtool.com",
        discovered_at=datetime(2026, 2, 24),
    )


@pytest.fixture()
def sample_card() -> SignalCard:
    """Create a sample SignalCard for testing."""
    return SignalCard(
        id=1,
        title="TestTool Launch",
        source_name="test-source",
        date=datetime(2026, 2, 24),
        url="http://testtool.com",
        tier=1,
        summary="A new AI tool launched",
        collector_type="rss",
        url_hash="abc123",
        enrichment_state="complete",
        review_state="approved",
    )


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temp SQLite DB with all migrations applied."""
    db_path = tmp_path / "test.db"
    asyncio.run(init_db(db_path))
    return db_path


def _insert_enriched_card(
    db_path: Path,
    entry: IcebreakerToolEntry,
    enrichment_attempt_count: int = 1,
    gate2_state: str = "pending",
) -> int:
    """Insert a card with enrichment data and return its ID."""

    async def _insert() -> int:
        async with get_connection(db_path) as db:
            repo = CardRepository(db)
            card = SignalCard(
                title="TestTool Launch",
                source_name="test-source",
                date=datetime(2026, 2, 24),
                url="http://testtool.com",
                tier=1,
                summary="A new AI tool",
                collector_type="rss",
                url_hash=f"hash_{datetime.now().timestamp()}",
                review_state="approved",
                enrichment_state="complete",
                enrichment_data=entry.model_dump_json(),
            )
            card_id = await repo.insert(card)
            # Set enrichment_state and enrichment_data via direct update
            await db.execute(
                """UPDATE cards
                   SET enrichment_state = 'complete',
                       enrichment_data = ?,
                       enrichment_attempt_count = ?,
                       gate2_state = ?
                   WHERE id = ?""",
                (entry.model_dump_json(), enrichment_attempt_count, gate2_state, card_id),
            )
            await db.commit()
            return card_id

    return asyncio.run(_insert())


# --- Unit Tests ---


@pytest.mark.unit
def test_build_gate2_card_with_re_enrich(
    sample_card: SignalCard, sample_entry: IcebreakerToolEntry
) -> None:
    """Gate 2 blocks with can_re_enrich=True include all three action buttons."""
    blocks = build_gate2_card_blocks(sample_card, sample_entry, can_re_enrich=True)
    block_str = str(blocks)
    assert "approve_gate2" in block_str
    assert "reject_gate2" in block_str
    assert "re_enrich" in block_str


@pytest.mark.unit
def test_build_gate2_card_without_re_enrich(
    sample_card: SignalCard, sample_entry: IcebreakerToolEntry
) -> None:
    """Gate 2 blocks with can_re_enrich=False hide the re-enrich button."""
    blocks = build_gate2_card_blocks(sample_card, sample_entry, can_re_enrich=False)
    block_str = str(blocks)
    assert "approve_gate2" in block_str
    assert "reject_gate2" in block_str
    assert "re_enrich" not in block_str


@pytest.mark.unit
def test_build_gate2_card_shows_enrichment_details(
    sample_card: SignalCard, sample_entry: IcebreakerToolEntry
) -> None:
    """Gate 2 blocks display entry name, description, and capabilities."""
    blocks = build_gate2_card_blocks(sample_card, sample_entry, can_re_enrich=True)
    block_str = str(blocks)
    assert sample_entry.name in block_str
    assert sample_entry.description in block_str
    assert "code generation" in block_str


@pytest.mark.unit
def test_build_gate2_confirmed_approved(sample_card: SignalCard) -> None:
    """Gate 2 confirmed blocks for approval show 'Approved' text."""
    blocks = build_gate2_confirmed_blocks(sample_card, "gate2_approved")
    block_str = str(blocks)
    assert "Approved" in block_str


@pytest.mark.unit
def test_build_gate2_confirmed_rejected(sample_card: SignalCard) -> None:
    """Gate 2 confirmed blocks for rejection show 'Rejected' text."""
    blocks = build_gate2_confirmed_blocks(sample_card, "gate2_rejected")
    block_str = str(blocks)
    assert "Rejected" in block_str


@pytest.mark.unit
def test_build_gate2_confirmed_re_enriching(sample_card: SignalCard) -> None:
    """Gate 2 confirmed blocks for re-enrichment show re-enrichment text."""
    blocks = build_gate2_confirmed_blocks(sample_card, "re_enriching")
    block_str = str(blocks)
    assert "re-enrichment" in block_str


# --- Integration Tests ---


@pytest.mark.integration
def test_gate2_approve_updates_state(
    tmp_db: Path, sample_entry: IcebreakerToolEntry
) -> None:
    """Gate 2 approval updates gate2_state and sets gate2_reviewed_at."""
    card_id = _insert_enriched_card(tmp_db, sample_entry)

    async def _test() -> None:
        async with get_connection(tmp_db) as db:
            repo = CardRepository(db)
            await repo.set_gate2_state(card_id, "gate2_approved")

            async with db.execute(
                "SELECT * FROM cards WHERE id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                card = CardRepository._row_to_card(row)

        assert card.gate2_state == "gate2_approved"
        assert card.gate2_reviewed_at is not None

    asyncio.run(_test())


@pytest.mark.integration
def test_gate2_reject_updates_state(
    tmp_db: Path, sample_entry: IcebreakerToolEntry
) -> None:
    """Gate 2 rejection updates gate2_state to gate2_rejected."""
    card_id = _insert_enriched_card(tmp_db, sample_entry)

    async def _test() -> None:
        async with get_connection(tmp_db) as db:
            repo = CardRepository(db)
            await repo.set_gate2_state(card_id, "gate2_rejected")

            async with db.execute(
                "SELECT * FROM cards WHERE id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                card = CardRepository._row_to_card(row)

        assert card.gate2_state == "gate2_rejected"

    asyncio.run(_test())


@pytest.mark.integration
def test_enrichment_attempt_increment(
    tmp_db: Path, sample_entry: IcebreakerToolEntry
) -> None:
    """Incrementing enrichment attempt count works correctly."""
    card_id = _insert_enriched_card(tmp_db, sample_entry)

    async def _test() -> None:
        async with get_connection(tmp_db) as db:
            repo = CardRepository(db)
            count1 = await repo.increment_enrichment_attempt(card_id)
            assert count1 == 2
            count2 = await repo.increment_enrichment_attempt(card_id)
            assert count2 == 3

    asyncio.run(_test())


@pytest.mark.integration
def test_re_enrich_capped_at_3_attempts(
    tmp_db: Path, sample_entry: IcebreakerToolEntry
) -> None:
    """Cards with enrichment_attempt_count >= 3 should not allow re-enrichment."""
    card_id = _insert_enriched_card(
        tmp_db, sample_entry, enrichment_attempt_count=3
    )

    async def _test() -> None:
        async with get_connection(tmp_db) as db:
            async with db.execute(
                "SELECT * FROM cards WHERE id = ?", (card_id,)
            ) as cursor:
                row = await cursor.fetchone()
                card = CardRepository._row_to_card(row)

        can_re_enrich = (card.enrichment_attempt_count or 1) < 3
        assert can_re_enrich is False

    asyncio.run(_test())


@pytest.mark.integration
def test_find_enriched_pending_gate2(
    tmp_db: Path, sample_entry: IcebreakerToolEntry
) -> None:
    """find_enriched_pending_gate2 returns only pending Gate 2 cards."""
    _insert_enriched_card(tmp_db, sample_entry, gate2_state="pending")
    _insert_enriched_card(tmp_db, sample_entry, gate2_state="gate2_approved")

    async def _test() -> None:
        async with get_connection(tmp_db) as db:
            repo = CardRepository(db)
            pending = await repo.find_enriched_pending_gate2()

        assert len(pending) == 1
        assert pending[0].gate2_state == "pending"

    asyncio.run(_test())
