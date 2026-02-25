"""Pydantic models for rubric-based scoring data."""

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    """Score for a single rubric dimension."""

    score: float = Field(ge=0.0, le=10.0, description="Dimension score from 0 to 10")
    rationale: str = Field(description="Brief rationale for the score")


class RubricScore(BaseModel):
    """Complete rubric score for a signal card across all 4 dimensions."""

    taxonomy_fit: DimensionScore = Field(
        description="How well the signal fits IcebreakerAI's taxonomy"
    )
    novel_capability: DimensionScore = Field(
        description="Whether this represents a genuinely new capability"
    )
    adoption_traction: DimensionScore = Field(
        description="Evidence of real-world adoption or traction"
    )
    credibility: DimensionScore = Field(
        description="Credibility of the source and information"
    )
    composite_score: float = Field(
        ge=0.0, le=10.0, description="Weighted composite score across all dimensions"
    )
    top_dimension: str = Field(
        description="Name of the dimension contributing most to the composite score"
    )
