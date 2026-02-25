"""Shared Anthropic client factory configured for OpenRouter."""
from __future__ import annotations

import os

import anthropic


def get_client() -> anthropic.Anthropic:
    """Create an Anthropic client configured to use OpenRouter.

    Returns:
        Anthropic client instance with OpenRouter base URL and API key.

    Raises:
        RuntimeError: If OPENROUTER_API_KEY environment variable is not set.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")
    return anthropic.Anthropic(
        base_url="https://openrouter.ai/api",
        api_key=api_key,
    )
