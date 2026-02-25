# Watchman — AI Tool Ecosystem Monitoring Agent

## What This Is

A monitoring agent that systematically tracks the AI tool ecosystem — frontier model releases, AI-native app launches, SaaS tools adding AI layers, and marketplace activity — and surfaces relevant signals to a human reviewer via Slack. Approved signals get enriched and transformed into structured tool entries that feed into the IcebreakerAI prompt generation pipeline.

## Core Value

Never miss a strategically relevant AI tool or capability update that should be in the IcebreakerAI tool registry. Reliable signal detection with human-in-the-loop quality control.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Source registry with configurable scan frequency per source
- [ ] Scheduled collectors that pull from registered sources (RSS, API, scrape)
- [ ] Signal normalization into structured "signal cards" (title, source, date, summary, links)
- [ ] Deduplication and clustering of same-event signals across sources
- [ ] Scoring against relevance rubric (taxonomy fit, novelty, traction, credibility)
- [ ] Slack bot integration for Lauren's review queue (approve/reject/snooze)
- [ ] Enrichment pipeline triggered on approval (capabilities, pricing, API surface, integration)
- [ ] Schema generation workflow producing draft structured tool entries
- [ ] Second approval gate before tool entry enters IcebreakerAI pipeline
- [ ] Expandable source registry (adding a source = adding a config entry)
- [ ] Tiered source architecture (Tier 1: structured/high-signal, Tier 2: launch platforms, Tier 3: SaaS changelogs)
- [ ] 15-20 starter sources across all tiers for MVP

### Out of Scope

- Full-auto ingestion without human review — Lauren's approval gate is non-negotiable for v1
- Real-time streaming/webhook-based monitoring — cron-based is sufficient
- Deep security/procurement evaluation of tools — surface + enriched cards only
- Integration with IcebreakerAI codebase directly — standalone first, integrate later
- Dev Twitter scraping, AI newsletter parsing — noisy sources deferred to future expansion
- Mobile app or web dashboard — Slack is the review interface

## Context

**Origin:** Lauren requested this as a parallel workstream alongside the GBTS enterprise sprint. Not urgent but "soon I need to be able to confidently say we have an answer here." Paul is building this as a goodwill investment in the product.

**Downstream consumer:** The IcebreakerAI pipeline. Tool entries produced by Watchman become inputs to the 6-stage prompt generation system. The schema must be compatible with IcebreakerAI's tool registry format.

**Prior brainstorm (ChatGPT session):** Extensive thinking on signal tiers, source registry schema, scoring rubric (taxonomy fit, novel capability, adoption/traction, credibility, enterprise readiness, integration leverage, cost/benefit). Methodology is simple — the hard part is source design. Start with 15-20 high-confidence sources, expand after scoring and dedupe are proven.

**Relationship to IcebreakerAI:** Loosely coupled feeder. Proposes candidates only — does not write directly to production tool records. Ingestion uses the same pipeline already trusted. Decision on whether this lives inside the icebreaker repo or standalone is deferred.

**Key insight from brainstorm:** Breadth beats depth later. Depth beats breadth now. Start structured, high-confidence, expandable. Signal fatigue kills systems like this.

## Constraints

- **Language**: Python 3.11+ (consistent with IcebreakerAI stack)
- **Deployment**: Local cron on Paul's machine or AWS instance initially
- **Review interface**: Slack bot (@slack/bolt or Python slack_sdk)
- **Schema compatibility**: Output must match IcebreakerAI tool registry schema
- **Cost**: Minimal LLM usage — scoring can use Haiku for cheap classification
- **Timeline**: Background workstream, not blocking enterprise sprint

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Standalone repo, not IcebreakerAI module | Keep sprint work clean, decide integration later | -- Pending |
| Slack bot for review UI | Lauren already lives in Slack, lowest friction | -- Pending |
| Surface cards first, enrich on approval | Avoid wasting LLM tokens on signals that get rejected | -- Pending |
| Two-step schema generation (draft + approval) | Quality control before anything enters production pipeline | -- Pending |
| Configurable per-source scan frequency | Different sources update at different cadences | -- Pending |
| 15-20 starter sources across 3 tiers | Enough coverage without drowning in noise | -- Pending |
| Cron-based, not real-time | Simplicity, no infrastructure overhead for background workstream | -- Pending |

---
*Last updated: 2026-02-24 after initialization*
