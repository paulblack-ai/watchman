# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Never miss a strategically relevant AI tool or capability update that should be in the IcebreakerAI tool registry. Reliable signal detection with human-in-the-loop quality control.
**Current focus:** Phase 2: Scoring and Slack Review (COMPLETE)

## Current Position

Phase: 2 of 4 (Scoring and Slack Review)
Plan: 2 of 2 in current phase -- COMPLETE
Status: Phase 2 complete, ready for Phase 3
Last activity: 2026-02-25 - Completed quick task 1: Switch LLM calls to OpenRouter

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: ~8 min
- Total execution time: ~44 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-collection-pipeline | 3 | ~30 min | ~10 min |
| 02-scoring-and-slack-review | 2 | ~8 min | ~4 min |

**Recent Trend:**
- Last 5 plans: 01-01, 01-02, 01-03, 02-01, 02-02
- Trend: Steady execution

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Claude Haiku (claude-haiku-4-5-20251001) used for scoring via structured json_schema output
- Rubric weights in YAML (not hardcoded): taxonomy_fit 0.35, novel_capability 0.30, adoption_traction 0.20, credibility 0.15
- Scoring decoupled from collection: dedicated 30-min APScheduler job
- Phase 2 DB migration is idempotent (try/except per ALTER TABLE)
- Slack Bolt with Socket Mode (no public webhook needed, works behind firewall)
- Daemon thread for Socket Mode handler (exits cleanly with main process)
- Graceful degradation: missing Slack tokens disable Slack but scheduler continues
- asyncio.run() bridge in Bolt action handlers (handlers are sync, DB methods are async)
- card_id as button value (integer round-trip for DB lookup)
- Daily delivery saves slack_message_ts per card (enables in-place chat_update)
- slack-bolt>=1.18 added as project dependency

### Pending Todos

None yet.

### Blockers/Concerns

- IcebreakerAI tool registry schema must be obtained before Phase 3 enrichment code is written (assigned to Phase 1 as INFRA-02)
- Slack workspace and bot credentials need to be configured before running Watchman with Slack enabled (SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID)
- Tier 3 scrape source list needs to be finalized for the starter 15-20 sources
- OPENROUTER_API_KEY environment variable must be set at runtime for scoring and enrichment to work

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Switch LLM calls to OpenRouter | 2026-02-25 | 76f9351 | [1-switch-to-openrouter](./quick/1-switch-to-openrouter/) |

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 02-02-PLAN.md (Slack review interface)
Resume file: None
