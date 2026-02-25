"""HTTP/API collector for structured API endpoints."""

import json
import logging
from datetime import datetime, timezone

import httpx

from watchman.collectors.base import BaseCollector, register_collector
from watchman.models.raw_item import RawItem

logger = logging.getLogger(__name__)


@register_collector("api")
class APICollector(BaseCollector):
    """Collector for structured API endpoints.

    Handles Hacker News Algolia API format specifically and provides
    generic JSON array/object parsing for other API sources.
    """

    async def collect(self) -> list[RawItem]:
        """Fetch and parse a structured API response.

        Returns:
            List of RawItem instances from the API response.
        """
        url = str(self.source.url)

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        now = datetime.now(timezone.utc)

        # Hacker News Algolia API format
        if "hn.algolia.com" in url:
            return self._parse_hackernews(data, now)

        # Generic JSON parsing
        return self._parse_generic(data, now)

    def _parse_hackernews(
        self, data: dict, now: datetime
    ) -> list[RawItem]:
        """Parse Hacker News Algolia API response.

        Args:
            data: JSON response from HN Algolia API.
            now: Current timestamp for fallback dates.

        Returns:
            List of RawItem instances.
        """
        hits = data.get("hits", [])
        items: list[RawItem] = []

        for hit in hits:
            published_date = now
            created_at = hit.get("created_at")
            if created_at:
                try:
                    published_date = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            # Use story URL if available, otherwise HN discussion URL
            item_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

            items.append(
                RawItem(
                    source_name=self.source.name,
                    collector_type="api",
                    title=hit.get("title"),
                    url=item_url,
                    summary=hit.get("story_text") or hit.get("comment_text"),
                    published_date=published_date,
                    fetched_at=now,
                    raw_data=json.dumps(hit, default=str, ensure_ascii=False),
                )
            )

        logger.info(
            "HN API '%s' returned %d hits", self.source.name, len(items)
        )
        return items

    def _parse_generic(
        self, data: dict | list, now: datetime
    ) -> list[RawItem]:
        """Parse a generic JSON API response.

        Handles both JSON arrays and objects with a 'results' or 'items' key.

        Args:
            data: JSON response data.
            now: Current timestamp for fallback dates.

        Returns:
            List of RawItem instances.
        """
        # Handle JSON array directly
        if isinstance(data, list):
            entries = data
        # Handle object with common result keys
        elif isinstance(data, dict):
            for key in ("results", "items", "data", "entries", "records"):
                if key in data and isinstance(data[key], list):
                    entries = data[key]
                    break
            else:
                logger.warning(
                    "API '%s': could not find results array in response",
                    self.source.name,
                )
                return []
        else:
            return []

        items: list[RawItem] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            # Try common field names
            title = entry.get("title") or entry.get("name")
            url = entry.get("url") or entry.get("link") or entry.get("href")
            summary = (
                entry.get("summary")
                or entry.get("description")
                or entry.get("body")
            )

            # Try common date field names
            published_date = now
            for date_key in ("date", "created_at", "published_at", "timestamp"):
                date_val = entry.get(date_key)
                if date_val:
                    try:
                        published_date = datetime.fromisoformat(
                            str(date_val).replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        break
                    except (ValueError, AttributeError):
                        continue

            items.append(
                RawItem(
                    source_name=self.source.name,
                    collector_type="api",
                    title=title,
                    url=url,
                    summary=summary,
                    published_date=published_date,
                    fetched_at=now,
                    raw_data=json.dumps(entry, default=str, ensure_ascii=False),
                )
            )

        logger.info(
            "API '%s' parsed %d entries", self.source.name, len(items)
        )
        return items
