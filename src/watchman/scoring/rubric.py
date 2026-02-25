"""Rubric configuration loader for scoring dimensions and weights."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class RubricDimension(BaseModel):
    """Configuration for a single rubric dimension."""

    weight: float
    description: str


class RubricConfig(BaseModel):
    """Full rubric configuration loaded from YAML."""

    dimensions: dict[str, RubricDimension]
    score_scale: int = 10
    daily_cap_min: int = 3
    daily_cap_max: int = 7
    daily_cap_target: int = 5


def load_rubric(path: Path) -> RubricConfig:
    """Load and validate rubric configuration from a YAML file.

    Args:
        path: Path to the rubric YAML file.

    Returns:
        Validated RubricConfig instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If the config fails validation.
    """
    if not path.exists():
        raise FileNotFoundError(f"Rubric config not found: {path}")

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Empty rubric config file: {path}")

    return RubricConfig.model_validate(raw)
