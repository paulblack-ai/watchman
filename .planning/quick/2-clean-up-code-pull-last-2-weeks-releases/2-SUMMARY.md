---
phase: quick-02
plan: 01
subsystem: pipeline
tags: [sqlite, data-reset, collectors, scoring, slack-delivery]

requires:
  - phase: 01-collection-pipeline
    provides: BaseCollector, RSS/API/Scrape collectors, normalizer, scorer
  - phase: 02-scoring-and-slack-review
    provides: Scoring pipeline, Slack delivery
provides:
  - max_age_days date filtering on BaseCollector.run()
  - One-shot reset-and-collect script for pipeline resets
  - Clean database with only last-2-weeks signal cards
affects: [collection-pipeline, scheduler]

tech-stack:
  added: [python-dotenv]
  patterns: [date-filtered-collection, one-shot-pipeline-script]

key-files:
  created:
    - src/watchman/scripts/__init__.py
    - src/watchman/scripts/reset_and_collect.py
  modified:
    - src/watchman/collectors/base.py

key-decisions:
  - "max_age_days parameter added to BaseCollector.run() with None default for backward compatibility"
  - "DELETE FROM used instead of DROP TABLE to preserve schema during data wipe"
  - "Sequential source collection to avoid overwhelming APIs"

patterns-established:
  - "Date filtering at BaseCollector level: all collector types benefit from max_age_days"

requirements-completed: []

duration: 4min
completed: 2026-02-25
---

# Quick Task 2: Clean Up Code Pull (Last 2 Weeks Releases) Summary

**Wiped 1669 stale test cards, collected 52 fresh items from last 14 days across 18 sources, scored all via OpenRouter, delivered top 5 to Slack**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T20:48:48Z
- **Completed:** 2026-02-25T20:52:58Z
- **Tasks:** 3 (2 auto + 1 checkpoint auto-approved)
- **Files modified:** 3

## Accomplishments
- Added max_age_days date filtering to BaseCollector.run() (backward-compatible)
- Created one-shot reset_and_collect.py script: wipe -> collect -> normalize -> score -> deliver
- Wiped all 1669 stale testing cards; collected 52 fresh items from last 14 days
- All 52 cards scored via OpenRouter (0 failures); top 5 delivered to Slack channel C0AJ05BRVLY

## Task Commits

Each task was committed atomically:

1. **Task 1: Create one-shot reset-and-collect script with 2-week date filter** - `7d1501f` (feat)
2. **Task 2: Execute the reset-and-collect pipeline** - No commit (runtime output only, watchman.db is gitignored)
3. **Task 3: Verify Slack delivery and card quality** - Auto-approved (checkpoint)

## Files Created/Modified
- `src/watchman/scripts/__init__.py` - Package init for scripts module
- `src/watchman/scripts/reset_and_collect.py` - One-shot pipeline: wipe DB, collect, normalize, score, deliver
- `src/watchman/collectors/base.py` - Added max_age_days parameter to BaseCollector.run()

## Decisions Made
- Used max_age_days=None default to keep backward compatibility with existing scheduler
- DELETE FROM (not DROP TABLE) preserves schema during wipe, avoids re-creation issues
- Sequential source collection prevents API rate limit issues
- python-dotenv installed in venv for standalone .env loading

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing python-dotenv dependency**
- **Found during:** Task 2 (Pipeline execution)
- **Issue:** python-dotenv not installed in venv, ModuleNotFoundError on import
- **Fix:** Ran `.venv/bin/pip install python-dotenv`
- **Files modified:** None (runtime dependency only)
- **Verification:** Pipeline ran successfully after install
- **Committed in:** N/A (pip install, not source code)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal -- missing pip dependency resolved immediately.

## Issues Encountered
- Anthropic Blog RSS (404), Meta AI Blog RSS (404), Hacker News API (timeout), Product Hunt (403 Forbidden), Supabase Changelog (timeout) all failed to collect -- expected per plan ("some sources may return 0 items")
- VentureBeat AI, GitHub Trending, BetaList, Linear Changelog, Stripe Changelog returned items but all filtered out as older than 14 days
- System Python 3.9 incompatible with codebase (uses `str | None` union syntax) -- used .venv Python 3.13 instead

## Collection Results

| Source | Items |
|--------|-------|
| OpenAI Blog | 13 |
| TechCrunch AI | 20 |
| Google AI Blog | 8 |
| HuggingFace Blog | 7 |
| Notion Changelog | 1 |
| Figma Changelog | 1 |
| Vercel Changelog | 1 |
| Crescendo | 1 |
| 10 other sources | 0 (filtered/failed) |
| **Total** | **52** |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Database is clean with only recent signal cards
- Regular scheduler can still run normally (max_age_days defaults to None)
- Some source URLs may need updating (Anthropic, Meta AI returned 404)

---
*Quick Task: 02-clean-up-code-pull-last-2-weeks-releases*
*Completed: 2026-02-25*
