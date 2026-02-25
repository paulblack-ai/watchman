# Project Research Summary

**Project:** Watchman — AI Ecosystem Monitoring Agent
**Domain:** Signal collection pipeline with human-in-the-loop Slack review
**Researched:** 2026-02-24
**Confidence:** HIGH

## Executive Summary

Watchman is a cron-driven intelligence pipeline that monitors AI ecosystem sources, scores signals against a relevance rubric, surfaces them to Lauren via Slack for approval, and enriches approved signals into structured IcebreakerAI tool entries. The canonical architecture for this class of system is a staged medallion pipeline (Bronze/Silver/Gold) where raw signals are progressively refined through collection, normalization, deduplication, scoring, and human review — with a strict human gate before any expensive enrichment runs. This pattern is well-established in data engineering and maps cleanly to a single-process, local cron agent.

The recommended stack is Python 3.11+, APScheduler 3.x (not 4.x — it is explicitly pre-release), SQLite as the integration bus, slack-bolt for the Slack interface, and the Anthropic SDK with instructor for structured LLM outputs. Claude Haiku 4.5 handles cheap scoring; Sonnet 4.5 is reserved for enrichment on approved signals only. The entire stack is synchronous — no asyncio complexity — which matches the cron execution model and keeps the system debuggable.

The two existential risks are signal fatigue (Lauren abandons the queue because it is too noisy) and silent scraper breakage (the system stops collecting without any alert). Both must be addressed in Phase 1 before Lauren sees the first Slack card. A hard daily cap of 3-7 cards, content-based deduplication, and per-source health monitoring are non-negotiable from day one — not v1.x additions.

## Key Findings

### Recommended Stack

Python 3.11+ on a single-process, synchronous architecture using APScheduler 3.x for per-source cron scheduling. SQLite is the integration bus between pipeline stages — each stage reads and writes to the database independently, which makes stages testable in isolation and state fully inspectable. The stack avoids framework bloat: no LangChain, no Celery, no async HTTP clients that would complicate the sync cron model.

**Core technologies:**
- **Python 3.11+**: Runtime — matches IcebreakerAI stack (mandatory constraint); 3.11+ performance gains over 3.10
- **APScheduler 3.11.x**: Scheduling — per-source cron frequencies; V4 is pre-release and explicitly unstable, do NOT use
- **SQLite (stdlib)**: State store and integration bus — zero-dependency, inspectable, sufficient for single-machine cron
- **anthropic SDK 0.81.x + instructor 1.x**: LLM calls with Pydantic-validated structured output; auto-retry on schema violations
- **slack-bolt 1.27.x**: Interactive Slack review interface with Block Kit buttons and Socket Mode for local dev
- **feedparser 6.0.x**: RSS/Atom parsing — 9.6M monthly downloads, handles malformed feeds
- **httpx 0.27.x**: HTTP client for API sources — synchronous, type-annotated, forward-looking standard
- **trafilatura 2.0.x**: Article text extraction for Tier 3 scrape sources — best-in-class content extraction accuracy
- **pydantic 2.x + pydantic-settings 2.x**: Signal card schemas and config/secrets management
- **datasketch 1.6.x**: MinHash/LSH near-duplicate detection for cross-source clustering
- **uv**: Package management — replaces pip + virtualenv; faster dependency resolution

### Expected Features

**Must have (table stakes):**
- Source registry (YAML config) with tiered scan frequencies — foundation that everything else depends on
- RSS + HTTP collectors with cron scheduling — Tier 1 and Tier 2 source coverage
- Signal normalization into uniform card schema — required for consistent Slack presentation
- URL hash deduplication — prevents duplicate flooding from day one
- Relevance scoring via Claude Haiku against IcebreakerAI rubric — surfaces only relevant signals
- Slack delivery with Approve / Reject / Snooze buttons — the entire review UX
- Enrichment triggered on first approval only — capabilities, pricing, API surface
- Draft tool entry generation in IcebreakerAI schema format — the actual deliverable
- Second Slack approval gate before pipeline entry — quality control before IcebreakerAI ingestion

