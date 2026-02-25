# Roadmap: Watchman

## Overview

Watchman is a staged pipeline that collects AI ecosystem signals, scores them for relevance, surfaces them to Lauren via Slack for approval, and transforms approved signals into structured IcebreakerAI tool entries. The roadmap follows the pipeline's natural build order: collection and normalization first (nothing else works without signals in the database), then scoring and Slack review (the human gate), then enrichment (triggered only on approval), and finally the second approval gate and output emitter. Each phase delivers a verifiable, end-to-end capability that builds on the previous one.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Collection Pipeline** - Source registry, collectors, normalization, deduplication, and database foundation
- [x] **Phase 2: Scoring and Slack Review** - LLM scoring, daily volume cap, and Slack review queue with approve/reject/snooze
- [ ] **Phase 3: Enrichment Pipeline** - Approval-gated enrichment producing draft tool entries validated against IcebreakerAI schema
- [ ] **Phase 4: Gate 2 and Output** - Second approval gate and JSON output emitter completing the pipeline end-to-end
- [ ] **Phase 5: Wire Normalizer and Health Digest** - Connect normalizer and daily health digest to scheduler (gap closure)
- [ ] **Phase 6: Tech Debt and Doc Sync** - Fix deprecated APIs, sync docs with actual state (gap closure)

## Phase Details

### Phase 1: Collection Pipeline
**Goal**: Signals flow from external sources into normalized, deduplicated cards in the database, with source health monitored
**Depends on**: Nothing (first phase)
**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, COLL-01, COLL-02, COLL-03, COLL-04, PROC-01, PROC-02, PROC-03, INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. Running the scheduler pulls signals from at least 15 configured sources across all three tiers and writes raw items to the SQLite database
  2. Raw items are normalized into structured signal cards with title, source, date, summary, URL, and tier
  3. Duplicate signals (same URL or same title+date across sources) appear only once in the card table
  4. A source that returns zero results for 2+ consecutive runs triggers a Slack health alert
  5. IcebreakerAI tool registry schema is encoded as Pydantic models and available for downstream validation
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project foundation: package setup, Pydantic models, source registry, SQLite database, repositories
- [x] 01-02-PLAN.md — Collectors and scheduler: RSS/API/scrape collectors with APScheduler automation
- [x] 01-03-PLAN.md — Signal processing and health: normalization, deduplication, Slack health alerts

### Phase 2: Scoring and Slack Review
**Goal**: Lauren receives a curated, scored review queue in Slack and can approve, reject, or snooze each signal card
**Depends on**: Phase 1
**Requirements**: PROC-04, PROC-05, PROC-06, SLCK-01, SLCK-02, SLCK-03, SLCK-04
**Success Criteria** (what must be TRUE):
  1. Signal cards are scored against the IcebreakerAI relevance rubric using Claude Haiku, with score breakdowns persisted per signal
  2. Lauren receives no more than 3-7 scored cards per day in Slack, formatted with Block Kit
  3. Lauren can approve, reject, or snooze any card via Slack buttons, and the action updates signal state in the database
  4. Snoozed cards re-appear in the queue after 30 days
**Notes**:
  - Phase 2 should include a `/watchman add-source` slash command so Lauren can add sources directly from Slack (DEC-008)
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Scoring engine: Claude Haiku structured output scoring, rubric YAML config, DB migration, daily cap logic
- [x] 02-02-PLAN.md — Slack review interface: Bolt app, Block Kit cards, approve/reject/snooze actions, delivery job, /watchman slash command

### Phase 3: Enrichment Pipeline
**Goal**: Approved signals are automatically enriched with capabilities, pricing, API surface, and integration details, producing draft tool entries
**Depends on**: Phase 2
**Requirements**: ENRCH-01, ENRCH-02, ENRCH-03
**Success Criteria** (what must be TRUE):
  1. Enrichment triggers only when Lauren approves a signal in Gate 1 (never on unapproved signals)
  2. Enriched entries include capabilities, pricing, API surface, and integration hooks extracted by LLM
  3. Every enriched entry validates against the IcebreakerAI tool registry Pydantic schema before proceeding
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Core enrichment module: DB migration, web scraper, Claude Sonnet extractor, pipeline orchestrator
- [x] 03-02-PLAN.md — Integration and tests: wire enrichment into Slack approve action, fallback scheduler job, unit tests

### Phase 4: Gate 2 and Output
**Goal**: Lauren reviews enriched tool entries in a second Slack approval gate, and approved entries are written as IcebreakerAI-compatible JSON files
**Depends on**: Phase 3
**Requirements**: OUT-01, OUT-02, OUT-03
**Success Criteria** (what must be TRUE):
  1. Lauren receives enriched tool entries in Slack for second-round review with approve/reject buttons
  2. Approved entries are written as JSON files to the output directory in IcebreakerAI-compatible schema
  3. Rejected entries are marked as rejected and do not produce output files
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md -- Gate 2 core: DB migration, Block Kit cards, action handlers, JSON output writer, enrichment pipeline wiring
- [x] 04-02-PLAN.md -- Tests: Gate 2 flow tests and JSON output writer tests

### Phase 5: Wire Normalizer and Health Digest
**Goal**: Close critical pipeline gap — connect normalizer and daily health digest to the scheduler so raw items become signal cards and persistent source failures get daily notifications
**Depends on**: Phase 1
**Requirements**: PROC-01, PROC-02, PROC-03, SRC-04
**Gap Closure:** Closes gaps from v1 audit (normalizer never scheduled, daily digest never scheduled)
**Success Criteria** (what must be TRUE):
  1. Scheduler calls `process_unprocessed()` on a recurring schedule, converting raw items into signal cards
  2. URL dedup and content fingerprint dedup execute as part of normalization (both live inside `process_unprocessed()`)
  3. Scheduler calls `send_daily_digest()` once daily, delivering a health summary to Slack
  4. Full pipeline flow works end-to-end: collection → normalization → scoring → Slack delivery
**Plans**: 1 plan

Plans:
- [ ] 05-01-PLAN.md -- Wire normalizer and daily digest: add job functions to scheduler/jobs.py, wire into main.py, unit tests

### Phase 6: Tech Debt and Doc Sync
**Goal**: Fix deprecated APIs, sync documentation with actual state, and add missing verification artifacts
**Depends on**: Phase 5
**Requirements**: None (tech debt / documentation)
**Gap Closure:** Closes tech debt items from v1 audit
**Success Criteria** (what must be TRUE):
  1. All `datetime.utcnow()` calls replaced with `datetime.now(UTC)`
  2. SUMMARY docs reference OPENROUTER_API_KEY (not ANTHROPIC_API_KEY)
  3. REQUIREMENTS.md checkboxes match actual implementation status (SLCK-01–04, OUT-01–03 checked)
  4. Phases 1 and 3 have VERIFICATION.md files
**Plans**: 0 plans

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Collection Pipeline | 3/3 | Complete | 2026-02-24 |
| 2. Scoring and Slack Review | 2/2 | Complete | 2026-02-25 |
| 3. Enrichment Pipeline | 2/2 | Complete | 2026-02-25 |
| 4. Gate 2 and Output | 2/2 | Complete | 2026-02-25 |
| 5. Wire Normalizer and Health Digest | 0/1 | Planned | - |
| 6. Tech Debt and Doc Sync | 0/0 | Not started | - |
