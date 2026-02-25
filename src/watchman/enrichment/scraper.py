"""Web page content extraction using httpx and trafilatura."""
from __future__ import annotations


import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)


async def scrape_url(url: str, timeout: float = 15.0) -> str | None:
    """Fetch a URL and extract main content text.

    Uses httpx for async HTTP fetching and trafilatura for content extraction.
    Returns None on any failure (graceful fallback to card metadata).

    Args:
        url: URL to fetch and extract content from.
        timeout: HTTP request timeout in seconds.

    Returns:
        Extracted text content, or None if fetching or extraction fails.
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Watchman/0.1"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        extracted = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
        )

        if not extracted:
            logger.warning("No content extracted from %s", url)
            return None

        logger.info(
            "Scraped %d chars from %s", len(extracted), url
        )
        return extracted

    except Exception:
        logger.warning("Scrape failed for %s, falling back to card data", url)
        return None
