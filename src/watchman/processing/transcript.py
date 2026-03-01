"""YouTube transcript scanning: pre-filter and LLM-based tool extraction."""
from __future__ import annotations

import asyncio
import json
import logging
import re

from watchman.models.raw_item import RawItem

logger = logging.getLogger(__name__)

# Patterns that indicate skip-worthy content (tutorials, vlogs, lifestyle, opinions)
_SKIP_PATTERNS = re.compile(
    r"how i use|my workflow|morning routine|day in the life"
    r"|tutorial for beginners|beginner.?s? guide"
    r"|what .+ tell us about|explained for beginners"
    r"|how to (?:start|learn|get into)|tips for"
    r"|my (?:honest )?review of (?:chatgpt|copilot|gemini)"
    r"|unpopular opinion|hot take|rant about",
    re.IGNORECASE,
)

# Strong positive signals — always pass these through
_STRONG_TOOL_PATTERNS = re.compile(
    r"new ai tool|just launched|just released|just dropped"
    r"|tools you need|tools this week|tools that|ai tools"
    r"|top \d+ tool|best new|game.?changer|alternative to"
    r"|\d+\s+(?:new\s+)?(?:ai\s+)?tool"
    r"|product launch|new feature|is here|vs |i tested"
    r"|first (?:ai|look)|hands.on|demo|launches|released"
    r"|new (?:ai|app|model|platform|update|version)"
    r"|ai (?:agent|browser|model|app|platform|assistant)",
    re.IGNORECASE,
)


def is_tool_announcement(title: str, description: str | None) -> bool:
    """Pre-filter to detect videos worth scanning for tool mentions.

    These YouTube sources are curated AI channels, so most content is
    relevant. We use a permissive approach: skip only clearly irrelevant
    content (tutorials, vlogs, lifestyle). Most videos from AI-focused
    channels like Matt Wolfe and Futurepedia cover tools/products.

    Args:
        title: Video title.
        description: Video description (may be None).

    Returns:
        True if the video is worth scanning for tool mentions.
    """
    combined = title
    if description:
        combined = f"{title} {description}"

    # Strong positive signals always pass
    if _STRONG_TOOL_PATTERNS.search(combined):
        return True

    # Skip clearly irrelevant content
    if _SKIP_PATTERNS.search(title):
        return False

    # Default: allow through for AI-focused channels
    # These are curated sources — most videos are relevant
    return True


async def extract_tools_from_transcript(item: RawItem) -> list[dict]:
    """Fetch YouTube transcript and extract individual tool mentions via LLM.

    Args:
        item: RawItem with collector_type="youtube" and raw_data containing video_id.

    Returns:
        List of dicts with 'title' and 'description' keys, one per tool found.
        Returns empty list if transcript fetch fails or no tools are found.
    """
    # Extract video_id from raw_data
    try:
        raw = json.loads(item.raw_data or "{}")
        video_id = raw.get("video_id")
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse raw_data for YouTube item '%s'", item.title)
        return []

    if not video_id:
        logger.warning("No video_id in raw_data for YouTube item '%s'", item.title)
        return []

    # Fetch transcript (v1.x API: instance-based, .fetch(), snippet objects)
    transcript_text = ""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        transcript_data = await asyncio.to_thread(api.fetch, video_id)
        transcript_text = " ".join(snippet.text for snippet in transcript_data)
        # Truncate to 4000 chars to keep LLM costs reasonable
        transcript_text = transcript_text[:4000]
        logger.info("Fetched transcript for '%s' (%d chars)", item.title, len(transcript_text))
    except Exception:
        logger.warning(
            "Transcript unavailable for '%s' (id=%s), falling back to title+description",
            item.title,
            video_id,
        )

    # Build content for LLM: prefer transcript, fall back to description
    if transcript_text.strip():
        content_label = "Transcript"
        content_text = transcript_text
    elif item.summary and len(item.summary.strip()) > 50:
        content_label = "Video description"
        content_text = item.summary[:2000]
    else:
        # No transcript and no meaningful description — can't extract tools
        logger.info("No transcript or description for '%s', skipping extraction", item.title)
        return []

    # LLM extraction
    prompt = (
        "Extract individual AI tools or products mentioned in this YouTube video "
        f"{content_label.lower()} as new launches, releases, or demos. Skip tools only mentioned "
        "in passing (e.g., 'like ChatGPT'). Focus on tools being announced, demoed, "
        "or reviewed as new.\n\n"
        "Return a JSON array: "
        '[{"title": "Tool Name - What It Does", '
        '"description": "1-2 sentence summary of what the tool does and why it matters"}]\n\n'
        "If no specific new tools are mentioned, return an empty array: []\n\n"
        f"Video title: {item.title}\n"
        f"{content_label}:\n{content_text}"
    )

    try:
        from watchman.llm_client import get_client
        from watchman.processing.normalizer import _parse_llm_json

        client = get_client()
        response = await asyncio.to_thread(
            client.messages.create,
            model="anthropic/claude-haiku-4.5",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        parsed = _parse_llm_json(text)

        if isinstance(parsed, list):
            valid = [
                {"title": e.get("title", ""), "description": e.get("description", "")}
                for e in parsed
                if isinstance(e, dict) and e.get("title")
            ]
            if valid:
                logger.info(
                    "Extracted %d tools from transcript of '%s'",
                    len(valid),
                    item.title,
                )
                return valid

        logger.info("No tools extracted from transcript of '%s'", item.title)
    except Exception:
        logger.exception("LLM transcript extraction failed for '%s'", item.title)

    return []
