"""Bolt App initialization and Socket Mode handler setup."""

import logging
import os
import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from watchman.slack.actions import register_actions, register_gate2_actions, register_view_more_action
from watchman.slack.commands import register_commands

logger = logging.getLogger(__name__)


def create_slack_app() -> App:
    """Create and configure a Slack Bolt App with all action and command handlers.

    Reads SLACK_BOT_TOKEN from the environment. Registers action handlers
    (approve, reject, snooze, details) and slash command handlers (/watchman).

    Returns:
        Configured Bolt App instance.

    Raises:
        KeyError: If SLACK_BOT_TOKEN environment variable is not set.
    """
    app = App(token=os.environ["SLACK_BOT_TOKEN"])

    register_actions(app)
    register_gate2_actions(app)
    register_view_more_action(app)
    register_commands(app)

    logger.info("Slack Bolt App created with all handlers registered")
    return app


def start_socket_mode(app: App) -> threading.Thread:
    """Start Slack Socket Mode handler in a daemon thread.

    The daemon thread allows the process to exit cleanly without waiting
    for the Socket Mode connection to close.

    Args:
        app: Configured Bolt App instance.

    Returns:
        The daemon thread running the Socket Mode handler.

    Raises:
        KeyError: If SLACK_APP_TOKEN environment variable is not set.
    """
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])

    thread = threading.Thread(target=handler.start, daemon=True)
    thread.start()

    logger.info("Slack Socket Mode listener started in daemon thread")
    return thread
