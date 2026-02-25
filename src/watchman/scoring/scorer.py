"""Claude Haiku-based relevance scorer for signal cards."""

import logging
from pathlib import Path

import anthropic
import aiosqlite

from watchman.models.signal_card import SignalCard
from watchman.scoring.models import RubricScore
from watchman.scoring.rubric import RubricConfig, load_rubric
from watchman.storage.database import get_connection
from watchman.storage.repositories import CardRepository

logger = logging.getLogger(__name__)


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

    return f"""You are scoring an AI industry signal card for relevance to the IcebreakerAI tool registry.

## Signal Card

**Title:** {card.title}
**URL:** {card.url}
**Source:** {card.source_name} (Tier {card.tier})
**Summary:** {card.summary or 'No summary available.'}

## Scoring Rubric

Score each dimension from 0 to {rubric.score_scale} (0 = not relevant, {rubric.score_scale} = highly relevant).

{dimensions_text}

## Instructions

1. Score each dimension from 0-{rubric.score_scale} with a brief rationale (1-2 sentences).
2. Compute the composite_score as the weighted sum: {' + '.join(f'{name} * {dim.weight}' for name, dim in rubric.dimensions.items())}.
3. Set top_dimension to the dimension name with the highest weighted contribution to the composite score.

Respond with a JSON object matching the required schema."""


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
    client = anthropic.Anthropic()
    prompt = _build_scoring_prompt(card, rubric)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
        betas=["output-128k-2025-02-19"],
        output_config={
            "format": {
                "type": "json_schema",
                "name": "rubric_score",
                "schema": RubricScore.model_json_schema(),
            }
        },
    )

    return RubricScore.model_validate_json(response.content[0].text)


async def score_unscored_cards(db_path: Path, rubric_path: Path) -> int:
    """Find and score all unscored, non-duplicate signal cards.

    Scores each card sequentially (not parallel) to be rate-limit friendly.
    Persists scores to the database via CardRepository.

    Args:
        db_path: Path to the SQLite database.
        rubric_path: Path to the rubric YAML config.

    Returns:
        Number of cards successfully scored in this run.
    """
    rubric = load_rubric(rubric_path)
    scored_count = 0

    async with get_connection(db_path) as db:
        repo = CardRepository(db)
        unscored = await repo.find_unscored()

        if not unscored:
            logger.info("No unscored cards found — skipping scoring run")
            return 0

        logger.info("Found %d unscored cards to score", len(unscored))

        for card in unscored:
            try:
                logger.info(
                    "Scoring card %d: %s", card.id, card.title[:60]
                )
                rubric_score = await score_card(card, rubric)
                await repo.save_score(card.id, rubric_score)
                scored_count += 1
                logger.info(
                    "Scored card %d: composite=%.2f top_dim=%s",
                    card.id,
                    rubric_score.composite_score,
                    rubric_score.top_dimension,
                )
            except Exception:
                logger.exception(
                    "Failed to score card %d (%s)", card.id, card.title[:60]
                )
                # Continue scoring remaining cards despite failure
                continue

    logger.info("Scoring run complete: %d/%d cards scored", scored_count, len(unscored))
    return scored_count
