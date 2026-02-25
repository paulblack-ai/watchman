"""RSS/Atom feed collector using feedparser."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

from watchman.collectors.base import BaseCollector, register_collector
from watchman.models.raw_item import RawItem

logger = logging.getLogger(__name__)


@register_collector("rss")
class RSSCollector(BaseCollector):
    """Collector for RSS and Atom feeds.

    Uses httpx to fetch feed content and feedparser to parse entries.
    Handles multiple date formats and falls back to fetch timestamp
    when publish dates are missing.
    """

    async def collect(self) -> list[RawItem]:
        """Fetch and parse an RSS/Atom feed.

        Returns:
            List of RawItem instances from feed entries.
        """
        url = str(self.source.url)

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            logger.warning(
                "Feed '%s' has parse errors and no entries: %s",
                self.source.name,
                feed.bozo_exception,
            )
            return []

        items: list[RawItem] = []
        now = datetime.now(timezone.utc)

        for entry in feed.entries:
            published_date = self._parse_date(entry, now)

            # Extract summary from various feed fields
            summary = None
            if hasattr(entry, "summary"):
                summary = entry.summary
            elif hasattr(entry, "description"):
                summary = entry.description

            # Store raw entry data as JSON for debugging/reprocessing
            raw_data = json.dumps(
                {k: str(v) for k, v in entry.items()},
                default=str,
                ensure_ascii=False,
            )

            items.append(
                RawItem(
                    source_name=self.source.name,
                    collector_type="rss",
                    title=entry.get("title"),
                    url=entry.get("link"),
                    summary=summary,
                    published_date=published_date,
                    fetched_at=now,
                    raw_data=raw_data,
                )
            )

        logger.info(
            "RSS feed '%s' parsed %d entries", self.source.name, len(items)
        )
        return items

    @staticmethod
    def _parse_date(entry: feedparser.FeedParserDict, fallback: datetime) -> datetime:
        """Parse publish date from a feed entry with fallback.

        Tries published_parsed, then updated_parsed, then falls back
        to the fetch timestamp (per user decision).

        Args:
            entry: A feedparser entry dict.
            fallback: Datetime to use if no date is found.

        Returns:
            Parsed datetime or fallback.
        """
        for attr in ("published_parsed", "updated_parsed"):
            parsed = entry.get(attr)
            if parsed is not None:
                try:
                    return datetime.fromtimestamp(mktime(parsed))
                except (ValueError, OverflowError):
                    continue

        return fallback
