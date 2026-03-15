---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-02-25T20:37:04.113Z"
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 12
  completed_plans: 12
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Never miss a strategically relevant AI tool or capability update that should be in the IcebreakerAI tool registry. Reliable signal detection with human-in-the-loop quality control.
**Current focus:** All phases complete, human verification passed

## Current Position

Phase: 7 of 7 — All complete
Plan: All plans complete
Status: Human verification passed (7/7 tests), ready for milestone completion
Last activity: 2026-03-15 - Completed quick task 11: Fix Notion Poller for Select Properties

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: ~8 min
- Total execution time: ~49 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-collection-pipeline | 3 | ~30 min | ~10 min |
| 02-scoring-and-slack-review | 2 | ~8 min | ~4 min |
| 05-wire-normalizer-and-health-digest | 1 | ~5 min | ~5 min |

**Recent Trend:**
- Last 5 plans: 01-03, 02-01, 02-02, 04-02, 05-01
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
- Normalizer job scheduled unconditionally (no Slack dependency); source_configs from full registry
- Daily digest gated on slack_enabled + SLACK_PAUL_USER_ID at schedule time
- Changelog detection: source_name contains "Changelog" OR tier 3 + scrape collector
- Split cards get unique url_hash by appending #title to URL before hashing
- LLM imports lazy in normalizer to avoid hard anthropic dependency at module load
- JinaCollector added for sites blocking direct scrapers (uses r.jina.ai markdown API)
- Anthropic and Meta AI have no public RSS feeds; switched to Jina-based collection
- Changelog detection may need update: some changelogs now use "jina" collector type instead of "scrape"
- YouTube transcript scanning: keyword pre-filter gates transcript API calls, non-tool videos fall through to single-card normalization
- VentureBeat /category/ai/feed/ stale since Jan 2026; switched to /feed/ which has fresh daily AI content
- Figma /whats-new/ redirects to /release-notes/ (JS-rendered); switched from scrape to jina collector
- python-dotenv added to pyproject.toml (was missing from dependency list, discovered during EC2 migration)

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
| 2 | Clean up code pull (last 2 weeks releases) | 2026-02-25 | 7d1501f | [2-clean-up-code-pull-last-2-weeks-releases](./quick/2-clean-up-code-pull-last-2-weeks-releases/) |
| 3 | Changelog splitting, title improvement, View More Signals | 2026-02-25 | fe0e2ee | [3-disable-huggingface-split-changelogs-int](./quick/3-disable-huggingface-split-changelogs-int/) |
| 4 | View More Signals pagination handler | 2026-02-25 | 4411754 | [4-view-more-signals-in-increments-of-5](./quick/4-view-more-signals-in-increments-of-5/) |
| 5 | Fix view-more button text and Python 3.9 compat | 2026-02-25 | 5ee7cdb | [5-fix-view-more-signals-button-count-and-c](./quick/5-fix-view-more-signals-button-count-and-c/) |
| 6 | Fix broken source URLs and crawling methods | 2026-02-28 | f1d240a | [6-fix-broken-source-urls-and-crawling-meth](./quick/6-fix-broken-source-urls-and-crawling-meth/) |
| 7 | YouTube transcript scanning | 2026-03-01 | 3ec9706 | [7-youtube-transcript-scanning](./quick/7-youtube-transcript-scanning/) |
| 8 | Fix broken VentureBeat and Figma sources | 2026-03-13 | 763a8d7 | [8-fix-broken-watchman-sources-venturebeat-](./quick/8-fix-broken-watchman-sources-venturebeat-/) |
| 9 | Migrate Watchman to company EC2 instance | 2026-03-13 | 81110d8 | [9-migrate-watchman-to-company-ec2-instance](./quick/9-migrate-watchman-to-company-ec2-instance/) |
| 10 | Notion migration: replace Slack review surface | 2026-03-14 | cfd5a30 | [10-watchman-notion-migration-replace-slack-](./quick/10-watchman-notion-migration-replace-slack-/) |
| 11 | Fix Notion poller for select-type properties | 2026-03-15 | 2feb012 | [11-fix-notion-poller-for-select-properties](./quick/11-fix-notion-poller-for-select-properties/) |

## Session Continuity

Last session: 2026-03-15
Stopped at: Completed quick task 11 (Fix Notion poller for select-type properties)
Resume file: .planning/phases/07-audit-gap-closure-runtime-fixes/.continue-here.md
