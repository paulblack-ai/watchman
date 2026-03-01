"""Raw item to signal card normalization with LLM-powered changelog splitting."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from watchman.models.raw_item import RawItem
from watchman.models.signal_card import SignalCard
from watchman.models.source import SourceConfig
from watchman.processing.deduplicator import handle_duplicate, is_duplicate
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository, RawItemRepository

logger = logging.getLogger(__name__)

# Patterns that indicate a generic/non-specific title
_GENERIC_TITLE_PATTERNS = re.compile(
    r"^(what'?s new|changelog|releases?|updates?|blog|news|latest)"
    r"|^.{1,20}$",
    re.IGNORECASE,
)


def _is_changelog_candidate(item: RawItem, source_cfg: SourceConfig | None) -> bool:
    """Detect whether a raw item is a changelog-style page that should be split.

    Args:
        item: Raw item to check.
        source_cfg: Source configuration (may be None).

    Returns:
        True if the item likely contains multiple changelog entries.
    """
    if "changelog" in item.source_name.lower():
        return True
    if source_cfg and source_cfg.tier == 3 and item.collector_type == "scrape":
        return True
    return False


def _is_generic_title(title: str, source_name: str) -> bool:
    """Check if a title is too generic and would benefit from LLM improvement.

    Args:
        title: The card title.
        source_name: The source name for comparison.

    Returns:
        True if the title appears generic.
    """
    if not title or title == "Untitled":
        return True
    # Title is basically just the source/site name
    if title.lower().strip() in source_name.lower():
        return True
    if source_name.lower().strip() in title.lower() and len(title) < 40:
        return True
    if _GENERIC_TITLE_PATTERNS.search(title):
        return True
    return False


def _parse_llm_json(text: str) -> list[dict] | dict | None:
    """Parse JSON from LLM response, handling markdown code fences.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed JSON (list or dict), or None if parsing fails.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response: %s", text[:200])
        return None


