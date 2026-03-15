"""Notion API client wrapper with rate limiting."""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Rate limit: stay under 3 requests/second (Notion API limit)
_RATE_LIMIT_SLEEP = 0.35


class NotionAPIError(Exception):
    """Raised when a Notion API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NotionClient:
    """Thin wrapper around the Notion SDK with rate limiting.

    All methods sleep _RATE_LIMIT_SLEEP seconds between API calls to stay
    under Notion's 3 requests/second rate limit.

    Args:
        token: Notion integration token (starts with "secret_").
        database_id: Target Notion database ID.
    """

    def __init__(self, token: str, database_id: str) -> None:
        from notion_client import Client  # noqa: PLC0415

        self._client = Client(auth=token)
        self.database_id = database_id

    def create_page(
        self, properties: dict[str, Any], children: list[dict] | None = None
    ) -> str:
        """Create a new page in the Notion database.

        Args:
            properties: Notion property values dict.
            children: Optional list of block dicts for page body content.

        Returns:
            Page ID of the created page.

        Raises:
            NotionAPIError: If the API call fails.
        """
        time.sleep(_RATE_LIMIT_SLEEP)
        try:
            kwargs: dict[str, Any] = {
                "parent": {"database_id": self.database_id},
                "properties": properties,
            }
            if children:
                kwargs["children"] = children
            response = self._client.pages.create(**kwargs)
            return response["id"]
        except Exception as e:
            status = getattr(e, "status", None) or getattr(e, "code", None)
            logger.error("Notion create_page failed: %s", e)
            raise NotionAPIError(str(e), status_code=status) from e

    def update_page(self, page_id: str, properties: dict[str, Any]) -> None:
        """Update properties of an existing Notion page.

        Args:
            page_id: ID of the page to update.
            properties: Property values to update.

        Raises:
            NotionAPIError: If the API call fails.
        """
        time.sleep(_RATE_LIMIT_SLEEP)
        try:
            self._client.pages.update(page_id=page_id, properties=properties)
        except Exception as e:
            status = getattr(e, "status", None) or getattr(e, "code", None)
            logger.error("Notion update_page failed for %s: %s", page_id, e)
            raise NotionAPIError(str(e), status_code=status) from e

    def update_page_content(self, page_id: str, children: list[dict]) -> None:
        """Append block content to an existing Notion page.

        Args:
            page_id: ID of the page to append to.
            children: List of block dicts to append.

        Raises:
            NotionAPIError: If the API call fails.
        """
        time.sleep(_RATE_LIMIT_SLEEP)
        try:
            self._client.blocks.children.append(
                block_id=page_id, children=children
            )
        except Exception as e:
            status = getattr(e, "status", None) or getattr(e, "code", None)
            logger.error("Notion update_page_content failed for %s: %s", page_id, e)
            raise NotionAPIError(str(e), status_code=status) from e

    def query_database(
        self,
        filter: dict | None = None,
        sorts: list[dict] | None = None,
    ) -> list[dict]:
        """Query the Notion database, handling pagination automatically.

        Args:
            filter: Optional Notion filter object.
            sorts: Optional list of sort objects.

        Returns:
            List of all matching page objects.

        Raises:
            NotionAPIError: If the API call fails.
        """
        results: list[dict] = []
        start_cursor: str | None = None

        while True:
            time.sleep(_RATE_LIMIT_SLEEP)
            try:
                kwargs: dict[str, Any] = {"database_id": self.database_id}
                if filter:
                    kwargs["filter"] = filter
                if sorts:
                    kwargs["sorts"] = sorts
                if start_cursor:
                    kwargs["start_cursor"] = start_cursor

                response = self._client.databases.query(**kwargs)
                results.extend(response.get("results", []))

                if not response.get("has_more"):
                    break
                start_cursor = response.get("next_cursor")

            except Exception as e:
                status = getattr(e, "status", None) or getattr(e, "code", None)
                logger.error("Notion query_database failed: %s", e)
                raise NotionAPIError(str(e), status_code=status) from e

        return results

    def get_page(self, page_id: str) -> dict:
        """Retrieve a single Notion page by ID.

        Args:
            page_id: ID of the page to retrieve.

        Returns:
            Page object dict.

        Raises:
            NotionAPIError: If the API call fails.
        """
        time.sleep(_RATE_LIMIT_SLEEP)
        try:
            return self._client.pages.retrieve(page_id=page_id)
        except Exception as e:
            status = getattr(e, "status", None) or getattr(e, "code", None)
            logger.error("Notion get_page failed for %s: %s", page_id, e)
            raise NotionAPIError(str(e), status_code=status) from e
