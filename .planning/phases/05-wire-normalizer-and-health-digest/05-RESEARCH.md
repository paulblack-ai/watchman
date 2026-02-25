# Phase 5: Wire Normalizer and Health Digest - Research

**Researched:** 2026-02-25
**Domain:** APScheduler job wiring, async/sync bridge pattern, Python codebase integration
**Confidence:** HIGH

## Summary

Phase 5 is a gap-closure phase, not a greenfield build. The v1 audit identified two unwired pipeline fragments: `process_unprocessed()` in `processing/normalizer.py` is never called by the scheduler, meaning raw items collected by all three collectors never become signal cards; and `send_daily_digest()` in `health/alerter.py` (backed by `get_daily_digest()` in `health/tracker.py`) is defined but never scheduled, meaning persistent source failures have no ongoing notification after the initial alert.

The fix is surgical: add two new job functions to `scheduler/jobs.py` following the exact same async/sync bridge pattern already established by `run_scoring_job`, `run_enrichment_job`, and `collect_source`. Then wire those jobs into `main.py` via `setup_scheduler()` or `schedule_*` calls alongside the existing jobs. No new libraries, no schema migrations, and no new modules are required — the entire implementation lives in two files.

The most important constraint is that `process_unprocessed()` requires a `source_configs: dict[str, SourceConfig]` argument for tier lookup, which means the normalizer job must receive the source map built from the enabled sources list in `main.py`. The daily digest job requires Slack credentials (`SLACK_BOT_TOKEN` and `SLACK_PAUL_USER_ID`) and must only be scheduled when those env vars are present (consistent with existing graceful-degradation pattern).

**Primary recommendation:** Add `run_normalizer_job` and `schedule_normalizer_job` to `scheduler/jobs.py`, add `run_daily_digest_job` and `schedule_daily_digest_job` to `scheduler/jobs.py`, then call both from `main.py`. Follow the existing async/sync bridge and graceful-degradation patterns exactly — no new patterns introduced.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-01 | System normalizes raw items into structured signal cards (title, source, date, summary, URL, tier) | `process_unprocessed()` already does this; just needs to be called from scheduler. |
| PROC-02 | System deduplicates signals by URL hash before scoring | URL dedup already runs inside `process_unprocessed()` via `is_duplicate()` layer 1. Needs scheduling. |
| PROC-03 | System deduplicates signals by content fingerprint (normalized title + date) to catch cross-source duplicates | Content fingerprint dedup runs inside `process_unprocessed()` via `is_duplicate()` layer 2. Needs scheduling. |
| SRC-04 | System monitors per-source health and alerts via Slack when a source yields zero results for 2+ consecutive runs | Individual alert fires at first detection (consecutive_zeros == 2). Daily digest (`get_daily_digest` + `send_daily_digest`) defined but never scheduled — needs a daily cron job. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | >=3.10,<4 (BackgroundScheduler) | Scheduling recurring jobs | Already used in project; `IntervalTrigger` and `CronTrigger` both in use |
| aiosqlite | >=0.20 | Async SQLite for `process_unprocessed()` | Already used throughout |
| slack-sdk | >=3.0 (WebClient) | `send_daily_digest()` HTTP calls | Already imported in `health/alerter.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | `asyncio.run()` bridge for APScheduler thread pool | All async functions need wrapping — consistent with existing jobs |
| logging | stdlib | Structured logging per job | Consistent with all existing job functions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Adding jobs directly in `setup_scheduler()` | Dedicated `schedule_*` functions | Dedicated functions keep `setup_scheduler` small and make jobs individually testable; follow existing pattern |
| Passing source_configs as a dict | Passing full SourceRegistry | Dict by name is simpler for the hot lookup path inside normalizer |

**Installation:** No new packages required.

## Architecture Patterns

### Recommended Project Structure

No new files. Changes confined to:

```
src/watchman/
├── scheduler/
│   └── jobs.py          # ADD: run_normalizer_job, schedule_normalizer_job,
│                        #      run_daily_digest_job, schedule_daily_digest_job
└── main.py              # ADD: calls to schedule_normalizer_job, schedule_daily_digest_job
```

### Pattern 1: Async/Sync Bridge (established)

**What:** APScheduler runs jobs in a thread pool; all business logic is async. Every job wraps its async call with `asyncio.run()`.

**When to use:** Every job function in `scheduler/jobs.py` — this is the only pattern used in the project.

**Example (from `scheduler/jobs.py` lines 57–74):**
```python
def run_scoring_job(db_path: Path, rubric_path: Path) -> None:
    """Sync wrapper that runs async scoring via asyncio.run()."""
    from watchman.scoring.scorer import score_unscored_cards  # noqa: PLC0415
    try:
        scored = asyncio.run(score_unscored_cards(db_path, rubric_path))
        logger.info("Scoring job complete: %d cards scored", scored)
    except Exception:
        logger.exception("Scoring job failed")
