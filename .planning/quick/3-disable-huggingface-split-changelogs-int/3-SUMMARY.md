---
phase: quick-3
plan: 01
subsystem: processing
tags: [llm, changelog-splitting, normalizer, slack, openrouter, claude-haiku]

requires:
  - phase: 01-collection-pipeline
    provides: "Raw item collection, normalizer, sources.yaml"
  - phase: 02-scoring-and-slack-review
    provides: "Scoring pipeline, Slack delivery, Block Kit cards"
provides:
  - "LLM-powered changelog page splitting into individual feature cards"
  - "Generic title improvement via LLM for scrape items"
  - "View More Signals button in Slack footer"
  - "Paginated card retrieval (find_next_scored_batch)"
affects: [normalizer, slack-delivery, blocks]

tech-stack:
  added: []
  patterns: ["Lazy LLM imports in normalizer", "Changelog detection by source name and tier", "URL hash disambiguation for split cards"]

key-files:
  created: []
  modified:
    - "src/watchman/processing/normalizer.py"
    - "src/watchman/slack/blocks.py"
    - "src/watchman/storage/repositories.py"

key-decisions:
  - "Changelog detection: source_name contains 'Changelog' OR tier 3 + scrape collector"
  - "Split cards get unique url_hash by appending #title to URL before hashing"
  - "Lazy import of llm_client to avoid hard dependency on anthropic at module load"
  - "Generic title detection via regex patterns and source name comparison"

patterns-established:
  - "LLM-powered content splitting: single raw item -> multiple signal cards"
  - "Override params on normalize_raw_item for title/summary substitution"

requirements-completed: [QT3-01, QT3-02, QT3-03, QT3-04, QT3-05]

duration: 9min
completed: 2026-02-25
---

# Quick Task 3: Changelog Splitting and Signal Quality Summary

**LLM-powered changelog page splitting into individual feature cards with specific titles, generic title improvement, and View More Signals button in Slack footer**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-25T21:07:34Z
- **Completed:** 2026-02-25T21:16:30Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Changelog pages (Notion, Figma, Vercel, Supabase) now split into individual feature cards with specific titles instead of one vague card per page
- Figma changelog split into 4 specific entries (AI Image Tools, Make Integration, Interactive Prototypes, Easier Color Variable Binding)
- Slack footer now shows "View N more signals" button when total scored cards exceed the daily delivery cap (5 of 70 = 65 remaining)
- Full pipeline ran end-to-end: 66 raw items collected -> 70 signal cards created (4 extra from splitting) -> 70 scored -> 5 delivered to Slack

## Task Commits

Each task was committed atomically:

1. **Task 1: LLM changelog splitting and title improvement** - `80eb053` (feat)
2. **Task 2: View More Signals button and paginated retrieval** - `40d574b` (feat)
3. **Task 3: Fix url_hash uniqueness and re-run pipeline** - `fe0e2ee` (fix)

## Files Created/Modified
- `src/watchman/processing/normalizer.py` - Added split_changelog_item(), improve_generic_title(), override params on normalize_raw_item(), updated process_unprocessed() with changelog splitting logic
- `src/watchman/slack/blocks.py` - Updated build_review_footer() to include View More Signals action button when total > showing
- `src/watchman/storage/repositories.py` - Added find_next_scored_batch() for paginated card retrieval with OFFSET

## Decisions Made
- Changelog detection uses source_name containing "Changelog" OR tier 3 + scrape type
- Split cards disambiguate url_hash by appending `#title` to the URL before hashing, preventing UNIQUE constraint failures
- LLM imports are lazy (inside function body) to avoid hard anthropic dependency at module import time
- Generic title detection uses regex patterns (starts with "what's new", "changelog", etc.) and source name substring matching

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UNIQUE constraint failure on url_hash for split changelog cards**
- **Found during:** Task 3 (Pipeline run)
- **Issue:** Split cards from the same changelog page share the same URL, causing sqlite3.IntegrityError on the url_hash UNIQUE constraint
- **Fix:** When override_title is set (split card), compute url_hash from `url#title` instead of just `url`
- **Files modified:** src/watchman/processing/normalizer.py
- **Verification:** Second pipeline run completed with no errors, all split cards inserted successfully
- **Committed in:** fe0e2ee (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for split card insertion. No scope creep.

## Issues Encountered
- HuggingFace was never in sources.yaml (plan noted this correctly) - no changes needed
- Some sources fail to collect (Anthropic Blog 404, Meta AI Blog 404, Product Hunt 403, Supabase timeout on first run) - pre-existing issues, not related to this task
- Linear and Stripe changelogs filtered out as older than 14 days

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Changelog splitting is production-ready
- View More Signals button is rendered but the action handler (to post next batch when clicked) needs to be added in a follow-up task
- Pre-existing source collection failures (Anthropic, Meta, Product Hunt) should be addressed separately

---
*Quick Task: 3-disable-huggingface-split-changelogs-int*
*Completed: 2026-02-25*
