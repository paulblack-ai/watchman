---
phase: 05-wire-normalizer-and-health-digest
plan: 01
subsystem: infra
tags: [apscheduler, normalizer, health-digest, slack]

# Dependency graph
requires:
  - phase: 01-collection-pipeline
    provides: process_unprocessed normalizer, get_daily_digest tracker, send_daily_digest alerter
provides:
  - Normalizer job wired into scheduler (15-min interval)
  - Daily health digest job wired into scheduler (daily 8 AM cron)
  - Full pipeline flow: collection -> normalization -> scoring -> Slack delivery
affects: [06-tech-debt-and-doc-sync]

# Tech tracking
tech-stack:
  added: []
  patterns: [scheduler-job-wiring, graceful-degradation-gating]

key-files:
  created:
    - tests/test_normalizer_job.py
  modified:
    - src/watchman/scheduler/jobs.py
    - src/watchman/main.py

key-decisions:
  - "Normalizer job scheduled unconditionally (no Slack dependency) since normalization is core pipeline"
  - "Daily digest gated on slack_enabled AND SLACK_PAUL_USER_ID at schedule time (not runtime)"
  - "source_configs built from full registry (not just enabled sources) for correct tier assignment"

patterns-established:
  - "Schedule-time gating: check env vars before registering job to avoid no-op scheduled tasks"

requirements-completed: [PROC-01, PROC-02, PROC-03, SRC-04]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 5 Plan 01: Wire Normalizer and Health Digest Summary

**Normalizer and daily health digest wired into APScheduler with 15-min normalization interval and daily 8 AM Slack digest**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25
- **Completed:** 2026-02-25
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Normalizer job calls process_unprocessed() every 15 minutes, converting raw items into deduplicated signal cards
- Daily health digest sends failing source summary to Slack at 08:00 AM when credentials are available
- Full pipeline flow now works end-to-end: collection -> normalization -> scoring -> Slack delivery
- 10 unit tests covering all 4 phase requirements (PROC-01, PROC-02, PROC-03, SRC-04)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add normalizer and daily digest job functions** - `38059a8` (feat)
2. **Task 2: Wire jobs into main.py** - `12a493e` (feat)
3. **Task 3: Add unit tests** - `68e6667` (test)

## Files Created/Modified
- `src/watchman/scheduler/jobs.py` - Added run_normalizer_job, schedule_normalizer_job, run_daily_digest_job, schedule_daily_digest_job
- `src/watchman/main.py` - Imported and wired normalizer (unconditional) and digest (Slack-gated) jobs
- `tests/test_normalizer_job.py` - 10 unit tests for normalizer and digest job functions

## Decisions Made
- source_configs built from full registry.sources (not enabled_sources) to avoid Tier 2 defaults for temporarily-disabled sources
- Normalizer scheduled unconditionally; digest gated on slack_enabled + SLACK_PAUL_USER_ID
- Daily digest reads credentials at runtime for resilience but is only scheduled when env vars are present

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Existing SLACK_BOT_TOKEN, SLACK_APP_TOKEN, and SLACK_PAUL_USER_ID env vars are used.

## Next Phase Readiness
- Pipeline gap closed: raw items now flow through normalization automatically
- Ready for Phase 6: Tech Debt and Doc Sync

---
*Phase: 05-wire-normalizer-and-health-digest*
*Completed: 2026-02-25*
