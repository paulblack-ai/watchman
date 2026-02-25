"""Claude Sonnet-based structured extraction for enrichment."""

import logging
from datetime import datetime

import anthropic

from watchman.llm_client import get_client
from watchman.models.icebreaker import IcebreakerToolEntry

logger = logging.getLogger(__name__)


def _build_enrichment_prompt(
    card_title: str,
    card_url: str,
    card_summary: str | None,
    page_content: str | None,
) -> str:
    """Build the enrichment extraction prompt for Claude Sonnet.

    Args:
        card_title: Title of the signal card.
        card_url: URL of the tool/signal.
        card_summary: Optional summary from the signal card.
        page_content: Extracted page content, or None if scraping failed.

    Returns:
        Formatted prompt string.
    """
    summary_line = f"**Summary:** {card_summary}" if card_summary else ""

    if page_content is not None:
        content_section = f"## Page Content\n\n{page_content}"
    else:
        content_section = (
            "## Note\n"
            "Page content could not be scraped. "
            "Extract what you can from the title, summary, and URL only."
        )

    return f"""Extract structured tool information for the IcebreakerAI tool registry.

## Signal

**Title:** {card_title}
**URL:** {card_url}
{summary_line}

{content_section}

## Instructions

1. Extract factual information ONLY from the provided content.
2. For fields you cannot determine from the content, use null or empty list.
3. Do NOT infer or fabricate pricing, capabilities, or API details not mentioned in the content.
4. name: Use the tool/product name as it appears in the content.
5. description: A concise 1-2 sentence description of what the tool does.
6. capabilities: List specific features and capabilities mentioned in the content.
7. pricing: Extract pricing model if mentioned (free, freemium, paid, enterprise, etc.), null if not stated.
8. api_surface: Describe API/SDK availability if mentioned, null if not stated.
9. integration_hooks: List specific integrations mentioned (e.g., "Slack", "GitHub", "REST API").

Respond with a JSON object matching the required schema."""


async def enrich_card(
    card_title: str,
    card_url: str,
    card_summary: str | None,
    page_content: str | None,
) -> IcebreakerToolEntry:
    """Extract structured tool information using Claude Sonnet.

    Uses json_schema structured output to produce a validated IcebreakerToolEntry.

    Args:
        card_title: Title of the signal card.
        card_url: URL of the tool/signal.
        card_summary: Optional summary from the signal card.
        page_content: Extracted page content, or None for fallback extraction.

    Returns:
        Validated IcebreakerToolEntry with extracted data.

    Raises:
        anthropic.APIError: If the Anthropic API call fails.
        pydantic.ValidationError: If the response cannot be validated.
    """
    client = get_client()
    prompt = _build_enrichment_prompt(card_title, card_url, card_summary, page_content)

    response = client.messages.create(
        model="anthropic/claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        betas=["output-128k-2025-02-19"],
        output_config={
            "format": {
                "type": "json_schema",
                "name": "icebreaker_tool_entry",
                "schema": IcebreakerToolEntry.model_json_schema(),
            }
        },
    )

    entry = IcebreakerToolEntry.model_validate_json(response.content[0].text)

    # Overwrite source_url and discovered_at with known-accurate values
    return IcebreakerToolEntry(
        name=entry.name,
        description=entry.description,
        capabilities=entry.capabilities,
        pricing=entry.pricing,
        api_surface=entry.api_surface,
        integration_hooks=entry.integration_hooks,
        source_url=card_url,
        discovered_at=datetime.utcnow(),
    )
