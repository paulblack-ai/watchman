"""Source configuration models for the Watchman source registry."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, HttpUrl, field_validator


class SourceConfig(BaseModel):
    """Configuration for a single signal source.

    Each source in sources.yaml maps to one SourceConfig instance.
    The type field determines which collector handles this source.
    """

    name: str
    type: Literal["rss", "api", "scrape", "jina", "youtube"]
    url: HttpUrl
    tier: Literal[1, 2, 3]
    frequency: str
    enabled: bool = True

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        """Validate frequency is in human-readable interval format (e.g., '4h', '12h', '1d')."""
        if not re.match(r"^\d+[hmd]$", v):
            raise ValueError(
                f"Invalid frequency format: '{v}'. "
                "Use human-readable intervals like '4h', '12h', '30m', '1d'."
            )
        return v


class SourceRegistry(BaseModel):
    """Registry of all signal sources loaded from sources.yaml."""

    sources: list[SourceConfig]
