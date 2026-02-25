# Phase 3: Enrichment Pipeline - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

When Lauren approves a signal in Gate 1, the system automatically enriches it with capabilities, pricing, API surface, and integration hooks using an LLM, then validates the result against the IcebreakerAI tool registry Pydantic schema. This phase covers enrichment triggering, LLM extraction, and schema validation. It does not cover Gate 2 review or output file writing (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### LLM extraction source
- Primary source: scrape the tool's webpage (URL from signal card) and feed page content to the LLM
- Fallback: if the page is inaccessible (403, paywall, JS-heavy SPA), fall back to signal card data (title, summary, URL) for best-effort enrichment
- Do NOT pass scoring breakdown to the LLM -- enrichment extracts facts from content independently, without scoring bias

### LLM model choice
- Use Claude Sonnet for enrichment extraction (higher reasoning capability for nuanced content like inferring pricing tiers from vague marketing copy)
- This is a step up from Haiku used in scoring, justified by the more complex extraction task

### Claude's Discretion
- Enrichment field depth (how detailed capabilities, pricing, API surface fields should be)
- Validation failure handling (what happens when LLM output doesn't match the Pydantic schema)
- Pipeline timing (immediate vs batched enrichment after approval)
- Notification behavior (whether to notify Lauren when enrichment completes or silently queue for Gate 2)
- Prompt engineering approach for structured extraction
- Web scraping strategy (library choice, timeout handling, content extraction method)

</decisions>

<specifics>
## Specific Ideas

- The existing `IcebreakerToolEntry` Pydantic model in `src/watchman/models/icebreaker.py` defines the target schema (name, description, capabilities, pricing, api_surface, integration_hooks, source_url, discovered_at)
- Scoring already uses Claude Haiku successfully via the existing `src/watchman/scoring/` module -- enrichment can follow a similar pattern but with Sonnet

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 03-enrichment-pipeline*
*Context gathered: 2026-02-24*