```

The normalizer job follows this exactly:
```python
def run_normalizer_job(db_path: Path, source_configs: dict) -> None:
    """Sync wrapper that runs async normalization via asyncio.run()."""
    from watchman.processing.normalizer import process_unprocessed  # noqa: PLC0415
    try:
        new_cards = asyncio.run(process_unprocessed(db_path, source_configs))
        logger.info("Normalizer job complete: %d new cards created", new_cards)
    except Exception:
        logger.exception("Normalizer job failed")
```

### Pattern 2: Graceful Degradation (established)

**What:** Slack-dependent jobs are only scheduled when `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` are present. The daily digest also needs `SLACK_PAUL_USER_ID`.

**When to use:** Any job that makes outbound Slack API calls.

**Example (from `main.py` lines 92–94):**
```python
if slack_enabled:
    schedule_delivery_job(scheduler, db_path, rubric_path)
```

The daily digest job follows the same gate. The normalizer job has NO Slack dependency and should be scheduled unconditionally (like scoring and enrichment jobs).

### Pattern 3: Schedule Function Registration (established)

**What:** Each job type has a `schedule_*` function that registers it with the scheduler, making `main.py` a thin orchestrator.

**When to use:** All job registration — consistent with `schedule_scoring_job`, `schedule_enrichment_job`, `schedule_delivery_job`.

**Example:**
```python
def schedule_normalizer_job(
    scheduler: BackgroundScheduler, db_path: Path, source_configs: dict
) -> None:
    scheduler.add_job(
        run_normalizer_job,
        trigger=IntervalTrigger(minutes=15),  # Runs 2x as often as scoring
        args=[db_path, source_configs],
        id="normalize-raw-items",
        replace_existing=True,
    )
    logger.info("Scheduled normalizer job every 15 minutes")
```

### Pattern 4: Daily Cron for Health Digest

**What:** `send_daily_digest()` should fire once per day, similar to `deliver_daily_review_sync` (daily at 9 AM). A reasonable time is 8 AM to give Paul a morning health briefing before the review digest.

**When to use:** Any job that should fire once per day at a predictable time.

**Example:**
```python
def schedule_daily_digest_job(
    scheduler: BackgroundScheduler, db_path: Path
) -> None:
    scheduler.add_job(
        run_daily_digest_job,
        trigger=CronTrigger(hour=8, minute=0),
        args=[db_path],
        id="send-daily-health-digest",
        replace_existing=True,
    )
    logger.info("Scheduled daily health digest job at 08:00 AM")
