"""JSON output writer for IcebreakerAI-compatible tool entries."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from watchman.models.icebreaker import IcebreakerToolEntry

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 50


def _get_output_dir() -> Path:
    """Get the output directory from environment or default.

    Returns:
        Path to the output directory.
    """
    return Path(os.environ.get("WATCHMAN_OUTPUT_DIR", "./output"))


def _sanitize_filename(name: str) -> str:
    """Sanitize a tool name for use as a filename component.

    Replaces non-alphanumeric characters (except hyphens) with underscores,
    converts to lowercase, and truncates to MAX_NAME_LENGTH.

    Args:
        name: Raw tool name to sanitize.

    Returns:
        Sanitized filename-safe string.
    """
    return re.sub(r"[^\w\-]", "_", name).lower()[:MAX_NAME_LENGTH]


def write_tool_entry(entry: IcebreakerToolEntry, card_id: int) -> Path:
    """Write a validated tool entry as a JSON file to the output directory.

    Creates the output directory if it does not exist. Uses one-file-per-tool
    naming: {sanitized_name}_{card_id}.json. Does not overwrite existing files.

    Args:
        entry: Validated IcebreakerToolEntry to write.
        card_id: Card ID for unique filename.

    Returns:
        Path to the written (or existing) JSON file.
    """
    output_dir = _get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_filename(entry.name)
    filename = f"{safe_name}_{card_id}.json"
    filepath = output_dir / filename

    if filepath.exists():
        logger.info("Output file already exists, skipping: %s", filepath)
        return filepath

    filepath.write_text(entry.model_dump_json(indent=2))
    logger.info("Wrote tool entry to %s", filepath)
    return filepath
