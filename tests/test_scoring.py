"""Tests for the scoring module: rubric loading, models, and scorer."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from watchman.models.signal_card import SignalCard
from watchman.scoring.models import DimensionScore, RubricScore
from watchman.scoring.rubric import RubricConfig, RubricDimension, load_rubric
from watchman.scoring.scorer import _build_scoring_prompt, score_card

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RUBRIC_PATH = Path(__file__).parent.parent / "src" / "watchman" / "config" / "rubric.yaml"


@pytest.fixture
def rubric() -> RubricConfig:
    return load_rubric(RUBRIC_PATH)


@pytest.fixture
def sample_card() -> SignalCard:
    return SignalCard(
        title="GPT-5 Released with Native Tool Use",
        source_name="OpenAI Blog",
        date=datetime(2026, 2, 24),
        url="https://openai.com/blog/gpt-5",
        tier=1,
        summary="OpenAI released GPT-5 with native tool use and enhanced function calling.",
        collector_type="rss",
        url_hash=SignalCard.compute_url_hash("https://openai.com/blog/gpt-5"),
    )


@pytest.fixture
def sample_rubric_score() -> RubricScore:
    return RubricScore(
        taxonomy_fit=DimensionScore(score=9.0, rationale="Directly relevant AI model release"),
        novel_capability=DimensionScore(score=8.5, rationale="Introduces native tool use capability"),
        adoption_traction=DimensionScore(score=7.0, rationale="High-profile release with expected broad adoption"),
        credibility=DimensionScore(score=10.0, rationale="Official OpenAI announcement"),
        composite_score=8.6,
        top_dimension="taxonomy_fit",
    )


# ---------------------------------------------------------------------------
# Unit tests: load_rubric
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_rubric_returns_valid_config(rubric: RubricConfig) -> None:
    """load_rubric should return a RubricConfig with 4 dimensions."""
    assert isinstance(rubric, RubricConfig)
    assert len(rubric.dimensions) == 4


@pytest.mark.unit
def test_rubric_has_expected_dimensions(rubric: RubricConfig) -> None:
    """Rubric should contain exactly the 4 expected dimensions."""
    expected = {"taxonomy_fit", "novel_capability", "adoption_traction", "credibility"}
    assert set(rubric.dimensions.keys()) == expected


@pytest.mark.unit
def test_rubric_weights_sum_to_one(rubric: RubricConfig) -> None:
    """Rubric dimension weights should sum to approximately 1.0."""
    total = sum(d.weight for d in rubric.dimensions.values())
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"


@pytest.mark.unit
def test_rubric_default_cap_settings(rubric: RubricConfig) -> None:
    """Rubric should have correct default daily cap settings."""
    assert rubric.daily_cap_min == 3
    assert rubric.daily_cap_max == 7
    assert rubric.daily_cap_target == 5
    assert rubric.score_scale == 10


@pytest.mark.unit
def test_load_rubric_raises_on_missing_file() -> None:
    """load_rubric should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        load_rubric(Path("/nonexistent/rubric.yaml"))


# ---------------------------------------------------------------------------
# Unit tests: RubricScore / DimensionScore models
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dimension_score_accepts_valid_range() -> None:
    """DimensionScore should accept scores between 0 and 10."""
    score = DimensionScore(score=7.5, rationale="Good signal")
    assert score.score == 7.5
    assert score.rationale == "Good signal"


@pytest.mark.unit
def test_dimension_score_rejects_out_of_range() -> None:
    """DimensionScore should reject scores outside the 0-10 range."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DimensionScore(score=11.0, rationale="Too high")

    with pytest.raises(ValidationError):
        DimensionScore(score=-1.0, rationale="Negative")


@pytest.mark.unit
def test_rubric_score_validates_correctly(sample_rubric_score: RubricScore) -> None:
    """RubricScore should validate and store all fields correctly."""
    assert sample_rubric_score.composite_score == 8.6
    assert sample_rubric_score.top_dimension == "taxonomy_fit"
    assert sample_rubric_score.taxonomy_fit.score == 9.0
    assert sample_rubric_score.credibility.score == 10.0


@pytest.mark.unit
def test_rubric_score_serialization(sample_rubric_score: RubricScore) -> None:
    """RubricScore should serialize to JSON and deserialize back correctly."""
    json_str = sample_rubric_score.model_dump_json()
    restored = RubricScore.model_validate_json(json_str)
    assert restored.composite_score == sample_rubric_score.composite_score
    assert restored.top_dimension == sample_rubric_score.top_dimension
    assert restored.taxonomy_fit.score == sample_rubric_score.taxonomy_fit.score


@pytest.mark.unit
def test_rubric_score_composite_weighted_concept(rubric: RubricConfig) -> None:
    """Verify composite score calculation concept using rubric weights."""
    scores = {
        "taxonomy_fit": 8.0,
        "novel_capability": 7.0,
        "adoption_traction": 5.0,
        "credibility": 9.0,
    }
    expected_composite = sum(
        scores[dim] * rubric.dimensions[dim].weight
        for dim in scores
    )
    # With weights 0.35, 0.30, 0.20, 0.15:
    # 8*0.35 + 7*0.30 + 5*0.20 + 9*0.15 = 2.8 + 2.1 + 1.0 + 1.35 = 7.25
    assert abs(expected_composite - 7.25) < 0.01


# ---------------------------------------------------------------------------
# Unit tests: scoring prompt builder
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_scoring_prompt_includes_card_details(
    sample_card: SignalCard, rubric: RubricConfig
) -> None:
    """Scoring prompt should include card title, URL, source, and summary."""
    prompt = _build_scoring_prompt(sample_card, rubric)
    assert sample_card.title in prompt
    assert sample_card.url in prompt
    assert sample_card.source_name in prompt
    assert "taxonomy_fit" in prompt
    assert "novel_capability" in prompt


@pytest.mark.unit
def test_build_scoring_prompt_includes_weights(
    sample_card: SignalCard, rubric: RubricConfig
) -> None:
    """Scoring prompt should include dimension weights."""
    prompt = _build_scoring_prompt(sample_card, rubric)
    # Weights appear as percentages in the prompt
    assert "35%" in prompt
    assert "30%" in prompt
    assert "20%" in prompt
    assert "15%" in prompt


# ---------------------------------------------------------------------------
# Integration tests: mocked score_card
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_score_card_returns_rubric_score(
    sample_card: SignalCard, rubric: RubricConfig, sample_rubric_score: RubricScore
) -> None:
    """score_card should return a valid RubricScore when API responds correctly."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=sample_rubric_score.model_dump_json())]

    with patch("watchman.scoring.scorer.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        result = await score_card(sample_card, rubric)

    assert isinstance(result, RubricScore)
    assert result.composite_score == sample_rubric_score.composite_score
    assert result.top_dimension == sample_rubric_score.top_dimension


@pytest.mark.integration
async def test_score_card_uses_correct_model(
    sample_card: SignalCard, rubric: RubricConfig, sample_rubric_score: RubricScore
) -> None:
    """score_card should use claude-haiku-4.5 model via OpenRouter."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=sample_rubric_score.model_dump_json())]

    with patch("watchman.scoring.scorer.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        await score_card(sample_card, rubric)

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "anthropic/claude-haiku-4.5"


@pytest.mark.integration
async def test_score_card_sends_prompt(
    sample_card: SignalCard, rubric: RubricConfig, sample_rubric_score: RubricScore
) -> None:
    """score_card should send messages with user prompt."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=sample_rubric_score.model_dump_json())]

    with patch("watchman.scoring.scorer.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        await score_card(sample_card, rubric)

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
