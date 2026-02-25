"""Claude Haiku-based relevance scorer for signal cards."""
from __future__ import annotations


import asyncio
import logging
from pathlib import Path

import anthropic
import aiosqlite

from watchman.llm_client import get_client
from watchman.models.signal_card import SignalCard
from watchman.scoring.models import RubricScore
from watchman.scoring.rubric import RubricConfig, load_rubric
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)

SCORING_CONCURRENCY = 20


def _build_scoring_prompt(card: SignalCard, rubric: RubricConfig) -> str:
    """Build the scoring prompt for Claude Haiku.

    Args:
        card: Signal card to score.
        rubric: Rubric configuration with dimension descriptions and weights.

    Returns:
        Formatted prompt string.
    """
    dimensions_text = "\n".join(
        f"- **{name}** (weight: {dim.weight:.0%}): {dim.description.strip()}"
        for name, dim in rubric.dimensions.items()
    )

    return f"""Score this AI signal card for the IcebreakerAI tool registry.

Title: {card.title}
URL: {card.url}
Source: {card.source_name} (Tier {card.tier})
Summary: {card.summary or 'No summary available.'}

Rubric (0-{rubric.score_scale} per dimension):
{dimensions_text}

Composite = {' + '.join(f'{name}*{dim.weight}' for name, dim in rubric.dimensions.items())}

Respond with ONLY this JSON (no markdown, no extra text):
{{"taxonomy_fit":{{"score":N,"rationale":"..."}},"novel_capability":{{"score":N,"rationale":"..."}},"adoption_traction":{{"score":N,"rationale":"..."}},"credibility":{{"score":N,"rationale":"..."}},"composite_score":N,"top_dimension":"..."}}"""


async def score_card(card: SignalCard, rubric: RubricConfig) -> RubricScore:
    """Score a signal card using Claude Haiku structured outputs.

    Args:
        card: Signal card to score.
        rubric: Rubric configuration with dimension weights and descriptions.

    Returns:
        RubricScore with per-dimension scores, composite score, and top dimension.

    Raises:
        anthropic.APIError: If the Anthropic API call fails.
        ValueError: If the response cannot be parsed as a valid RubricScore.
    """
    client = get_client()
    prompt = _build_scoring_prompt(card, rubric)

    response = await asyncio.to_thread(
        client.messages.create,
        model="anthropic/claude-haiku-4.5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract JSON from response text (may be wrapped in markdown code fences)
    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()

    import json as _json

    parsed = _json.loads(text)
    # Handle nested structures: LLM sometimes wraps scores inside extra keys
    if "taxonomy_fit" not in parsed:
        # Try to find the scores nested one level deep
        for val in parsed.values():
            if isinstance(val, dict) and "taxonomy_fit" in val:
                parsed = val
                break
    return RubricScore.model_validate(parsed)


async def score_unscored_cards(db_path: Path, rubric_path: Path) -> int:
    """Find and score all unscored, non-duplicate signal cards.

    Processes cards in batches of SCORING_CONCURRENCY with progressive DB saves.

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.

    Returns:
        Number of cards successfully scored in this run.
    """
    rubric = load_rubric(rubric_path)
    scored_count = 0
    failed_count = 0

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        unscored = await repo.find_unscored()

        if not unscored:
            logger.info("No unscored cards found — skipping scoring run")
            return 0

        total = len(unscored)
        logger.info(
            "Found %d unscored cards to score (batch_size=%d)",
            total,
            SCORING_CONCURRENCY,
        )

        # Process in batches for progressive saves and rate-limit safety
        for i in range(0, total, SCORING_CONCURRENCY):
            batch = unscored[i : i + SCORING_CONCURRENCY]

            async def _score_one(card: SignalCard) -> tuple[int, RubricScore | None]:
                try:
                    rubric_score = await score_card(card, rubric)
                    return card.id, rubric_score
                except Exception:
                    logger.warning(
                        "Failed to score card %d (%s)",
                        card.id,
                        card.title[:60],
                    )
                    return card.id, None

            results = await asyncio.gather(*[_score_one(c) for c in batch])

            for card_id, rubric_score in results:
                if rubric_score is not None:
                    await repo.save_score(card_id, rubric_score)
                    scored_count += 1
                else:
                    failed_count += 1

            logger.info(
                "Progress: %d/%d scored (%d failed)",
                scored_count,
                total,
                failed_count,
            )

    logger.info(
        "Scoring run complete: %d/%d cards scored (%d failed)",
        scored_count,
        total,
        failed_count,
    )
    return scored_count
