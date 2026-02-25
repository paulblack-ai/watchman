# Requirements: Watchman

**Defined:** 2026-02-24
**Core Value:** Never miss a strategically relevant AI tool or capability update that should be in the IcebreakerAI tool registry. Reliable signal detection with human-in-the-loop quality control.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Source Management

- [x] **SRC-01**: System loads sources from a YAML config file with type (rss/api/scrape), URL, tier (1/2/3), and scan frequency per source
- [x] **SRC-02**: Adding a new source requires only a new YAML entry, zero code changes
- [x] **SRC-03**: System includes 15-20 starter sources across Tier 1 (structured/official), Tier 2 (launch platforms), and Tier 3 (SaaS changelogs)
- [x] **SRC-04**: System monitors per-source health and alerts via Slack when a source yields zero results for 2+ consecutive runs

### Collection

- [x] **COLL-01**: System runs scheduled collectors on per-source cron frequencies using APScheduler
- [x] **COLL-02**: RSS collector parses RSS/Atom feeds and writes raw items to the database
- [x] **COLL-03**: HTTP/API collector fetches structured API responses and writes raw items to the database
- [x] **COLL-04**: Scrape collector extracts article content from web pages and writes raw items to the database

### Signal Processing

- [x] **PROC-01**: System normalizes raw items into structured signal cards (title, source, date, summary, URL, tier)
- [x] **PROC-02**: System deduplicates signals by URL hash before scoring
- [x] **PROC-03**: System deduplicates signals by content fingerprint (normalized title + date) to catch cross-source duplicates
- [x] **PROC-04**: System scores signals against IcebreakerAI relevance rubric (taxonomy fit, novel capability, adoption/traction, credibility) using Claude Haiku
- [x] **PROC-05**: System enforces a daily volume cap (3-7 cards) to prevent signal fatigue
- [x] **PROC-06**: System persists score breakdown per signal for future calibration

### Slack Review (Gate 1)

- [ ] **SLCK-01**: System delivers scored signal cards to Lauren's Slack channel using Block Kit
- [ ] **SLCK-02**: Lauren can approve a signal card via Slack button
- [ ] **SLCK-03**: Lauren can reject a signal card via Slack button
- [ ] **SLCK-04**: Lauren can snooze a signal card via Slack button (default 30-day expiry, re-queues after expiry)

### Enrichment

- [x] **ENRCH-01**: System triggers enrichment only on Gate 1 approval (never on unapproved signals)
- [x] **ENRCH-02**: Enrichment extracts capabilities, pricing, API surface, and integration hooks using LLM
- [x] **ENRCH-03**: Enrichment output is validated against IcebreakerAI tool registry schema via Pydantic

### Output (Gate 2)

- [ ] **OUT-01**: System presents enriched tool entry to Lauren in Slack for second approval
- [ ] **OUT-02**: Lauren can approve or reject the enriched entry via Slack buttons
- [ ] **OUT-03**: Approved entries are written as JSON files to an output directory in IcebreakerAI-compatible schema

### Infrastructure

- [x] **INFRA-01**: SQLite database serves as integration bus between pipeline stages
- [x] **INFRA-02**: IcebreakerAI tool registry schema is obtained and encoded as Pydantic models before enrichment code is written
- [x] **INFRA-03**: System runs as a single-process cron agent on Paul's machine or AWS instance

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Signal Quality

- **QUAL-01**: LLM-generated 2-sentence signal card summaries to reduce Lauren's time-to-decide
- **QUAL-02**: Fuzzy title clustering (Levenshtein) upgrade from URL-only dedup
- **QUAL-03**: Embedding-based semantic clustering for high-volume scenarios

### Operations

- **OPS-01**: `/watchman run` on-demand Slack slash command to trigger collection outside cron schedule
- **OPS-02**: Configurable snooze expiry (default 30 days ships in v1; user-configurable expiry is v2)
- **OPS-03**: Slack home tab summary view of queued vs approved signals

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full-auto ingestion without human review | Lauren's trust depends on being in the loop; auto-ingestion errors are invisible and compound |
| Real-time streaming / webhook monitoring | Cron cadences are sufficient; added infrastructure complexity not justified for background workstream |
| Web dashboard / admin UI | Slack IS the dashboard; a web UI doubles the interface to maintain |
| Dev Twitter / X scraping | Noisy, expensive API, scraping violates ToS and breaks constantly |
| AI newsletter parsing (TLDR, The Batch) | Fragile email parsing; web sources cover most content; defer to v2+ |
| Multi-user review queue | Out of scope for v1; Lauren is sole reviewer; generalize only if second reviewer needed |
| Automatic source discovery | Source list is curated deliberately; auto-discovery undermines tiered architecture |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 1 | Complete |
| SRC-02 | Phase 1 | Complete |
| SRC-03 | Phase 1 | Complete |
| SRC-04 | Phase 1 | Complete |
| COLL-01 | Phase 1 | Complete |
| COLL-02 | Phase 1 | Complete |
| COLL-03 | Phase 1 | Complete |
| COLL-04 | Phase 1 | Complete |
| PROC-01 | Phase 1 | Complete |
| PROC-02 | Phase 1 | Complete |
| PROC-03 | Phase 1 | Complete |
| PROC-04 | Phase 2 | Complete |
| PROC-05 | Phase 2 | Complete |
| PROC-06 | Phase 2 | Complete |
| SLCK-01 | Phase 2 | Pending |
| SLCK-02 | Phase 2 | Pending |
| SLCK-03 | Phase 2 | Pending |
| SLCK-04 | Phase 2 | Pending |
| ENRCH-01 | Phase 3 | Complete |
| ENRCH-02 | Phase 3 | Complete |
| ENRCH-03 | Phase 3 | Complete |
| OUT-01 | Phase 4 | Complete |
| OUT-02 | Phase 4 | Complete |
| OUT-03 | Phase 4 | Complete |
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after roadmap creation*
