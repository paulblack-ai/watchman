---
phase: 05-wire-normalizer-and-health-digest
status: passed
verified: 2026-02-25
verifier: automated
score: 7/7
---

# Phase 5: Wire Normalizer and Health Digest — Verification

## Goal
Close critical pipeline gap -- connect normalizer and daily health digest to the scheduler so raw items become signal cards and persistent source failures get daily notifications.

## Must-Have Verification

### Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Scheduler calls run_normalizer_job on a recurring 15-minute interval | PASS | `schedule_normalizer_job` uses `IntervalTrigger(minutes=15)` in jobs.py:171, called from main.py:100 |
| 2 | URL dedup and content fingerprint dedup execute as part of normalization | PASS | `process_unprocessed` in normalizer.py computes `url_hash` and `content_fingerprint`, calls `is_duplicate`/`handle_duplicate` from deduplicator |
| 3 | Scheduler calls run_daily_digest_job once daily at 08:00 | PASS | `schedule_daily_digest_job` uses `CronTrigger(hour=8, minute=0)` in jobs.py:237, called from main.py:108 |
| 4 | Daily digest job skips gracefully when SLACK_BOT_TOKEN or SLACK_PAUL_USER_ID is missing | PASS | `run_daily_digest_job` checks both env vars at runtime (jobs.py:198-205), returns early with warning log |
| 5 | Normalizer job is scheduled unconditionally (no Slack dependency) | PASS | `schedule_normalizer_job` call in main.py:100 is outside `if slack_enabled:` block |
| 6 | Daily digest job is only scheduled when slack_enabled and SLACK_PAUL_USER_ID are present | PASS | Nested inside `if slack_enabled:` with additional `if os.environ.get("SLACK_PAUL_USER_ID")` check (main.py:103-108) |
| 7 | Full pipeline flow works: collection -> normalization -> scoring -> Slack delivery | PASS | All 4 stages scheduled in main.py: collection (setup_scheduler), normalization (schedule_normalizer_job), scoring (schedule_scoring_job inside setup_scheduler), delivery (schedule_delivery_job) |

### Artifacts

| Artifact | Expected | Status |
|----------|----------|--------|
| src/watchman/scheduler/jobs.py contains `run_normalizer_job` | Present | PASS |
| src/watchman/scheduler/jobs.py contains `run_daily_digest_job` | Present | PASS |
| src/watchman/main.py contains `schedule_normalizer_job` call | Present | PASS |
| tests/test_normalizer_job.py contains `test_run_normalizer_job_creates_cards` | Present | PASS |

### Key Links

| From | To | Via | Status |
|------|----|-----|--------|
| main.py | scheduler/jobs.py | schedule_normalizer_job, schedule_daily_digest_job | PASS |
| scheduler/jobs.py | processing/normalizer.py | process_unprocessed via asyncio.run() | PASS |
| scheduler/jobs.py | health/tracker.py | get_daily_digest via asyncio.run() | PASS |

## Requirement Cross-Reference

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| PROC-01 | Normalize raw items into structured signal cards | PASS | run_normalizer_job calls process_unprocessed() which normalizes raw items into SignalCard objects |
| PROC-02 | Deduplicate signals by URL hash | PASS | process_unprocessed calls is_duplicate which checks url_hash |
| PROC-03 | Deduplicate signals by content fingerprint | PASS | process_unprocessed computes content_fingerprint and checks via is_duplicate |
| SRC-04 | Monitor per-source health and alert via Slack | PASS | run_daily_digest_job calls get_daily_digest + send_daily_digest for failing sources |

## Test Results

- **Unit tests:** 10/10 passing in tests/test_normalizer_job.py
- **Full suite:** 79/79 passing across all test files
- **No regressions** introduced

## Score

**7/7 must-haves verified. Status: PASSED.**

All requirement IDs (PROC-01, PROC-02, PROC-03, SRC-04) are accounted for and verified against the codebase.