```

### Anti-Patterns to Avoid

- **Calling `process_unprocessed()` inside `setup_scheduler()`:** Keep setup_scheduler focused on collection jobs. Use the existing `schedule_*` pattern for the normalizer job instead.
- **Scheduling digest job without credential check:** The `send_daily_digest()` in `health/alerter.py` requires `token` and `user_id`. If these are missing, Slack API will raise. Wrap with the same `SLACK_BOT_TOKEN` + `SLACK_PAUL_USER_ID` check from `health/tracker.py`.
- **Passing full SourceRegistry to the job:** The normalizer's `source_configs` parameter is `dict[str, SourceConfig]`. Build this dict in `main.py` before scheduling: `{s.name: s for s in enabled_sources}`.
- **Adding a DB migration:** Phase 5 adds no new tables or columns. No migration needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Job interval scheduling | Custom thread timer | `APScheduler IntervalTrigger` | Already in use; handles jitter, restart, error isolation |
| Daily cron trigger | `while True: sleep(86400)` | `APScheduler CronTrigger` | Already used for daily delivery job |
| Async-in-sync bridge | `asyncio.get_event_loop()` | `asyncio.run()` | Consistent with all existing jobs; safe in thread pool |

**Key insight:** Everything needed already exists. This phase is wiring, not building.

## Common Pitfalls

### Pitfall 1: Normalizer job scheduling frequency

**What goes wrong:** If the normalizer job runs AFTER the scoring job in the same cycle, new cards miss the scoring window. If it runs too infrequently, latency between collection and cards appearing in Slack grows.

**Why it happens:** The pipeline has strict ordering: collect → normalize → score → deliver. If the scoring job (every 30 min) fires before normalization completes, the raw items from this cycle won't be scored until the next scoring cycle.

**How to avoid:** Schedule the normalizer at a higher frequency than scoring (e.g., every 15 minutes), so raw items are normalized well before the 30-minute scoring job fires.

**Warning signs:** Cards appear in Slack with a 30-60 minute lag after collection.

### Pitfall 2: `source_configs` dict must include ALL sources, not just enabled

**What goes wrong:** The normalizer uses `source_configs.get(item.source_name)` to look up tier. If a raw item came from a disabled source that was later re-enabled, the lookup fails and defaults to Tier 2.

**Why it happens:** `main.py` currently passes only `enabled_sources` to `setup_scheduler`. If the dict is built only from enabled sources, items from sources that were previously enabled (when collected) but are now disabled will not have their tier set correctly.

**How to avoid:** Build `source_configs` from the full registry (`registry.sources`), not just enabled sources. This is a safe default since tier lookup is read-only.

**Warning signs:** All items from a temporarily-disabled source show up as Tier 2 after re-enable.

### Pitfall 3: Daily digest fires with no failing sources

**What goes wrong:** `send_daily_digest()` returns `True` immediately when `failing_sources` is empty. This is correct behavior, but logging should make this visible.

**Why it happens:** No bug — the function is designed this way. But without logging, an operator can't tell if the digest fired vs. was skipped vs. failed.

**How to avoid:** Log the result in `run_daily_digest_job`: "Daily digest sent (N sources failing)" or "Daily digest: no failing sources, skipped."

**Warning signs:** Silent runs in the log with no indication of digest state.

### Pitfall 4: `SLACK_PAUL_USER_ID` env var may be missing

**What goes wrong:** `send_daily_digest()` in `health/alerter.py` receives `token` and `user_id` as parameters. The caller (`health/tracker.py:check_and_alert`) reads them from `os.environ`. The daily digest job must do the same check before calling `send_daily_digest()`.

**Why it happens:** `SLACK_PAUL_USER_ID` is separate from `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`. The `slack_enabled` flag in `main.py` only checks bot and app tokens, not Paul's user ID.

**How to avoid:** In `run_daily_digest_job`, read `SLACK_BOT_TOKEN` and `SLACK_PAUL_USER_ID` from env and log a warning + return early if either is missing — identical to the pattern in `health/tracker.py:check_and_alert`.

**Warning signs:** `SlackApiError` in logs from the digest job.

### Pitfall 5: Import-time circular import risk

**What goes wrong:** Importing from `watchman.processing.normalizer` at module load time in `scheduler/jobs.py` could trigger circular imports if `normalizer.py` imports from `scheduler/`.

**Why it happens:** `normalizer.py` currently imports from `storage.database`, `storage.repositories`, `models.*`, and `processing.deduplicator` — no circular risk. But all other job runners defer their imports inside the function body with the `# noqa: PLC0415` comment.

**How to avoid:** Keep the import of `process_unprocessed` inside `run_normalizer_job` function body, consistent with all other job functions in `scheduler/jobs.py`.

**Warning signs:** `ImportError` or `CircularImportError` at startup.

## Code Examples

Verified patterns from existing codebase:

