---
phase: 07-audit-gap-closure-runtime-fixes
plan: 01
subsystem: infra
tags: [collectors, datetime, timezone, gate2, registry, sqlite]

requires:
  - phase: 01-collection-pipeline
    provides: collector registry pattern, raw_item and signal_card models
  - phase: 04-gate2-and-output
    provides: Gate 2 state management in repositories
provides:
  - Fixed collector registration via package-level import
  - Timezone-aware datetime defaults for RawItem and SignalCard
  - Conditional gate2_reviewed_at timestamp logic
affects: []

tech-stack:
  added: []
  patterns:
    - "Import from package __init__.py to trigger registration side effects"
    - "datetime.now(timezone.utc) over deprecated datetime.utcnow()"
    - "Conditional SQL branching for state-dependent timestamp writes"

key-files:
  created:
    - tests/test_collector_registry.py
  modified:
    - src/watchman/scheduler/jobs.py
    - src/watchman/models/raw_item.py
    - src/watchman/models/signal_card.py
    - src/watchman/storage/repositories.py
    - tests/test_gate2.py

key-decisions:
  - "Used timezone.utc (not datetime.UTC alias) to match existing codebase pattern in deduplicator.py and collectors"
  - "Python if/else branching in set_gate2_state rather than SQL CASE expression for clarity"

patterns-established:
  - "Import get_collector from watchman.collectors (not .base) to ensure registry is populated"

requirements-completed: [COLL-01, COLL-02, COLL-03, COLL-04]

duration: 5min
completed: 2026-02-25
---

# Phase 7 Plan 01: Runtime Fixes Summary

**Fixed collector registry import path, timezone-aware model defaults, and Gate 2 conditional timestamp with 7 targeted tests**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-25
- **Completed:** 2026-02-25
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Collector import in jobs.py now goes through package __init__.py, triggering all @register_collector decorators and populating COLLECTOR_REGISTRY with rss, api, scrape
- RawItem.fetched_at and SignalCard.created_at now produce timezone-aware UTC datetimes via datetime.now(timezone.utc)
- set_gate2_state("pending") no longer sets gate2_reviewed_at, while approval/rejection correctly sets it

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix collector import, datetime defaults, and Gate 2 timestamp logic** - `7026a83` (fix)
2. **Task 2: Add test coverage for collector registry and Gate 2 timestamp fix** - `9f112d5` (test)

## Files Created/Modified
- `src/watchman/scheduler/jobs.py` - Changed import from watchman.collectors.base to watchman.collectors
- `src/watchman/models/raw_item.py` - Replaced datetime.utcnow with datetime.now(timezone.utc)
- `src/watchman/models/signal_card.py` - Replaced datetime.utcnow with datetime.now(timezone.utc)
- `src/watchman/storage/repositories.py` - Added if/else branching for conditional gate2_reviewed_at
- `tests/test_collector_registry.py` - New file with 6 tests for registry and datetime awareness
- `tests/test_gate2.py` - Added test_gate2_pending_does_not_set_reviewed_at

## Decisions Made
- Used timezone.utc (not datetime.UTC alias) to match existing codebase pattern
- Used Python if/else branching in set_gate2_state rather than SQL CASE expression for clarity and testability

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three runtime bugs fixed and tested
- Full test suite: 86 passed, 0 failures
- Phase 7 gap closure complete

---
*Phase: 07-audit-gap-closure-runtime-fixes*
*Completed: 2026-02-25*
