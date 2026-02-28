"""Jina markdown collector using r.jina.ai for content extraction."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from watchman.collectors.base import BaseCollector, register_collector
from watchman.models.raw_item import RawItem

logger = logging.getLogger(__name__)


@register_collector("jina")
class JinaCollector(BaseCollector):
    """Collector that fetches page content via Jina AI's reader API.

    Uses https://r.jina.ai/{url} to get a markdown representation of any
    web page. Parses the markdown to extract individual entries from
    changelog pages (split on headings) or blog listing pages (extract links).
    Falls back to a single RawItem with full page content if no structure
    is detected.
    """

    JINA_PREFIX = "https://r.jina.ai/"

    async def collect(self) -> list[RawItem]:
        """Fetch markdown via Jina and parse into RawItem entries.

        Returns:
            List of RawItem instances extracted from the page.
        """
        source_url = str(self.source.url)
        jina_url = f"{self.JINA_PREFIX}{source_url}"
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True
        ) as client:
            response = await client.get(
                jina_url,
                headers={
                    "Accept": "text/markdown",
                    "User-Agent": "Watchman/1.0",
                    "X-No-Cache": "true",
                },
            )
            response.raise_for_status()

        markdown = response.text
        if not markdown or not markdown.strip():
            logger.warning(
                "Jina '%s': empty response from %s",
                self.source.name,
                jina_url,
            )
            return []

        # Try parsing as changelog (heading-based structure)
        items = self._parse_changelog(markdown, source_url, now)
        if items:
            logger.info(
                "Jina '%s' parsed %d changelog entries from %s",
                self.source.name,
                len(items),
                source_url,
            )
            return items

        # Try parsing as blog listing (link-based structure)
        items = self._parse_blog_listing(markdown, source_url, now)
        if items:
            logger.info(
                "Jina '%s' parsed %d blog listing entries from %s",
                self.source.name,
                len(items),
                source_url,
            )
            return items

        # Fallback: single item with full content
        logger.info(
            "Jina '%s' no structure detected, returning single item from %s",
            self.source.name,
            source_url,
        )
        return [
            RawItem(
                source_name=self.source.name,
                collector_type="jina",
                title=self.source.name,
                url=source_url,
                summary=markdown[:500],
                published_date=now,
                fetched_at=now,
                raw_data=json.dumps(
                    {"url": source_url, "content_length": len(markdown)},
                    default=str,
                    ensure_ascii=False,
                ),
            )
        ]

    def _parse_changelog(
        self, markdown: str, source_url: str, now: datetime
    ) -> list[RawItem]:
        """Parse markdown with heading-based structure (changelogs).

        Splits on ## or ### headings. Each heading becomes a RawItem
        with the heading text as title and body text as summary.

        Args:
            markdown: Full markdown text from Jina.
            source_url: Original source URL.
            now: Current timestamp.

        Returns:
            List of RawItem instances, or empty list if no headings found.
        """
        # Split on ## or ### headings (not # which is usually the page title)
        sections = re.split(r"^(#{2,3})\s+(.+)$", markdown, flags=re.MULTILINE)

        # sections layout: [preamble, level, title, body, level, title, body, ...]
        if len(sections) < 4:
            return []

        items: list[RawItem] = []
        i = 1
        while i < len(sections) - 2:
            _level = sections[i]
            title = sections[i + 1].strip()
            body = sections[i + 2].strip() if i + 2 < len(sections) else ""
            i += 3

            # Skip empty or very short sections
            if not title or len(title) < 3:
                continue

            summary = body[:500] if body else None

            items.append(
                RawItem(
                    source_name=self.source.name,
                    collector_type="jina",
                    title=title,
                    url=source_url,
                    summary=summary,
                    published_date=now,
                    fetched_at=now,
                    raw_data=json.dumps(
                        {
                            "url": source_url,
                            "title": title,
                            "body_length": len(body),
                        },
                        default=str,
                        ensure_ascii=False,
                    ),
                )
            )

        return items

    def _parse_blog_listing(
        self, markdown: str, source_url: str, now: datetime
    ) -> list[RawItem]:
        """Parse markdown with link-based structure (blog listings).

        Looks for markdown links [title](url) and extracts each as a
        RawItem. Filters out navigation/boilerplate links (short titles,
        anchor-only hrefs, common nav text).

        Args:
            markdown: Full markdown text from Jina.
            source_url: Original source URL.
            now: Current timestamp.

        Returns:
            List of RawItem instances, or empty list if insufficient links.
        """
        # Find all markdown links
        link_pattern = re.compile(r"\[([^\]]{5,})\]\((https?://[^\)]+)\)")
        matches = link_pattern.findall(markdown)

        if len(matches) < 3:
            return []

        # Filter out common navigation links
        nav_words = {
            "home", "about", "contact", "login", "sign up", "sign in",
            "privacy", "terms", "cookie", "menu", "search", "subscribe",
            "read more", "learn more", "see all", "view all",
        }

        items: list[RawItem] = []
        seen_urls: set[str] = set()

        for title, url in matches:
            title = title.strip()
            if title.lower() in nav_words:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Try to extract surrounding text as summary
            # Find the line containing this link and nearby lines
            summary = self._extract_context(markdown, title, url)

            items.append(
                RawItem(
                    source_name=self.source.name,
                    collector_type="jina",
                    title=title,
                    url=url,
                    summary=summary,
                    published_date=now,
                    fetched_at=now,
                    raw_data=json.dumps(
                        {"source_url": source_url, "link_url": url, "title": title},
                        default=str,
                        ensure_ascii=False,
                    ),
                )
            )

        return items

    @staticmethod
    def _extract_context(markdown: str, title: str, url: str) -> str | None:
        """Extract text surrounding a link as context/summary.

        Args:
            markdown: Full markdown text.
            title: Link title text.
            url: Link URL.

        Returns:
            Surrounding text (up to 300 chars) or None.
        """
        # Find the line with this link
        escaped_title = re.escape(title)
        pattern = re.compile(
            rf"^(.*\[{escaped_title}\]\({re.escape(url)}\).*)$",
            re.MULTILINE,
        )
        match = pattern.search(markdown)
        if not match:
            return None

        line_start = match.start()
        # Get a window of text around the link
        context_start = max(0, line_start - 100)
        context_end = min(len(markdown), match.end() + 200)
        context = markdown[context_start:context_end].strip()

        # Clean up markdown formatting
        context = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", context)
        context = re.sub(r"[#*_`]", "", context)

        return context[:300] if context else None