### Normalizer job (follows scoring job pattern exactly)
```python
# Source: src/watchman/scheduler/jobs.py (existing pattern)
def run_normalizer_job(db_path: Path, source_configs: dict) -> None:
    """Sync wrapper that runs async normalization via asyncio.run().

    Called by APScheduler's thread pool. Processes all unprocessed raw items,
    normalizing them into signal cards and deduplicating by URL and content.

    Args:
        db_path: Path to the SQLite database.
        source_configs: Dict of source name -> SourceConfig for tier lookup.
    """
    from watchman.processing.normalizer import process_unprocessed  # noqa: PLC0415

    try:
        new_cards = asyncio.run(process_unprocessed(db_path, source_configs))
        logger.info("Normalizer job complete: %d new cards created", new_cards)
    except Exception:
        logger.exception("Normalizer job failed")


def schedule_normalizer_job(
    scheduler: BackgroundScheduler, db_path: Path, source_configs: dict
) -> None:
    """Register a 15-minute interval normalizer job with the scheduler.

    Args:
        scheduler: The APScheduler BackgroundScheduler to add the job to.
        db_path: Path to the SQLite database.
        source_configs: Dict of source name -> SourceConfig for tier lookup.
    """
    scheduler.add_job(
        run_normalizer_job,
        trigger=IntervalTrigger(minutes=15),
        args=[db_path, source_configs],
        id="normalize-raw-items",
        replace_existing=True,
    )
    logger.info("Scheduled normalizer job every 15 minutes")
```

### Daily digest job (follows delivery job pattern + health/tracker credential check)
```python
# Source: src/watchman/scheduler/jobs.py (existing patterns combined)
def run_daily_digest_job(db_path: Path) -> None:
    """Sync wrapper that runs the daily health digest via asyncio.run().

    Called by APScheduler's thread pool once daily. Fetches all currently
    failing sources and sends a summary DM to Paul via Slack.

    Args:
        db_path: Path to the SQLite database.
    """
    import os  # noqa: PLC0415
    from watchman.health.tracker import get_daily_digest  # noqa: PLC0415
    from watchman.health.alerter import send_daily_digest  # noqa: PLC0415

    token = os.environ.get("SLACK_BOT_TOKEN")
    user_id = os.environ.get("SLACK_PAUL_USER_ID")

    if not token or not user_id:
        logger.warning("Slack credentials not configured, skipping daily health digest")
        return

    try:
        failing_sources = asyncio.run(get_daily_digest(db_path))
        if not failing_sources:
            logger.info("Daily health digest: no failing sources")
            return
        success = send_daily_digest(token=token, user_id=user_id, failing_sources=failing_sources)
        if success:
            logger.info("Daily health digest sent: %d failing sources", len(failing_sources))
        else:
            logger.warning("Daily health digest failed to send")
    except Exception:
        logger.exception("Daily digest job failed")


def schedule_daily_digest_job(
    scheduler: BackgroundScheduler, db_path: Path
) -> None:
    """Register a daily 8 AM health digest job with the scheduler.

    Args:
        scheduler: The APScheduler BackgroundScheduler to add the job to.
        db_path: Path to the SQLite database.
    """
    scheduler.add_job(
        run_daily_digest_job,
        trigger=CronTrigger(hour=8, minute=0),
        args=[db_path],
        id="send-daily-health-digest",
        replace_existing=True,
    )
    logger.info("Scheduled daily health digest job at 08:00 AM")
```

### main.py wiring additions
```python
# Source: src/watchman/main.py (additions after existing schedule_enrichment_job call)

# Build source_configs dict for normalizer tier lookup (use full registry for robustness)
source_configs = {s.name: s for s in registry.sources}

# Add normalizer job (runs unconditionally — no Slack dependency)
from watchman.scheduler.jobs import schedule_normalizer_job  # noqa: PLC0415
schedule_normalizer_job(scheduler, db_path, source_configs)

# Add daily digest job only when Slack credentials are available
if slack_enabled and os.environ.get("SLACK_PAUL_USER_ID"):
    from watchman.scheduler.jobs import schedule_daily_digest_job  # noqa: PLC0415
    schedule_daily_digest_job(scheduler, db_path)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.get_event_loop().run_until_complete()` | `asyncio.run()` | Python 3.10+ | `asyncio.run()` is the correct pattern for new event loop per call in thread pool context |
| APScheduler 4.x | APScheduler 3.x (pinned <4) | Project decision | APScheduler 4 has breaking API changes; project is pinned to 3.x deliberately |

**Deprecated/outdated:**
- `datetime.utcnow()` in `processing/deduplicator.py` line 63: deprecated in Python 3.12, should be `datetime.now(timezone.utc)` — but this is Phase 6 scope (tech debt), not Phase 5.

## Open Questions

