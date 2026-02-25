---
phase: 04-gate-2-and-output
plan: 01
subsystem: slack, output
tags: [slack-bolt, block-kit, json-output, gate2, pydantic]

requires:
  - phase: 03-enrichment-pipeline
    provides: "Enrichment pipeline producing IcebreakerToolEntry data"
  - phase: 02-scoring-and-slack-review
    provides: "Gate 1 Slack action handler patterns and Block Kit card builders"
provides:
  - "Gate 2 Slack Block Kit cards showing enrichment details"
  - "Gate 2 action handlers (approve/reject/re-enrich)"
  - "JSON output writer producing IcebreakerAI-compatible files"
  - "Gate 2 delivery wired into enrichment pipeline completion"
  - "Phase 4 DB migration with gate2_state, enrichment_attempt_count, output_path"
affects: []

tech-stack:
  added: []
  patterns: ["Gate 2 action handler pattern mirroring Gate 1", "One-file-per-tool JSON output with no-overwrite"]

key-files:
  created:
    - "src/watchman/output/__init__.py"
    - "src/watchman/output/writer.py"
  modified:
    - "src/watchman/storage/database.py"
    - "src/watchman/storage/repositories.py"
    - "src/watchman/models/signal_card.py"
    - "src/watchman/slack/blocks.py"
    - "src/watchman/slack/actions.py"
    - "src/watchman/enrichment/pipeline.py"
    - "src/watchman/slack/app.py"

key-decisions:
  - "Gate 2 cards differentiated from Gate 1 via :mag: prefix and enrichment detail fields"
  - "One JSON file per tool: {sanitized_name}_{card_id}.json, no overwrite"
  - "Gate 2 delivery immediate after enrichment (not batched)"
  - "Re-enrichment capped at 2 retries (3 total attempts) with DB-persisted counter"
  - "Output directory configurable via WATCHMAN_OUTPUT_DIR env var (default ./output)"

patterns-established:
  - "Gate 2 action handler pattern: separate register_gate2_actions() function"
  - "deliver_gate2_card() called from enrichment pipeline completion path"
  - "Filename sanitization: re.sub(r'[^\\w\\-]', '_', name).lower()[:50]"

requirements-completed: [OUT-01, OUT-02, OUT-03]

duration: 8min
completed: 2026-02-24
---

# Phase 4 Plan 01: Gate 2 Core Summary

**Gate 2 Slack review with enrichment details, approve/reject/re-enrich actions, and JSON output writer for IcebreakerAI-compatible files**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-24
- **Completed:** 2026-02-24
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Phase 4 DB migration adds gate2_state, gate2_reviewed_at, gate2_slack_ts, enrichment_attempt_count, output_path columns
- Gate 2 Block Kit cards display enrichment details (capabilities, pricing, API surface) with approve/reject/re-enrich buttons
- JSON output writer writes validated IcebreakerToolEntry as pretty-printed JSON files to configurable output directory
- Gate 2 delivery wired into enrichment pipeline - cards posted to Slack immediately after enrichment completes
- Re-enrichment retry cap enforced at DB level with enrichment_attempt_count column

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration and model updates** - `32d2a0c` (feat)
2. **Task 2: Gate 2 blocks, actions, output writer** - `9a5ae0e` (feat)
3. **Task 3: Pipeline wiring and app registration** - `6655dfc` (feat)

## Files Created/Modified
- `src/watchman/storage/database.py` - Phase 4 migration (gate2_state, enrichment_attempt_count, output_path)
- `src/watchman/models/signal_card.py` - Phase 4 fields on SignalCard model
- `src/watchman/storage/repositories.py` - Gate 2 state methods (set_gate2_state, save_output_path, increment_enrichment_attempt, find_enriched_pending_gate2)
- `src/watchman/slack/blocks.py` - Gate 2 card builders (build_gate2_card_blocks, build_gate2_confirmed_blocks)
- `src/watchman/slack/actions.py` - Gate 2 action handlers (approve_gate2, reject_gate2, re_enrich)
- `src/watchman/output/__init__.py` - New output module
- `src/watchman/output/writer.py` - JSON file writer (write_tool_entry, _sanitize_filename)
- `src/watchman/enrichment/pipeline.py` - Gate 2 delivery after enrichment (deliver_gate2_card)
- `src/watchman/slack/app.py` - Gate 2 action registration

## Decisions Made
- Gate 2 cards use :mag: prefix header and two-column fields layout to differentiate from Gate 1
- JSON files use one-file-per-tool naming: {sanitized_name}_{card_id}.json
- No-overwrite policy: if file exists, skip silently
- Gate 2 delivery is immediate (not batched) to keep pipeline responsive
- Re-enrich button hidden when enrichment_attempt_count >= 3

## Deviations from Plan
None - plan executed as specified

## Issues Encountered
None

## User Setup Required
- Set `WATCHMAN_OUTPUT_DIR` environment variable for custom output directory (default: ./output)

## Next Phase Readiness
- Gate 2 core implementation complete, ready for testing (Plan 04-02)
- All action handlers registered and pipeline wiring verified

---
*Phase: 04-gate-2-and-output*
*Completed: 2026-02-24*
