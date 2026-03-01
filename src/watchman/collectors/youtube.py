"""YouTube channel collector using RSS feeds + optional transcript scanning."""
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


@register_collector("youtube")
class YouTubeCollector(BaseCollector):
    """Collector for YouTube channels via their Atom RSS feeds.

    Uses YouTube's built-in Atom feed at:
    https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID

    The source URL in sources.yaml should be the full feed URL.
    Video entries are returned as RawItem instances with the video
    title, URL, and description from the feed.
    """

    async def collect(self) -> list[RawItem]:
        """Fetch and parse a YouTube channel's RSS feed.

        Returns:
            List of RawItem instances from recent videos.
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
                "YouTube feed '%s' has parse errors and no entries: %s",
                self.source.name,
                feed.bozo_exception,
            )
            return []

        items: list[RawItem] = []
        now = datetime.now(timezone.utc)

        for entry in feed.entries:
            published_date = self._parse_date(entry, now)

            # YouTube feeds use media:group for description
            summary = None
            if hasattr(entry, "media_group"):
                for item in entry.media_group:
                    if hasattr(item, "content") and isinstance(item.get("content"), str):
                        summary = item["content"]
                        break
            if not summary and hasattr(entry, "summary"):
                summary = entry.summary
            if not summary and hasattr(entry, "media_description"):
                summary = entry.media_description

            video_id = entry.get("yt_videoid", "")
            video_url = entry.get("link", f"https://www.youtube.com/watch?v={video_id}")

            raw_data = json.dumps(
                {
                    "video_id": video_id,
                    "channel": self.source.name,
                    "url": video_url,
                },
                default=str,
                ensure_ascii=False,
            )

            items.append(
                RawItem(
                    source_name=self.source.name,
                    collector_type="youtube",
                    title=entry.get("title"),
                    url=video_url,
                    summary=summary[:500] if summary else None,
                    published_date=published_date,
                    fetched_at=now,
                    raw_data=raw_data,
                )
            )

        logger.info(
            "YouTube feed '%s' parsed %d entries", self.source.name, len(items)
        )
        return items

    @staticmethod
    def _parse_date(entry: feedparser.FeedParserDict, fallback: datetime) -> datetime:
        """Parse publish date from a YouTube feed entry.

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
