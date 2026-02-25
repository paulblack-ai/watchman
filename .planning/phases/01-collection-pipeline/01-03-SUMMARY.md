---
phase: 01-collection-pipeline
plan: 03
subsystem: processing, health
tags: [deduplication, normalization, slack-sdk, difflib]

requires:
  - phase: 01-collection-pipeline/01
    provides: Pydantic models, SQLite database, repositories
provides:
  - Signal card normalization from raw items
  - Two-layer deduplication (URL hash + content fingerprint)
  - Source health tracking with consecutive zero detection
  - Slack DM alerting with suggested actions
  - Daily digest for ongoing failures
affects: [phase-2]

tech-stack:
  added: []
  patterns: [two-layer-dedup, health-tracking, slack-dm-alerts]

key-files:
  created:
    - src/watchman/processing/normalizer.py
    - src/watchman/processing/deduplicator.py
    - src/watchman/health/tracker.py
    - src/watchman/health/alerter.py
    - .env.example
  modified: []

key-decisions:
  - "Min 20-char title length guard for fuzzy matching to prevent false positives"
  - "Insert duplicate card then link (vs reject) for full audit trail"
  - "Graceful degradation without Slack credentials (log warning, don't crash)"

patterns-established:
  - "Two-layer dedup: fast URL hash then slow fuzzy title similarity"
  - "Health tracker records every run; consecutive_zeros computed from history"
  - "Slack alerts: individual on first detection, daily digest thereafter"

requirements-completed: [SRC-04, PROC-01, PROC-02, PROC-03]

duration: 5min
completed: 2026-02-24
---

# Phase 1 Plan 03: Processing and Health Summary

**Two-layer signal deduplication (URL hash + title fingerprint), raw-to-card normalization, and Slack DM health alerting**

## Performance

- **Duration:** 5 min
- **Tasks:** 2
- **Files created:** 7

## Accomplishments
- Normalizer converts RawItem to SignalCard with tier lookup and date fallback
- URL hash dedup prevents same-URL duplicates (fast, exact)
- Content fingerprint dedup catches cross-source duplicates (>85% title similarity, 7-day window)
- Health tracker detects consecutive zero-yield runs per source
- Slack DM alerter sends to Paul with source-type-specific suggestions
- Daily digest aggregates ongoing failures

## Task Commits

1. **Task 1: Normalization and deduplication** - `7c411cc` (feat)
2. **Task 2: Health tracking and alerting** - (same commit, combined)

## User Setup Required

**External services require manual configuration.** Environment variables needed:
- `SLACK_BOT_TOKEN` - From Slack App settings > OAuth & Permissions
- `SLACK_PAUL_USER_ID` - From Paul's Slack profile > Copy Member ID

See `.env.example` for template.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## Next Phase Readiness
- Complete collection pipeline: sources -> collectors -> raw items -> normalization -> dedup -> signal cards
- Health monitoring active for all sources
- Ready for Phase 2: scoring and Slack review

---
*Phase: 01-collection-pipeline*
*Completed: 2026-02-24*
