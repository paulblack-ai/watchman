"""Watchman signal collectors for RSS, API, scrape, and Jina sources."""

# Import collectors to trigger registration decorators
from watchman.collectors import api, jina, rss, scrape  # noqa: F401
from watchman.collectors.base import COLLECTOR_REGISTRY, get_collector

__all__ = ["COLLECTOR_REGISTRY", "get_collector"]
