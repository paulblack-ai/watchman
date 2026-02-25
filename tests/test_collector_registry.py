"""Tests for collector registry population, resolution, and model datetime awareness."""

import pytest

from watchman.collectors import COLLECTOR_REGISTRY, get_collector
from watchman.collectors.api import APICollector
from watchman.collectors.rss import RSSCollector
from watchman.collectors.scrape import ScrapeCollector
from watchman.models.raw_item import RawItem
from watchman.models.signal_card import SignalCard
from watchman.models.source import SourceConfig


@pytest.mark.unit
def test_collector_registry_populated() -> None:
    """COLLECTOR_REGISTRY contains exactly 3 entries after package import."""
    assert len(COLLECTOR_REGISTRY) == 3
    assert set(COLLECTOR_REGISTRY.keys()) == {"rss", "api", "scrape"}


@pytest.mark.unit
def test_get_collector_returns_rss(tmp_path) -> None:
    """get_collector returns an RSSCollector for type='rss'."""
    source = SourceConfig(
        name="test-source", type="rss", url="https://example.com/feed", tier=1, frequency="6h"
    )
    collector = get_collector(source, tmp_path / "test.db")
    assert isinstance(collector, RSSCollector)


@pytest.mark.unit
def test_get_collector_returns_api(tmp_path) -> None:
    """get_collector returns an APICollector for type='api'."""
    source = SourceConfig(
        name="test-source", type="api", url="https://example.com/api", tier=1, frequency="6h"
    )
    collector = get_collector(source, tmp_path / "test.db")
    assert isinstance(collector, APICollector)


@pytest.mark.unit
def test_get_collector_returns_scrape(tmp_path) -> None:
    """get_collector returns a ScrapeCollector for type='scrape'."""
    source = SourceConfig(
        name="test-source", type="scrape", url="https://example.com/page", tier=1, frequency="6h"
    )
    collector = get_collector(source, tmp_path / "test.db")
    assert isinstance(collector, ScrapeCollector)


@pytest.mark.unit
def test_raw_item_fetched_at_is_aware() -> None:
    """RawItem default fetched_at is timezone-aware (UTC)."""
    item = RawItem(source_name="test", collector_type="rss")
    assert item.fetched_at.tzinfo is not None


@pytest.mark.unit
def test_signal_card_created_at_is_aware() -> None:
    """SignalCard default created_at is timezone-aware (UTC)."""
    card = SignalCard(
        title="test",
        source_name="test",
        date="2026-01-01",
        url="https://example.com",
        tier=1,
        collector_type="rss",
        url_hash="abc123",
    )
    assert card.created_at.tzinfo is not None
