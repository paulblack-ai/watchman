"""Configuration loading for the Watchman source registry."""

import re
from pathlib import Path

import yaml

from watchman.models.source import SourceConfig, SourceRegistry


def load_sources(config_path: Path) -> SourceRegistry:
    """Load and validate source registry from YAML config file.

    Args:
        config_path: Path to sources.yaml file.

    Returns:
        Validated SourceRegistry instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config fails validation.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Source config not found: {config_path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError(f"Empty config file: {config_path}")

    return SourceRegistry.model_validate(raw)


def get_enabled_sources(registry: SourceRegistry) -> list[SourceConfig]:
    """Filter registry to only enabled sources.

    Args:
        registry: Full source registry.

    Returns:
        List of enabled SourceConfig instances.
    """
    return [s for s in registry.sources if s.enabled]


def parse_interval(freq: str) -> dict[str, int]:
    """Parse human-readable interval into APScheduler kwargs.

    Converts formats like '4h', '30m', '1d' into
    {'hours': 4}, {'minutes': 30}, {'days': 1}.

    Args:
        freq: Frequency string (e.g., '4h', '12h', '1d').

    Returns:
        Dict with APScheduler interval keyword argument.

    Raises:
        ValueError: If frequency format is invalid.
    """
    match = re.match(r"^(\d+)([hmd])$", freq)
    if not match:
        raise ValueError(f"Invalid frequency: {freq}. Use e.g. '4h', '12h', '1d'.")

    value = int(match.group(1))
    unit = match.group(2)
    unit_map = {"h": "hours", "m": "minutes", "d": "days"}

    return {unit_map[unit]: value}
