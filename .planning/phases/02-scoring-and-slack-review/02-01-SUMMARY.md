---
phase: 02-scoring-and-slack-review
plan: "01"
subsystem: scoring
tags: [anthropic, claude-haiku, pydantic, sqlite, yaml, scoring, rubric]

requires:
  - phase: 01-collection-pipeline
    provides: SignalCard model, CardRepository, database schema, scheduler jobs

provides:
  - Claude Haiku structured-output scoring pipeline for signal cards
  - 4-dimension rubric YAML config (taxonomy_fit, novel_capability, adoption_traction, credibility)
  - RubricScore and DimensionScore Pydantic v2 models
  - Phase 2 database migration (8 new columns: score + review + slack)
  - CardRepository scoring/review methods (save_score, find_unscored, find_top_scored_today, set_review_state, snooze_card)
  - Dedicated 30-min APScheduler scoring job
  - 15 pytest unit and integration tests

affects:
  - 02-02 (Slack review delivery uses scored cards and CardRepository review methods)
  - 03-enrichment (enrichment pipeline builds on scored cards)

tech-stack:
  added:
    - anthropic>=0.40 (Claude Haiku API client)
  patterns:
    - Structured LLM outputs via output_config.format json_schema
    - Idempotent database migrations via try/except per ALTER TABLE
    - Dedicated scheduler job pattern (scoring decoupled from collection jobs)

key-files:
  created:
    - src/watchman/scoring/__init__.py
    - src/watchman/scoring/models.py
    - src/watchman/scoring/rubric.py
    - src/watchman/scoring/scorer.py
    - src/watchman/config/rubric.yaml
    - tests/__init__.py
    - tests/test_scoring.py
  modified:
    - src/watchman/storage/database.py
    - src/watchman/storage/repositories.py
    - src/watchman/models/signal_card.py
    - src/watchman/scheduler/jobs.py
    - pyproject.toml

key-decisions:
  - "Use Claude Haiku (claude-haiku-4-5-20251001) for scoring — cost-effective, sufficient for relevance assessment"
  - "Rubric weights in YAML (not hardcoded) — taxonomy_fit 0.35, novel_capability 0.30, adoption_traction 0.20, credibility 0.15"
  - "Score breakdowns persisted as JSON string in score_breakdown column for audit trail"
  - "Dedicated 30-min scoring job added to scheduler instead of coupling scoring to each collector"
  - "Idempotent phase 2 migration via try/except around each ALTER TABLE — safe to run multiple times"

patterns-established:
  - "Scoring job: score_unscored_cards called every 30 min by APScheduler, processes sequentially (rate-limit friendly)"
  - "Review workflow: review_state enum (pending/approved/rejected/snoozed) on card, snooze_until for re-surface"
  - "CardRepository.find_top_scored_today: ORDER BY relevance_score DESC, tier ASC — score primary, tier tiebreaker"

requirements-completed: [PROC-04, PROC-05, PROC-06]

duration: 4min
completed: 2026-02-25
---

# Phase 2 Plan 01: Scoring Engine Summary

**Claude Haiku relevance scorer with 4-dimension YAML rubric, Phase 2 SQLite migration, and CardRepository review methods**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T02:25:51Z
- **Completed:** 2026-02-25T02:30:40Z
- **Tasks:** 2 of 2
- **Files modified:** 11

## Accomplishments

- Scoring pipeline: score_card calls Claude Haiku with structured json_schema output, returns RubricScore with composite score, per-dimension breakdown, and top contributing dimension
- Rubric config: 4 dimensions loaded from rubric.yaml with weights summing to 1.0 — weights configurable without code edits
- Database migration: 8 new columns added to cards table (score + review + slack); migration is idempotent
- CardRepository extended with 6 new methods for daily cap selection, review state management, and snooze support
- Scheduler integration: dedicated 30-min scoring job decoupled from collection jobs
- 15 tests: rubric loading, model validation, prompt building, mocked score_card (all passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Scoring models, rubric config, and database migration** - `c8f35b0` (feat)
2. **Task 2: Claude Haiku scorer and scheduler integration** - `61af866` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `src/watchman/scoring/__init__.py` - Scoring module package
- `src/watchman/scoring/models.py` - DimensionScore and RubricScore Pydantic v2 models
- `src/watchman/scoring/rubric.py` - RubricConfig loader (load_rubric function)
- `src/watchman/scoring/scorer.py` - Claude Haiku scorer (score_card, score_unscored_cards)
- `src/watchman/config/rubric.yaml` - Default rubric with 4 dimensions and daily cap settings
- `src/watchman/storage/database.py` - Phase 2 migration (migrate_phase2, called from init_db)
- `src/watchman/storage/repositories.py` - CardRepository with save_score, find_unscored, find_top_scored_today, set_review_state, snooze_card
- `src/watchman/models/signal_card.py` - Added 8 optional Phase 2 fields
- `src/watchman/scheduler/jobs.py` - run_scoring_job, schedule_scoring_job, setup_scheduler with rubric_path
- `pyproject.toml` - Added anthropic>=0.40 dependency, registered pytest marks
- `tests/test_scoring.py` - 15 unit and integration tests

## Decisions Made

- Used `output_config.format` with `json_schema` (not function calling) for structured LLM output — cleaner API
- Added `anthropic` to pyproject.toml dependencies and installed in venv (missing dependency, auto-fixed Rule 3)
- Registered `unit` and `integration` pytest marks in pyproject.toml to avoid warnings

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing anthropic package dependency**
- **Found during:** Task 2 (Claude Haiku scorer implementation)
- **Issue:** anthropic package not in pyproject.toml dependencies; scorer.py would fail to import
- **Fix:** Added `anthropic>=0.40` to pyproject.toml and ran pip install in venv
- **Files modified:** pyproject.toml
- **Verification:** `from watchman.scoring.scorer import score_card` succeeds
- **Committed in:** 61af866 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking dependency)
**Impact on plan:** Essential fix — scorer could not run without the anthropic client library.

## Issues Encountered

- Python version mismatch: system Python is 3.9.6 but project requires >=3.11. Resolved by using .venv (Python 3.13.11) for all commands.

## User Setup Required

None - no external service configuration required for scoring engine itself. Note: `ANTHROPIC_API_KEY` environment variable must be set at runtime for score_card to call the API.

## Next Phase Readiness

- Scoring pipeline fully operational: score_card + score_unscored_cards ready to call
- CardRepository has all methods needed by Phase 2 Plan 02 (Slack review delivery)
- find_top_scored_today and set_review_state are the primary entry points for the Slack digest
- No blockers for Phase 2 Plan 02

---
*Phase: 02-scoring-and-slack-review*
*Completed: 2026-02-25*
