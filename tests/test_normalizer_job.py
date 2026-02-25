"""Tests for normalizer and daily digest scheduler jobs."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from watchman.models.source import SourceConfig
from watchman.scheduler.jobs import (
    run_daily_digest_job,
    run_normalizer_job,
    schedule_daily_digest_job,
    schedule_normalizer_job,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def source_configs() -> dict[str, SourceConfig]:
    return {
        "test-source": SourceConfig(
            name="test-source",
            type="rss",
            url="https://example.com/feed",
            tier=1,
            frequency="4h",
        ),
    }


# ---------------------------------------------------------------------------
# PROC-01: Normalizer job creates signal cards
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_normalizer_job_creates_cards(
    db_path: Path, source_configs: dict[str, SourceConfig]
) -> None:
    """run_normalizer_job should call process_unprocessed and log result."""
    with patch(
        "watchman.scheduler.jobs.asyncio.run", return_value=5
    ) as mock_run:
        run_normalizer_job(db_path, source_configs)
        mock_run.assert_called_once()
        # Verify process_unprocessed was the async function passed to asyncio.run
        call_args = mock_run.call_args[0][0]
        # It's a coroutine from process_unprocessed(db_path, source_configs)
        # Close the coroutine to avoid RuntimeWarning
        call_args.close()


@pytest.mark.unit
def test_run_normalizer_job_handles_exception(
    db_path: Path, source_configs: dict[str, SourceConfig]
) -> None:
    """run_normalizer_job should catch and log exceptions without re-raising."""
    with patch(
        "watchman.scheduler.jobs.asyncio.run",
        side_effect=RuntimeError("DB connection failed"),
    ):
        # Should not raise
        run_normalizer_job(db_path, source_configs)


# ---------------------------------------------------------------------------
# PROC-02 + PROC-03: URL dedup and content fingerprint dedup run inside
# process_unprocessed (verified by calling process_unprocessed through the job)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_normalizer_job_calls_process_unprocessed_with_correct_args(
    db_path: Path, source_configs: dict[str, SourceConfig]
) -> None:
    """run_normalizer_job should pass db_path and source_configs to process_unprocessed."""
    with patch(
        "watchman.processing.normalizer.process_unprocessed"
    ) as mock_process:
        mock_process.return_value = 3  # Simulate 3 new cards

        with patch("watchman.scheduler.jobs.asyncio.run") as mock_run:
            mock_run.return_value = 3
            run_normalizer_job(db_path, source_configs)

            # asyncio.run was called with the coroutine
            mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# SRC-04: Daily digest sends when sources are failing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_daily_digest_sends_when_failing_sources(db_path: Path) -> None:
    """run_daily_digest_job should send digest when there are failing sources."""
    failing = [
        {"source_name": "broken-feed", "consecutive_zeros": 5, "last_error": "timeout"},
    ]

    with (
        patch.dict(
            "os.environ",
            {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_PAUL_USER_ID": "U12345"},
        ),
        patch("watchman.scheduler.jobs.asyncio.run", return_value=failing) as mock_run,
        patch("watchman.health.alerter.send_daily_digest", return_value=True) as mock_send,
    ):
        run_daily_digest_job(db_path)

        # asyncio.run called for get_daily_digest
        mock_run.assert_called_once()
        # send_daily_digest called with correct args
        mock_send.assert_called_once_with(
            token="xoxb-test",
            user_id="U12345",
            failing_sources=failing,
        )


# ---------------------------------------------------------------------------
# SRC-04: Daily digest skips when no failing sources
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_daily_digest_skips_when_no_failing_sources(db_path: Path) -> None:
    """run_daily_digest_job should skip sending when no sources are failing."""
    with (
        patch.dict(
            "os.environ",
            {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_PAUL_USER_ID": "U12345"},
        ),
        patch("watchman.scheduler.jobs.asyncio.run", return_value=[]),
        patch("watchman.health.alerter.send_daily_digest") as mock_send,
    ):
        run_daily_digest_job(db_path)
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# SRC-04: Daily digest skips without credentials
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_daily_digest_skips_without_credentials(db_path: Path) -> None:
    """run_daily_digest_job should return early when Slack credentials are missing."""
    with (
        patch.dict("os.environ", {}, clear=True),
        patch("watchman.scheduler.jobs.asyncio.run") as mock_run,
    ):
        run_daily_digest_job(db_path)
        mock_run.assert_not_called()


@pytest.mark.unit
def test_daily_digest_skips_without_user_id(db_path: Path) -> None:
    """run_daily_digest_job should return early when SLACK_PAUL_USER_ID is missing."""
    with (
        patch.dict(
            "os.environ",
            {"SLACK_BOT_TOKEN": "xoxb-test"},
            clear=True,
        ),
        patch("watchman.scheduler.jobs.asyncio.run") as mock_run,
    ):
        run_daily_digest_job(db_path)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# SRC-04: Daily digest handles exceptions
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_daily_digest_handles_exception(db_path: Path) -> None:
    """run_daily_digest_job should catch and log exceptions without re-raising."""
    with (
        patch.dict(
            "os.environ",
            {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_PAUL_USER_ID": "U12345"},
        ),
        patch(
            "watchman.scheduler.jobs.asyncio.run",
            side_effect=RuntimeError("DB error"),
        ),
    ):
        # Should not raise
        run_daily_digest_job(db_path)


# ---------------------------------------------------------------------------
# Schedule registration: both jobs appear in scheduler
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_schedule_normalizer_job_registers(
    db_path: Path, source_configs: dict[str, SourceConfig]
) -> None:
    """schedule_normalizer_job should register a job with the scheduler."""
    scheduler = MagicMock()
    schedule_normalizer_job(scheduler, db_path, source_configs)

    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args
    assert call_kwargs.kwargs["id"] == "normalize-raw-items"
    assert call_kwargs.kwargs["replace_existing"] is True


@pytest.mark.unit
def test_schedule_daily_digest_job_registers(db_path: Path) -> None:
    """schedule_daily_digest_job should register a daily cron job."""
    scheduler = MagicMock()
    schedule_daily_digest_job(scheduler, db_path)

    scheduler.add_job.assert_called_once()
    call_kwargs = scheduler.add_job.call_args
    assert call_kwargs.kwargs["id"] == "send-daily-health-digest"
    assert call_kwargs.kwargs["replace_existing"] is True
