---
phase: 01-collection-pipeline
verified: 2026-02-25T00:00:00Z
status: human_needed
score: 13/14 must-haves verified
human_verification:
  - test: "Run scheduler and verify signals are collected from at least 15 sources"
    expected: "Raw items appear in SQLite database from RSS, API, and scrape collectors across all three tiers"
    why_human: "Requires live network access to external sources and a running APScheduler instance"
  - test: "Verify a source returning zero results for 2+ consecutive runs triggers a Slack health alert"
    expected: "Slack DM sent to Paul with source name and failure count"
    why_human: "Requires live Slack workspace with configured SLACK_BOT_TOKEN and SLACK_PAUL_USER_ID"
---

# Phase 1: Collection Pipeline Verification Report

**Phase Goal:** Signals flow from external sources into normalized, deduplicated cards in the database, with source health monitored
**Verified:** 2026-02-25
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running the scheduler pulls signals from at least 15 configured sources across all three tiers | HUMAN NEEDED | `src/watchman/config/sources.yaml` contains 17 sources: 5 Tier 1, 6 Tier 2, 6 Tier 3. APScheduler jobs registered in `src/watchman/scheduler/jobs.py`. Collectors exist for all three types (rss, api, scrape). Live verification requires network access. |
| 2 | Raw items are written to the SQLite database | VERIFIED | `RSSCollector`, `APICollector`, `ScrapeCollector` all return `list[RawItem]`; `RawItemRepository.insert()` persists to database via `src/watchman/storage/repositories.py` |
| 3 | Raw items are normalized into structured signal cards (title, source, date, summary, URL, tier) | VERIFIED | `src/watchman/processing/normalizer.py:49` `process_unprocessed()` converts raw items to `SignalCard` instances; `SignalCard` model at `src/watchman/models/signal_card.py:10` has fields: title, source_name, date, summary, url, tier |
| 4 | Duplicate signals by URL appear only once | VERIFIED | `src/watchman/processing/deduplicator.py:54` Layer 1: `find_by_url_hash(card.url_hash)` performs exact URL hash match before inserting |
| 5 | Duplicate signals by content fingerprint (title+date) are caught | VERIFIED | `src/watchman/processing/deduplicator.py:63` Layer 2: `title_similarity()` with 85% threshold within 7-day window plus 1-day date proximity check |
| 6 | Deduplication is called during normalization | VERIFIED | `src/watchman/processing/normalizer.py:85` calls `is_duplicate(card, card_repo)` for each card; duplicates are linked via `handle_duplicate()` at line 91 |
| 7 | Source health monitoring tracks consecutive failures | VERIFIED | `src/watchman/health/tracker.py` tracks per-source health; calls `send_health_alert()` when threshold reached |
| 8 | Slack health alert fires on 2+ consecutive zero-result runs | HUMAN NEEDED | `src/watchman/health/alerter.py:18` `send_health_alert()` sends Slack DM; `src/watchman/health/tracker.py:73` triggers alert. Live Slack required for verification. |
| 9 | Sources loaded from YAML with type, URL, tier, and frequency | VERIFIED | `src/watchman/config/sources.yaml` has 17 entries; each with `name`, `type` (rss/api/scrape), `url`, `tier` (1/2/3), `frequency` |
| 10 | Adding a new source requires only a YAML entry | VERIFIED | `src/watchman/models/source.py` defines `Source` model; registry loads from YAML. No code changes needed for new sources. |
| 11 | RSS collector parses feeds and writes raw items | VERIFIED | `src/watchman/collectors/rss.py:18` `RSSCollector` uses feedparser, returns `list[RawItem]` |
| 12 | API collector fetches structured responses | VERIFIED | `src/watchman/collectors/api.py:16` `APICollector` handles HN Algolia and generic JSON formats |
| 13 | Scrape collector extracts content from web pages | VERIFIED | `src/watchman/collectors/scrape.py:17` `ScrapeCollector` uses trafilatura for content extraction |
| 14 | IcebreakerAI tool registry schema encoded as Pydantic models | VERIFIED | `src/watchman/models/icebreaker.py:12` `IcebreakerToolEntry(BaseModel)` with fields: name, description, capabilities, pricing, api_surface, integration_hooks, source_url, discovered_at |

## Must-Have Analysis

| Must-Have | Covered By | Status |
|-----------|-----------|--------|
| 15+ sources across 3 tiers | sources.yaml: 17 sources (5/6/6 per tier) | VERIFIED |
| Normalization to signal cards | normalizer.py process_unprocessed() | VERIFIED |
| URL deduplication | deduplicator.py Layer 1: find_by_url_hash | VERIFIED |
| Content fingerprint dedup | deduplicator.py Layer 2: title similarity | VERIFIED |
| Health alerts on consecutive failures | health/tracker.py + health/alerter.py | HUMAN NEEDED |
| Pydantic schema for IcebreakerAI | models/icebreaker.py IcebreakerToolEntry | VERIFIED |

## Code Quality

- All collectors follow BaseCollector pattern with `async def collect()` interface
- Type annotations on all function signatures
- Proper logging throughout (no print statements)
- Error handling with fallbacks (date parsing, empty feeds)

## Known Issues

- `datetime.utcnow()` deprecation warnings resolved in Phase 6 (replaced with `datetime.now(timezone.utc)`)
- Live Slack integration for health alerts requires environment variables: SLACK_BOT_TOKEN, SLACK_PAUL_USER_ID

---

*Phase: 01-collection-pipeline*
*Verified: 2026-02-25*