**Should have (differentiators):**
- LLM-generated 2-sentence signal card summaries (Haiku) — reduces Lauren's time-to-decide
- Fuzzy title clustering (Levenshtein) — upgrade from URL-only dedup after v1 validation
- Per-source health monitoring with Slack alerts on zero-yield runs — prevents silent breakage
- Configurable snooze expiry — "resurface in 30 days if it gains traction" workflow
- `/watchman run` on-demand slash command — trigger collection outside cron schedule

**Defer (v2+):**
- Embedding-based semantic clustering — only if fuzzy matching produces false positives at scale
- AI newsletter ingestion (TLDR, The Batch) — fragile email parsing; web sources cover most content
- Slack home tab summary view — only if Lauren requests a portfolio view
- Multi-user review queue — out of scope; Lauren is the sole reviewer

**Anti-features (deliberately excluded):**
- Full-auto ingestion without human review — Lauren's trust depends on staying in the loop
- Real-time webhook monitoring — cron cadences are sufficient; added infrastructure complexity is not justified
- Web dashboard — Slack is the dashboard

### Architecture Approach

The architecture is a linear staged pipeline where the SQLite database acts as the integration bus between stages. No stage calls another stage directly — each reads its input from the DB and writes its output back to the DB. This makes every stage independently runnable, replayable on failure, and inspectable by querying the database. The Slack bot is the human gateway: Gate 1 approves signals for enrichment, Gate 2 approves enriched entries for IcebreakerAI output.

**Major components:**
1. **Source Registry + Scheduler** — YAML config drives APScheduler; adding a source = one YAML entry, zero code changes
2. **Collectors (RSS/API/Scrape)** — BaseCollector abstract class; one file per type; write raw items to `raw_items` table
3. **Normalizer + Deduplicator** — converts raw items to SignalCard schema; URL hash dedup then semantic fingerprint check
4. **LLM Scorer** — Haiku classifies cards against rubric; stores score breakdown (not just pass/fail) for calibration
5. **Slack Bot + Gate 1 Review Queue** — surfaces scored cards above threshold; handles approve/reject/snooze interactions
6. **Enricher + Schema Generator** — triggered only on Gate 1 approval; Haiku/Sonnet extracts capabilities, pricing, API surface; Pydantic validates against IcebreakerAI schema
7. **Gate 2 + Output Emitter** — second Slack approval gate; writes approved entries as JSON to `output/` directory

### Critical Pitfalls

1. **Signal fatigue kills adoption** — Lauren stops reviewing if queue exceeds ~7 cards/day. Hard daily volume cap and aggressive scoring threshold must be in place before the first Slack card is sent. Track approval rate weekly; if it drops below 20%, raise the threshold.

2. **Deduplication naivety creates phantom duplicates** — The same launch appears across 4-8 sources within 24 hours. URL-only dedup is insufficient. Content-based dedup (normalized title + date tuple) must be built alongside normalization in Phase 1, not added later.

3. **Silent scraper breakage goes undetected for weeks** — Websites change, scrapers break, the queue goes quiet. Per-source health monitoring (Slack alert to Paul on zero-yield for 2+ consecutive runs) must be built with the collectors, not deferred.

4. **IcebreakerAI schema incompatibility discovered late** — Enrichment prompts built against assumed schema fields require costly rework when integration is attempted. Obtain the actual IcebreakerAI JSON schema before writing any enrichment code.

5. **Enrichment runs before human approval** — The simpler path is enriching everything upfront; the correct path is gating enrichment on the Slack approve callback. Wiring this correctly requires it be designed as part of the Slack interaction flow from the start.

## Implications for Roadmap

Based on the architecture build order and pitfall phase mapping, four phases are suggested:

### Phase 1: Foundation — Collection, Normalization, and Deduplication

**Rationale:** The DB schema, source registry, collectors, normalizer, and deduplicator are preconditions for every other component. Nothing else can be built or tested until signals flow from sources into normalized, deduplicated cards in the database. This phase also addresses the three pitfalls that must be solved before Lauren sees the first card.

**Delivers:** A working collection pipeline that pulls from Tier 1 and Tier 2 sources, normalizes signals into SignalCard schema, deduplicates by URL hash and content fingerprint, and logs per-source health metrics.

**Addresses:**
- Source registry (YAML config) with tiered frequencies
- RSS + HTTP collectors
- Signal normalization
- URL hash + content-based deduplication
- Per-source health monitoring with Slack alerts
- IcebreakerAI schema obtained and Pydantic models written