1. **Normalizer job frequency**
   - What we know: Scoring runs every 30 minutes. Collection runs per-source (4h, 12h, 1d frequencies).
   - What's unclear: Whether 15 minutes is the right cadence or if it should run faster (e.g., every 5 minutes) or at the same rate as scoring (every 30 minutes).
   - Recommendation: 15 minutes is a safe default — fast enough to normalize before the next scoring cycle, slow enough to not thrash the database. Can be adjusted without code changes if APScheduler config is parameterized later.

2. **Daily digest scheduling gate: `slack_enabled` vs `SLACK_PAUL_USER_ID`**
   - What we know: `slack_enabled` = `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN`. Digest also needs `SLACK_PAUL_USER_ID`.
   - What's unclear: Should scheduling be gated on all three, or should the job be scheduled regardless and handle missing `SLACK_PAUL_USER_ID` internally?
   - Recommendation: Gate at scheduling time on `slack_enabled and os.environ.get("SLACK_PAUL_USER_ID")` — avoids scheduling a job that will always log a warning and do nothing. Consistent with how delivery job is gated on `slack_enabled`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` with `asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_normalizer_job.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROC-01 | `process_unprocessed()` converts raw items to signal cards | unit | `pytest tests/test_normalizer_job.py::test_run_normalizer_job_creates_cards -x` | ❌ Wave 0 |
| PROC-02 | URL dedup skips duplicate URLs during normalization | unit | `pytest tests/test_normalizer_job.py::test_url_dedup_in_normalizer_job -x` | ❌ Wave 0 |
| PROC-03 | Content fingerprint dedup skips similar-title items | unit | `pytest tests/test_normalizer_job.py::test_content_fingerprint_dedup_in_normalizer_job -x` | ❌ Wave 0 |
| SRC-04 | `run_daily_digest_job` sends digest when sources are failing | unit | `pytest tests/test_normalizer_job.py::test_daily_digest_sends_when_failing_sources -x` | ❌ Wave 0 |
| SRC-04 | `run_daily_digest_job` skips sending when no failing sources | unit | `pytest tests/test_normalizer_job.py::test_daily_digest_skips_when_no_failing_sources -x` | ❌ Wave 0 |
| SRC-04 | `run_daily_digest_job` skips when Slack credentials missing | unit | `pytest tests/test_normalizer_job.py::test_daily_digest_skips_without_credentials -x` | ❌ Wave 0 |
| PROC-01 + end-to-end | Scheduler registration: normalizer and digest jobs appear in job list | unit | `pytest tests/test_normalizer_job.py::test_schedule_functions_register_jobs -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_normalizer_job.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_normalizer_job.py` — covers PROC-01, PROC-02, PROC-03, SRC-04
- [ ] No new conftest.py needed — existing `tests/__init__.py` is sufficient; existing test fixtures pattern uses `unittest.mock` directly

*(Framework already installed: `pytest>=7.0`, `pytest-asyncio>=0.21` in `pyproject.toml` dev dependencies)*

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/watchman/scheduler/jobs.py` — existing async/sync bridge pattern, scheduler setup, all existing job functions
- Codebase inspection: `src/watchman/processing/normalizer.py` — `process_unprocessed()` signature and behavior
- Codebase inspection: `src/watchman/health/alerter.py` + `health/tracker.py` — `send_daily_digest()`, `get_daily_digest()` signatures and env var usage
- Codebase inspection: `src/watchman/main.py` — graceful degradation pattern, scheduler wiring, env var gates
- Codebase inspection: `.planning/v1-MILESTONE-AUDIT.md` — precise gap identification and root cause analysis
- Codebase inspection: `pyproject.toml` — APScheduler 3.x pinned, test framework configuration

### Secondary (MEDIUM confidence)
- Pattern inference: 15-minute normalizer frequency derived from 30-minute scoring cadence and typical collection frequencies (4h, 12h, 1d) — reasonable default with no strong evidence for a different value

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — entire stack already in use; no new dependencies
- Architecture: HIGH — patterns copied directly from existing production code
- Pitfalls: HIGH — derived from direct code inspection of the exact files being modified
- Test map: HIGH — test framework verified in pyproject.toml, test patterns verified from existing test files

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable codebase; valid until APScheduler major version changes or project refactor)
