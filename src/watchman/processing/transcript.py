"""YouTube transcript scanning: pre-filter and LLM-based tool extraction."""
from __future__ import annotations

import asyncio
import json
import logging
import re

from watchman.models.raw_item import RawItem

logger = logging.getLogger(__name__)

# Keyword patterns that indicate a tool-announcement video
_TOOL_ANNOUNCEMENT_PATTERNS = re.compile(
    r"new ai tool|just launched|just released|new feature|product launch"
    r"|tools you need|tools this week|tools that|ai tools"
    r"|top \d+ tool|best new|game.?changer|alternative to|just dropped"
    r"|\d+\s+(?:new\s+)?(?:ai\s+)?tool",
    re.IGNORECASE,
)

# Patterns that indicate non-tool content (tutorials, vlogs, etc.)
_NON_TOOL_PATTERNS = re.compile(
    r"how i use|my workflow|morning routine|day in the life"
    r"|tutorial for beginners",
    re.IGNORECASE,
)


def is_tool_announcement(title: str, description: str | None) -> bool:
    """Keyword-based pre-filter to detect tool-announcement videos.

    Returns True if the title or description suggests the video covers
    new AI tools, product launches, or feature releases. No LLM cost.

    Args:
        title: Video title.
        description: Video description (may be None).

    Returns:
        True if the video likely announces tools; False otherwise.
    """
    combined = title
    if description:
        combined = f"{title} {description}"

    has_tool_signal = bool(_TOOL_ANNOUNCEMENT_PATTERNS.search(combined))
    has_non_tool_signal = bool(_NON_TOOL_PATTERNS.search(title))

    # If title has non-tool signals and no tool signals, skip
    if has_non_tool_signal and not has_tool_signal:
        return False

    # Only return True on positive match
    return has_tool_signal


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

    # Fetch transcript
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_data = await asyncio.to_thread(
            YouTubeTranscriptApi.get_transcript, video_id
        )
        transcript_text = " ".join(seg["text"] for seg in transcript_data)
        # Truncate to 4000 chars to keep LLM costs reasonable
        transcript_text = transcript_text[:4000]
    except Exception:
        logger.warning(
            "Failed to fetch transcript for video '%s' (id=%s)",
            item.title,
            video_id,
        )
        return []

    if not transcript_text.strip():
        return []

    # LLM extraction
    prompt = (
        "Extract individual AI tools or products mentioned in this YouTube video "
        "transcript as new launches, releases, or demos. Skip tools only mentioned "
        "in passing (e.g., 'like ChatGPT'). Focus on tools being announced, demoed, "
        "or reviewed as new.\n\n"
        "Return a JSON array: "
        '[{"title": "Tool Name - What It Does", '
        '"description": "1-2 sentence summary of what the tool does and why it matters"}]\n\n'
        "If no specific new tools are mentioned, return an empty array: []\n\n"
        f"Video title: {item.title}\n"
        f"Transcript:\n{transcript_text}"
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