**Avoids:** Silent scraper breakage (health monitoring built here), deduplication naivety (content-based dedup built here), schema incompatibility (IcebreakerAI schema locked before Phase 2).

**Research flag:** Standard patterns — no additional research needed. feedparser, httpx, SQLite, and APScheduler are well-documented.

---

### Phase 2: Scoring and Slack Review (Gate 1)

**Rationale:** LLM scoring and the Slack review interface are the heart of the system. They depend on normalized, deduplicated cards from Phase 1. The scoring threshold, daily volume cap, and Slack interaction handling must all be implemented together — they are the primary levers for preventing signal fatigue.

**Delivers:** Scored signal cards surfaced to Lauren's Slack review queue; Approve / Reject / Snooze actions that update signal state in the DB; daily volume cap enforced; score breakdown persisted for calibration.

**Uses:** Claude Haiku 4.5 for scoring via anthropic SDK + instructor; slack-bolt 1.27.x with Block Kit; APScheduler wired to run scoring pass after each collection cycle.

**Implements:** LLM Scorer, Slack Bot, Gate 1 Review Queue.

**Avoids:** Signal fatigue (daily cap + high threshold from day one); LLM score threshold drift (score breakdown stored for future calibration).

**Research flag:** Slack interactive messages have known gotchas (ack() timing, message update after button click, button state after decision). Review the Slack Bolt Python docs for action handler patterns before implementation. No external research needed beyond what PITFALLS.md documents.

---

### Phase 3: Enrichment Pipeline and Schema Generation

**Rationale:** Enrichment depends entirely on Gate 1 approval state from Phase 2. The enrichment trigger must be wired to the Slack approve callback — not to signal detection. This is also where the IcebreakerAI schema Pydantic models (obtained in Phase 1) are exercised for the first time.

**Delivers:** Enriched tool cards (capabilities, pricing, API surface, integration hooks) generated on approval; draft IcebreakerAI tool entries validated against Pydantic schema; Slack follow-up message to Lauren when enrichment completes.

**Uses:** Claude Haiku/Sonnet 4.5 for enrichment and schema generation; instructor for structured output; Pydantic validation against IcebreakerAI schema.

**Implements:** Enricher, Schema Generator.

**Avoids:** Enrichment waste on rejects (gated on approval callback); schema incompatibility (Pydantic validation on every generated entry).

**Research flag:** Standard patterns — enrichment via instructor + Pydantic is well-documented. The only unknown is the exact IcebreakerAI schema, which must be locked in Phase 1.

---

### Phase 4: Gate 2, Output, and Polish

**Rationale:** The second approval gate and output emitter are the final steps of the pipeline. They depend on enriched entries from Phase 3. This phase also includes v1.x improvements — LLM-generated summaries, fuzzy title clustering, and on-demand `/watchman run` command — which are deferred here to avoid blocking the core pipeline.

**Delivers:** Second Slack approval gate surfacing enriched entries for Lauren's sign-off; JSON output emitter writing approved entries to `output/` directory; LLM-generated signal card summaries; fuzzy title clustering upgrade; `/watchman run` slash command.

**Implements:** Output Emitter, Gate 2 Slack flow, LLM summary generation, Levenshtein clustering.

**Research flag:** Standard patterns — output emitter and Gate 2 are structural repeats of patterns established in Phase 2. No additional research needed.

---

### Phase Ordering Rationale

- DB schema and source registry must precede all other work — they are the integration bus
- Deduplication must precede scoring — scoring duplicates wastes tokens and inflates Lauren's queue
- Scoring must precede the Slack bot — the bot needs scored cards to surface
- Enrichment must be gated on Gate 1 approval — this dependency is structural, not optional
- Gate 2 and output depend on enriched entries — they are the final stage of a linear pipeline
- Health monitoring and IcebreakerAI schema acquisition belong in Phase 1 because the cost of deferring them is disproportionately high (weeks of missed signals; full schema rework)

### Research Flags

**Needs deeper review during planning:**
- **Phase 2 (Slack interactions):** Review Slack Bolt Python action handler docs for ack() timing, message update patterns, and button state management. PITFALLS.md documents the gotchas but implementation details need the official docs.
- **Phase 3 (IcebreakerAI schema):** The schema must be obtained from the IcebreakerAI codebase before Phase 3 planning begins. This is a dependency, not a research gap — but it must be locked.

