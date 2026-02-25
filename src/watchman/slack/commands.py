"""Slash command handler for /watchman add-source."""

import logging
import re
from pathlib import Path

import yaml
from slack_bolt import App

logger = logging.getLogger(__name__)

SOURCES_YAML_PATH = Path("src/watchman/config/sources.yaml")

USAGE_TEXT = (
    "*Watchman Bot Commands*\n\n"
    "`/watchman add-source <url> [tier]`\n"
    "  Add a new source. Tier defaults to 2 (1=official, 2=launch platforms, 3=changelogs).\n\n"
    "`/watchman help`\n"
    "  Show this help message."
)

_URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}"
    r"(?::\d+)?"
    r"(?:/[^\s]*)?$"
)


def _is_valid_url(url: str) -> bool:
    """Check that a URL matches the expected http/https pattern.

    Args:
        url: URL string to validate.

    Returns:
        True if the URL is structurally valid, False otherwise.
    """
    return bool(_URL_PATTERN.match(url.strip()))


def _detect_source_type(url: str) -> str:
    """Auto-detect whether a source URL is RSS or scrape.

    Checks the URL for common RSS path segments. Falls back to "scrape".

    Args:
        url: Source URL to inspect.

    Returns:
        "rss" if the URL looks like a feed, "scrape" otherwise.
    """
    rss_patterns = ["/feed", "/rss", ".xml", "/atom", "feed.xml", "rss.xml"]
    lower_url = url.lower().rstrip("/")
    if any(lower_url.endswith(pattern) or f"/{pattern.lstrip('/')}" in lower_url for pattern in rss_patterns):
        return "rss"
    return "scrape"


def _append_source_to_yaml(url: str, tier: int, source_type: str) -> None:
    """Append a new source entry to sources.yaml.

    Loads the existing YAML, adds the new entry, and writes it back.

    Args:
        url: Source URL.
        tier: Source tier (1, 2, or 3).
        source_type: "rss" or "scrape".

    Raises:
        FileNotFoundError: If sources.yaml does not exist.
        yaml.YAMLError: If the existing YAML is malformed.
    """
    if not SOURCES_YAML_PATH.exists():
        raise FileNotFoundError(f"Source config not found: {SOURCES_YAML_PATH}")

    with open(SOURCES_YAML_PATH, "r") as f:
        config = yaml.safe_load(f) or {}

    sources = config.get("sources", [])

    # Generate a name from the URL hostname
    try:
        from urllib.parse import urlparse

        hostname = urlparse(url).hostname or url
        name = hostname.replace("www.", "").split(".")[0].title()
    except Exception:
        name = url

    # Set frequency based on tier
    frequency_map = {1: "4h", 2: "12h", 3: "24h"}
    frequency = frequency_map.get(tier, "12h")

    new_source = {
        "name": name,
        "type": source_type,
        "url": url,
        "tier": tier,
        "frequency": frequency,
        "enabled": True,
    }

    sources.append(new_source)
    config["sources"] = sources

    with open(SOURCES_YAML_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Added source '%s' (Tier %d, %s) to %s", name, tier, source_type, SOURCES_YAML_PATH)


def register_commands(app: App) -> None:
    """Register Watchman slash command handlers on the Bolt App.

    Handles subcommands: add-source, help.

    Args:
        app: Configured Bolt App to register handlers on.
    """

    @app.command("/watchman")
    def handle_watchman_command(ack, command, respond):  # noqa: ANN001, ANN202
        """Handle /watchman slash commands."""
        ack()

        text = (command.get("text") or "").strip()

        if not text or text == "help":
            respond(USAGE_TEXT)
            return

        if text.startswith("add-source"):
            _handle_add_source(text, respond)
            return

        respond(
            f"Unknown command: `{text}`\n\n{USAGE_TEXT}"
        )


def _handle_add_source(text: str, respond) -> None:  # noqa: ANN001
    """Parse and execute the add-source subcommand.

    Expected format: `add-source <url> [tier]`

    Args:
        text: Full command text starting with "add-source".
        respond: Slack respond function for posting the reply.
    """
    parts = text.split()
    # parts[0] is "add-source"

    if len(parts) < 2:
        respond(
            "Usage: `/watchman add-source <url> [tier]`\n"
            "Example: `/watchman add-source https://example.com/feed 1`"
        )
        return

    url = parts[1]
    tier = 2  # default tier

    if len(parts) >= 3:
        try:
            tier = int(parts[2])
        except ValueError:
            respond(
                f"Invalid tier: `{parts[2]}`. Tier must be 1, 2, or 3.\n"
                "Usage: `/watchman add-source <url> [tier]`"
            )
            return

    if tier not in (1, 2, 3):
        respond(
            f"Invalid tier: `{tier}`. Tier must be 1, 2, or 3.\n"
            "Usage: `/watchman add-source <url> [tier]`"
        )
        return

    if not _is_valid_url(url):
        respond(
            f"Invalid URL: `{url}`\n"
            "URL must start with http:// or https://.\n"
            "Usage: `/watchman add-source <url> [tier]`"
        )
        return

    source_type = _detect_source_type(url)

    try:
        _append_source_to_yaml(url, tier, source_type)
        respond(
            f"Added `{url}` as Tier {tier} {source_type} source. "
            f"Restart Watchman for the new source to be scheduled."
        )
    except Exception as e:
        logger.exception("Failed to add source %s", url)
        respond(f"Failed to add source: {e}")
