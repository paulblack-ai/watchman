---
phase: quick-4
plan: 01
subsystem: slack
tags: [slack-bolt, pagination, action-handler, block-kit]

requires:
  - phase: quick-3
    provides: build_review_footer, find_next_scored_batch, count_scored_today
provides:
  - view_more_signals action handler for paginating scored cards
  - Unit tests for view_more handler (3 test cases)
affects: [slack-delivery, slack-actions]

tech-stack:
  added: []
  patterns: [asyncio.run bridge for Slack action handlers, per-card DB connection for review state]

key-files:
  created:
    - tests/test_view_more_signals.py
  modified:
    - src/watchman/slack/actions.py
    - src/watchman/slack/app.py

key-decisions:
  - "PAGE_SIZE=5 hardcoded in handler (matches daily_cap_target default)"
  - "Each card gets its own asyncio.run for set_review_state (same pattern as delivery.py)"

patterns-established:
  - "Pagination via button value JSON payload with offset/remaining"

requirements-completed: [QUICK-4]

duration: 2min
completed: 2026-02-25
---

# Quick Task 4: View More Signals in Increments of 5 Summary

**Slack action handler that paginates scored cards in batches of 5 with auto-updating footer and "View More" button**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T21:21:23Z
- **Completed:** 2026-02-25T21:23:20Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Wired up view_more_signals action handler that fetches next 5 scored cards and posts them as reviewable signal cards
- Footer automatically shows "View More" button when more cards remain, or no button on final page
- Cards without valid score_breakdown are silently skipped
- 3 unit tests covering normal pagination, final page, and score-skip scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: Add view_more_signals action handler and register it** - `34d86f4` (feat)
2. **Task 2: Add unit test for view_more handler logic** - `4411754` (test)

## Files Created/Modified
- `src/watchman/slack/actions.py` - Added register_view_more_action and _handle_view_more_signals handler
- `src/watchman/slack/app.py` - Registered view_more handler after gate2 actions
- `tests/test_view_more_signals.py` - 3 pytest test cases for pagination behavior

## Decisions Made
- PAGE_SIZE=5 hardcoded in handler, consistent with daily_cap_target default
- Each posted card saves review state in its own async DB connection (same pattern as delivery.py)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

---
*Quick Task: 4-view-more-signals-in-increments-of-5*
*Completed: 2026-02-25*