**Standard patterns (skip research-phase):**
- **Phase 1:** feedparser, httpx, SQLite, APScheduler, pydantic-settings are all well-documented with stable APIs.
- **Phase 3:** instructor + Pydantic structured output from Anthropic is well-documented.
- **Phase 4:** Output emitter and Gate 2 are structural repeats of Phase 1-2 patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified on PyPI with current versions. APScheduler v4 warning verified in official migration docs. Pydantic V1/V2 incompatibility confirmed. |
| Features | MEDIUM | No direct competitors — Watchman is a custom internal tool. Table stakes defined by the system's downstream consumer (Lauren/IcebreakerAI), not market comparison. Core features are well-grounded; competitor feature analysis is indicative, not definitive. |
| Architecture | HIGH | Medallion pipeline + database-as-bus + HITL Slack gate is a well-established pattern. Build order derived from clear dependency analysis. Anti-patterns are confirmed from production HITL system case studies. |
| Pitfalls | HIGH | Signal fatigue, dedup naivety, and silent scraper breakage are documented failure modes from production monitoring systems. Slack interaction gotchas verified via n8n community and official Slack docs. |

**Overall confidence:** HIGH

### Gaps to Address

- **IcebreakerAI tool registry schema:** Must be obtained from the IcebreakerAI codebase before Phase 3 enrichment prompts are written. This is the single most important pre-Phase-3 prerequisite. Assign this as an explicit Phase 1 task.
- **Lauren's review bandwidth:** The 3-7 cards/day target is an estimate. Validate with Lauren in the first week and adjust the scoring threshold accordingly. Build the calibration mechanism in Phase 2 so threshold adjustment requires only a config change, not a code change.
- **Tier 3 (scrape) source list:** Which SaaS changelog and scrape-based sources are in scope is not defined in research. Finalize the starter source registry (15-20 sources across three tiers) before Phase 1 begins.
- **Slack workspace and bot credentials:** Socket Mode requires a Slack app to be created and configured with the correct scopes before Phase 2. This is a setup task, not a code task — but it blocks Phase 2 if deferred.

## Sources

### Primary (HIGH confidence)
- [APScheduler v4 migration warning](https://apscheduler.readthedocs.io/en/master/migration.html) — v4 pre-release status confirmed
- [anthropic PyPI v0.81.0](https://pypi.org/project/anthropic/) — current version confirmed Feb 2026
- [feedparser PyPI 6.0.12](https://libraries.io/pypi/feedparser) — version and download count confirmed
- [Slack API — approval workflow blueprint](https://api.slack.com/best-practices/blueprints/approval-workflows) — Slack HITL pattern
- [Slack API — interactive messages](https://api.slack.com/automation/interactive-messages) — Block Kit interaction handling
- [Databricks — Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture) — Bronze/Silver/Gold pipeline pattern
- [instructor — structured LLM outputs](https://python.useinstructor.com/) — Anthropic native support confirmed
- [trafilatura 2.0.x docs](https://trafilatura.readthedocs.io/en/latest/) — content extraction benchmarks

### Secondary (MEDIUM confidence)
- [n8n RSS + Slack workflow templates](https://n8n.io/workflows/6389-smart-rss-feed-monitoring-with-ai-filtering-baserow-storage-and-slack-alerts/) — HITL workflow patterns
- [Better Stack — alert fatigue guide](https://betterstack.com/community/guides/monitoring/best-practices-alert-fatigue/) — signal fatigue prevention
- [ScrapingBee — scraping challenges 2025](https://www.scrapingbee.com/blog/web-scraping-challenges/) — scraper breakage rates
- [SignalHub product page](https://getsignalhub.com) — competitor feature comparison
- [Feedly AI — deduplication skill](https://blog.feedly.com/deduplication-skill-feedlyai/) — cross-source dedup patterns
- [n8n HITL community thread](https://community.n8n.io/t/human-in-the-loop-slack-cannot-update-approve-disapprove-button-after-interaction/119544) — Slack button state gotcha

### Tertiary (LOW confidence)
- [Competitive intelligence automation 2026 (arisegtm)](https://arisegtm.com/blog/competitive-intelligence-automation-2026-playbook) — single marketing source; directionally useful only

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
