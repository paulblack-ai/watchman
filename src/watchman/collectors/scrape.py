"""Web scrape collector using trafilatura for content extraction."""

import json
import logging
from datetime import datetime

import httpx
import trafilatura

from watchman.collectors.base import BaseCollector, register_collector
from watchman.models.raw_item import RawItem

logger = logging.getLogger(__name__)


@register_collector("scrape")
class ScrapeCollector(BaseCollector):
    """Collector for web pages using trafilatura content extraction.

    Fetches page HTML with httpx (explicit timeout), then uses trafilatura
    to extract content and metadata. This avoids trafilatura's built-in
    fetcher which may hang on slow pages.
    """

    async def collect(self) -> list[RawItem]:
        """Fetch and extract content from a web page.

        Returns:
            List containing a single RawItem from the page, or empty list on failure.
        """
        url = str(self.source.url)
        now = datetime.utcnow()

        # Fetch HTML with httpx (explicit timeout to avoid hangs)
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        html = response.text

        # Extract content using trafilatura
        content = trafilatura.extract(
            html, include_links=True, output_format="txt"
        )

        if not content:
            logger.warning(
                "Scrape '%s': trafilatura extracted no content from %s",
                self.source.name,
                url,
            )
            return []

        # Extract metadata for title and date
        metadata = trafilatura.extract_metadata(html)

        title = None
        published_date = now  # Fallback to fetch timestamp

        if metadata:
            title = metadata.title
            if metadata.date:
                try:
                    published_date = datetime.fromisoformat(str(metadata.date))
                except (ValueError, AttributeError):
                    pass

        # Use first 500 chars of content as summary
        summary = content[:500] if content else None

        raw_data = json.dumps(
            {
                "url": url,
                "title": title,
                "content_length": len(content) if content else 0,
                "has_metadata": metadata is not None,
            },
            default=str,
            ensure_ascii=False,
        )

        logger.info(
            "Scrape '%s' extracted %d chars from %s",
            self.source.name,
            len(content) if content else 0,
            url,
        )

        return [
            RawItem(
                source_name=self.source.name,
                collector_type="scrape",
                title=title or self.source.name,
                url=url,
                summary=summary,
                published_date=published_date,
                fetched_at=now,
                raw_data=raw_data,
            )
        ]
