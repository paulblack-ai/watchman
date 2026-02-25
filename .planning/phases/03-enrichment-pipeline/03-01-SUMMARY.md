---
phase: 03-enrichment-pipeline
plan: 01
subsystem: enrichment
tags: [anthropic, claude-sonnet, trafilatura, httpx, pydantic, web-scraping, llm-extraction]

requires:
  - phase: 02-scoring-and-slack-review
    provides: "Review state tracking (approved/rejected/snoozed) on signal cards"
provides:
  - "Enrichment module with web scraper, Claude Sonnet extractor, and pipeline orchestrator"
  - "Phase 3 database migration adding enrichment_state, enrichment_data, enrichment_error, enriched_at columns"
  - "CardRepository enrichment methods: find_approved_unenriched, save_enrichment, save_enrichment_error, set_enrichment_state"
  - "IcebreakerToolEntry validation via json_schema structured output"
affects: [03-enrichment-pipeline, 04-gate2-and-output]

tech-stack:
  added: []
  patterns:
    - "Enrichment module mirrors scoring module architecture (scraper + extractor + pipeline)"
    - "Claude Sonnet with json_schema structured output for reliable extraction"
    - "Idempotent Phase 3 migration following Phase 2 try/except pattern"
    - "Graceful scraping fallback: trafilatura failure -> card metadata only"

key-files:
  created:
    - src/watchman/enrichment/__init__.py
    - src/watchman/enrichment/scraper.py
    - src/watchman/enrichment/extractor.py
    - src/watchman/enrichment/pipeline.py
  modified:
    - src/watchman/storage/database.py
    - src/watchman/models/signal_card.py
    - src/watchman/storage/repositories.py

key-decisions:
  - "Enrichment uses IcebreakerToolEntry.model_json_schema() for json_schema structured output (same pattern as scoring)"
  - "source_url and discovered_at are overwritten post-extraction to ensure accuracy (LLM values ignored for these)"
  - "Pipeline loads each card in its own connection context for isolation"

patterns-established:
  - "Enrichment pipeline pattern: scrape_url -> enrich_card -> validate -> save_enrichment"
  - "Guard pattern: check review_state == 'approved' before enrichment (ENRCH-01)"

requirements-completed: [ENRCH-01, ENRCH-02, ENRCH-03]

duration: 5min
completed: 2026-02-24
---

# Phase 3 Plan 01: Enrichment Pipeline Summary

**Web scraper with trafilatura, Claude Sonnet extractor with json_schema output, and enrichment pipeline orchestrator with approval guard**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-24
- **Completed:** 2026-02-24
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Phase 3 database migration adding enrichment tracking columns (idempotent)
- Web scraper using httpx + trafilatura with graceful fallback on failure
- Claude Sonnet extractor producing validated IcebreakerToolEntry via json_schema structured output
- Pipeline orchestrator with approval-only guard and error state tracking

## Task Commits

Each task was committed atomically:

1. **Task 1: Phase 3 database migration and enrichment state tracking** - `c28ca8d` (feat)
2. **Task 2: Web scraper and Claude Sonnet extractor modules** - `1dcebe8` (feat)
3. **Task 3: Enrichment pipeline orchestrator** - `6e44a1a` (feat)

## Files Created/Modified
- `src/watchman/enrichment/__init__.py` - Empty init for enrichment package
- `src/watchman/enrichment/scraper.py` - Web page content extraction with httpx + trafilatura
- `src/watchman/enrichment/extractor.py` - Claude Sonnet structured extraction for IcebreakerToolEntry
- `src/watchman/enrichment/pipeline.py` - Orchestrates scrape -> extract -> validate -> store
- `src/watchman/storage/database.py` - Phase 3 migration (enrichment_state, enrichment_data, enrichment_error, enriched_at)
- `src/watchman/models/signal_card.py` - Added enrichment fields to SignalCard model
- `src/watchman/storage/repositories.py` - Added enrichment query methods to CardRepository

## Decisions Made
- Used claude-sonnet-4-20250514 model name (hardcoded, matching scoring's Haiku hardcode pattern)
- Overwrite source_url and discovered_at after extraction (LLM may hallucinate these)
- Scrape timeout set to 15 seconds (balance between coverage and responsiveness)

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required (uses existing OPENROUTER_API_KEY)

## Next Phase Readiness
- Enrichment module ready for wiring into Slack approve action (Plan 02)
- All repository methods available for integration
- Pipeline can be called directly for testing

---
*Phase: 03-enrichment-pipeline*
*Completed: 2026-02-24*
