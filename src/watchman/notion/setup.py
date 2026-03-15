"""Notion database schema validation and setup instructions."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Required Notion database properties: name -> expected type
REQUIRED_PROPERTIES: dict[str, str] = {
    "Title": "title",
    "Source": "select",
    "Tier": "select",
    "Score": "number",
    "Top Dimension": "select",
    "Review Status": "status",
    "Published": "date",
    "URL": "url",
    "Enrichment": "select",
    "Gate 2": "status",
    "Snooze Until": "date",
    "Attempts": "number",
}


async def validate_database_schema(client) -> dict[str, bool]:
    """Query the Notion database metadata and check required properties.

    Does NOT auto-create missing properties — the user must set up the
    Notion database manually per print_setup_instructions().

    Args:
        client: NotionClient instance connected to the target database.

    Returns:
        Dict mapping property_name -> True if exists with correct type,
        False if missing or wrong type.
    """
    from notion_client import Client as _Client  # noqa: F401, PLC0415

    result: dict[str, bool] = {name: False for name in REQUIRED_PROPERTIES}

    try:
        response = client._client.databases.retrieve(
            database_id=client.database_id
        )
        existing: dict[str, dict] = response.get("properties", {})

        for prop_name, expected_type in REQUIRED_PROPERTIES.items():
            if prop_name not in existing:
                logger.warning(
                    "Notion database missing property: '%s' (expected type: %s)",
                    prop_name,
                    expected_type,
                )
                result[prop_name] = False
                continue

            actual_type = existing[prop_name].get("type", "")
            if actual_type != expected_type:
                logger.warning(
                    "Notion property '%s' has wrong type: got '%s', expected '%s'",
                    prop_name,
                    actual_type,
                    expected_type,
                )
                result[prop_name] = False
            else:
                result[prop_name] = True

    except Exception:
        logger.exception("Failed to retrieve Notion database schema")
        return result

    return result


def print_setup_instructions() -> None:
    """Print instructions for creating the Notion database with required properties."""
    print(
        """
=== Notion Database Setup Instructions ===

Create a new Notion database (full-page or inline) with the following properties:

Property Name    | Type       | Notes
-----------------|------------|----------------------------------------
Title            | Title      | (default — already exists)
Source           | Select     | Source name (e.g. "TechCrunch")
Tier             | Select     | Options: 1, 2, 3
Score            | Number     | Relevance score (0-1 float)
Top Dimension    | Select     | e.g. "novel_capability"
Review Status    | Status     | Options: To Review, Approved, Rejected, Snoozed
Published        | Date       | Article publication date
URL              | URL        | Original article URL
Enrichment       | Select     | Options: pending, in_progress, complete, failed, skipped
Gate 2           | Status     | Options: Not Started, To Review, Approved, Rejected
Snooze Until     | Date       | Date when a snoozed card re-appears
Attempts         | Number     | Enrichment attempt count

After creating the database:
1. Share the database with your Notion integration
2. Copy the database ID from the URL (32-char hex string)
3. Set environment variables:
   export NOTION_TOKEN=secret_...
   export NOTION_DATABASE_ID=<your-database-id>

Run `python -m watchman.main` to start Watchman with Notion integration.
"""
    )
