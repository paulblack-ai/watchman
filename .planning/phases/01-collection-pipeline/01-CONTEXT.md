# Phase 1: Collection Pipeline - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the complete signal ingestion path: source registry (YAML config), scheduled collectors (RSS/API/scrape), signal normalization into structured cards, deduplication (URL hash + content fingerprint), per-source health monitoring, SQLite database as integration bus, and IcebreakerAI schema encoded as Pydantic models. This phase ends with deduplicated signal cards in the database — scoring, Slack delivery, and enrichment are later phases.

</domain>

<decisions>
## Implementation Decisions

### Source Registry Design
- Single `sources.yaml` file with tier as a field per source (not split by tier)
- Scan frequency expressed as human-readable intervals: `4h`, `12h`, `24h` (not cron expressions)
- Each source has an `enabled: true/false` toggle for pausing without deleting
- Claude curates the 15-20 starter sources based on tier definitions (Tier 1: structured/official AI releases, Tier 2: launch platforms, Tier 3: SaaS changelogs)

### Signal Card Shape
- Normalized card fields: title, source name, date, URL, tier, raw summary/description from feed, collector type (rss/api/scrape)
- Raw feed items kept in a separate `raw_items` table after normalization — useful for debugging, re-processing, auditing
- Missing publish dates fall back to fetch timestamp (when Watchman collected the item)
- Collector type tracked on each card for debugging collector-specific issues

### Deduplication Strategy
- Two-layer dedup: URL exact hash match + content fingerprint (normalized title similarity >85%) within 7-day window
- Conservative matching to minimize false positives — better to let some dupes through than merge distinct signals
- Duplicate handling: first card is canonical; later duplicates linked but not surfaced
- Duplicate count ("seen across N sources") visible on canonical card when it reaches Slack — cross-source credibility signal for Lauren

### Health Alerting Behavior
- Health alerts sent as DM to Paul (not Lauren's review channel — keeps her queue clean)
- Alert threshold: 2 consecutive zero-yield runs per source
- Alert cadence: alert once on first detection, then roll failures into a daily digest (avoids alert fatigue)
- Alerts include suggested action based on source type (RSS: "check if URL changed", API: "check if key expired", scrape: "check if page selector broke")

### Claude's Discretion
- Exact YAML schema field names and structure
- SQLite table schema design
- Collector abstract class hierarchy
- Normalization algorithm details
- Exact duplicate fingerprint implementation (hashing approach)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The research summary recommends feedparser for RSS, httpx for HTTP, trafilatura for scraping, and APScheduler 3.x (not 4.x) for scheduling.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-collection-pipeline*
*Context gathered: 2026-02-24*