async def split_changelog_item(item: RawItem) -> list[dict]:
    """Split a changelog page into individual feature entries using LLM.

    Calls Claude Haiku to extract individual features/updates from a
    changelog page that may contain multiple entries.

    Args:
        item: Raw item containing changelog content.

    Returns:
        List of dicts with 'title' and 'description' keys.
        Returns a single-item list if splitting is not possible.
    """
    summary_text = item.summary or ""
    raw_text = item.raw_data or ""
    content = summary_text if len(summary_text) > len(raw_text) else raw_text
    if not content:
        content = summary_text or raw_text or ""

    prompt = (
        "Extract individual features/updates from this changelog page. "
        "For each feature, provide a specific title and a 1-2 sentence "
        "description of what it does. Return JSON array: "
        '[{"title": "...", "description": "..."}]. '
        "If there's only one feature or this isn't a changelog, return a "
        "single item with a more specific title/description than the page title.\n\n"
        f"Page title: {item.title}\n"
        f"URL: {item.url}\n"
        f"Content:\n{content[:3000]}"
    )

    try:
        from watchman.llm_client import get_client

        client = get_client()
        response = await asyncio.to_thread(
            client.messages.create,
            model="anthropic/claude-haiku-4.5",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        parsed = _parse_llm_json(text)

        if isinstance(parsed, list) and len(parsed) > 0:
            # Validate each entry has required keys
            valid = [
                {"title": e.get("title", ""), "description": e.get("description", "")}
                for e in parsed
                if isinstance(e, dict) and e.get("title")
            ]
            if valid:
                return valid

        if isinstance(parsed, dict) and parsed.get("title"):
            return [{"title": parsed["title"], "description": parsed.get("description", "")}]

        logger.warning("LLM returned unexpected format for changelog split: %s", text[:200])
    except Exception:
        logger.exception("LLM changelog splitting failed for '%s'", item.title)

    # Fallback: return original item info
    return [{"title": item.title or "Untitled", "description": item.summary or ""}]


async def improve_generic_title(item: RawItem) -> dict | None:
    """Use LLM to generate a more specific title and summary for generic items.

    Args:
        item: Raw item with a potentially generic title.

    Returns:
        Dict with 'title' and 'summary' keys, or None if improvement fails.
    """
    summary_text = item.summary or item.raw_data or ""
    prompt = (
        "Given this signal title and summary, provide a more specific and "
        "descriptive title (max 80 chars) and a 1-2 sentence summary. "
        'Return JSON: {"title": "...", "summary": "..."}.\n\n'
        f"Title: {item.title}\n"
        f"Source: {item.source_name}\n"
        f"Summary: {summary_text[:2000]}"
    )

    try:
        from watchman.llm_client import get_client

        client = get_client()
        response = await asyncio.to_thread(
            client.messages.create,
            model="anthropic/claude-haiku-4.5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        parsed = _parse_llm_json(text)

        if isinstance(parsed, dict) and parsed.get("title"):
            return {"title": parsed["title"], "summary": parsed.get("summary", "")}
    except Exception:
        logger.exception("LLM title improvement failed for '%s'", item.title)

    return None


def normalize_raw_item(
    item: RawItem,
    tier: int,
    override_title: str | None = None,
    override_summary: str | None = None,
) -> SignalCard:
    """Normalize a raw item into a signal card.

    Maps RawItem fields to SignalCard fields, computes URL hash
    and content fingerprint for deduplication.

    Args:
        item: Raw item from a collector.
        tier: Source tier (1, 2, or 3) from source config.
        override_title: If provided, use instead of item.title.
        override_summary: If provided, use instead of item.summary.

    Returns:
        A SignalCard instance ready for deduplication and storage.
    """
    title = override_title or item.title or "Untitled"
    url = item.url or ""
    date = item.published_date or item.fetched_at
    summary = override_summary if override_summary is not None else item.summary

    # For split cards (override_title set), make url_hash unique by appending title
    if override_title:
        url_hash = SignalCard.compute_url_hash(f"{url}#{override_title}")
    else:
        url_hash = SignalCard.compute_url_hash(url)
    # Use override title for fingerprint so split cards get distinct fingerprints
    content_fingerprint = SignalCard.compute_content_fingerprint(title, date)

    return SignalCard(
        title=title,
        source_name=item.source_name,
        date=date,
        url=url,
        tier=tier,
        summary=summary,
        collector_type=item.collector_type,
        url_hash=url_hash,
        content_fingerprint=content_fingerprint,
    )


async def _insert_and_dedup(
    card: SignalCard, card_repo: CardRepository
) -> bool:
    """Insert a card with deduplication. Returns True if new (non-duplicate).

    Args:
        card: SignalCard to insert.
        card_repo: Card repository for DB operations.

    Returns:
        True if the card was inserted as a new canonical card.
    """
    is_dup, canonical = await is_duplicate(card, card_repo)

    if is_dup and canonical:
        dup_id = await card_repo.insert(card)
        card_with_id = SignalCard(id=dup_id, **card.model_dump(exclude={"id"}))
        await handle_duplicate(card_with_id, canonical, card_repo)
        logger.debug(
            "Duplicate: '%s' matches canonical card %d",
            card.title,
            canonical.id,
        )
        return False

    await card_repo.insert(card)
    return True


async def process_unprocessed(
    db_path: Path, source_configs: dict[str, SourceConfig]
) -> int:
    """Process all unprocessed raw items: normalize, deduplicate, store.

    For changelog-style items, uses LLM to split into individual feature cards.
    For items with generic titles, uses LLM to improve specificity.

    Args:
        db_path: Path to the SQLite database.
        source_configs: Map of source name to SourceConfig for tier lookup.

    Returns:
        Number of new (non-duplicate) cards created.
    """
    new_cards = 0

    async with get_connection(db_path) as db:
        raw_repo = RawItemRepository(db)
        card_repo = CardRepository(db)

        unprocessed = await raw_repo.find_unprocessed()

        if not unprocessed:
            logger.debug("No unprocessed raw items")
            return 0

        logger.info("Processing %d unprocessed raw items", len(unprocessed))

        for item in unprocessed:
            try:
                source_cfg = source_configs.get(item.source_name)
                tier = source_cfg.tier if source_cfg else 2

                if item.collector_type == "youtube":
                    from watchman.processing.transcript import (
                        extract_tools_from_transcript,
                        is_tool_announcement,
                    )

                    if is_tool_announcement(item.title or "", item.summary):
                        tools = await extract_tools_from_transcript(item)
                        if tools:
                            logger.info(
                                "YouTube video '%s' yielded %d tool cards",
                                item.title,
                                len(tools),
                            )
                            for tool in tools:
                                card = normalize_raw_item(
                                    item,
                                    tier,
                                    override_title=tool["title"],
                                    override_summary=tool["description"],
                                )
                                if await _insert_and_dedup(card, card_repo):
                                    new_cards += 1
                            await raw_repo.mark_processed(item.id)
                            continue
                    # If not a tool announcement or extraction returned empty,
                    # fall through to standard normalization below

                if _is_changelog_candidate(item, source_cfg):
                    # Split changelog into individual feature cards
                    entries = await split_changelog_item(item)
                    logger.info(
                        "Changelog '%s' split into %d entries",
                        item.title,
                        len(entries),
                    )

                    for entry in entries:
                        card = normalize_raw_item(
                            item,
                            tier,
                            override_title=entry["title"],
                            override_summary=entry["description"],
                        )
                        if await _insert_and_dedup(card, card_repo):
                            new_cards += 1

                elif (
                    item.collector_type == "scrape"
                    and _is_generic_title(item.title or "", item.source_name)
                ):
                    # Try to improve generic title via LLM
                    improved = await improve_generic_title(item)
                    if improved:
                        card = normalize_raw_item(
                            item,
                            tier,
                            override_title=improved["title"],
                            override_summary=improved["summary"],
                        )
                    else:
                        card = normalize_raw_item(item, tier)

                    if await _insert_and_dedup(card, card_repo):
                        new_cards += 1

                else:
                    # Standard normalization
                    card = normalize_raw_item(item, tier)
                    if await _insert_and_dedup(card, card_repo):
                        new_cards += 1

                await raw_repo.mark_processed(item.id)

            except Exception:
                logger.exception(
                    "Error processing raw item %d: '%s'",
                    item.id,
                    item.title,
                )

    logger.info("Processed items: %d new cards created", new_cards)
    return new_cards
