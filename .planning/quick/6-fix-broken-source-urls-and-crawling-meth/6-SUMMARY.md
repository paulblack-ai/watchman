---
phase: quick-6
plan: 1
subsystem: collection
tags: [jina, r.jina.ai, markdown, rss, scrape, sources]

requires:
  - phase: 01-collection-pipeline
    provides: "BaseCollector, register_collector, RawItem, SourceConfig"
provides:
  - "JinaCollector for sites that block direct scrapers"
  - "Fixed URLs for all 8 broken sources"
  - "Updated source type mapping (rss/scrape to jina where needed)"
affects: [collection-pipeline, normalizer]

tech-stack:
  added: [r.jina.ai]
  patterns: [jina-markdown-collector, heading-based-changelog-parsing, link-based-blog-parsing]

key-files:
  created:
    - src/watchman/collectors/jina.py
  modified:
    - src/watchman/config/sources.yaml
    - src/watchman/models/raw_item.py
    - src/watchman/models/source.py
    - src/watchman/collectors/__init__.py

key-decisions:
  - "Anthropic and Meta AI have no public RSS feeds; switched to Jina scraping"
  - "VentureBeat main /feed/ times out; using /category/ai/feed/ instead"
  - "Jina collector parses changelog headings and blog listing links, falls back to single item"

requirements-completed: [FIX-URLS, FIX-SCRAPE, JINA-MARKDOWN]

duration: 9min
completed: 2026-02-28
---

# Quick Task 6: Fix Broken Source URLs and Crawling Methods Summary

**JinaCollector using r.jina.ai for 7 sources that block scrapers or lack RSS, plus VentureBeat RSS URL fix -- all 8 broken sources now returning items**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-28T17:30:31Z
- **Completed:** 2026-02-28T17:39:09Z
- **Tasks:** 3 (2 auto + 1 checkpoint auto-approved)
- **Files modified:** 5

## Accomplishments
- Created JinaCollector that fetches markdown via r.jina.ai and parses changelog headings or blog listing links
- Fixed all 8 broken sources: Anthropic Blog, Meta AI Blog, Product Hunt AI, GitHub Trending, BetaList, VentureBeat AI, Linear Changelog, Stripe Changelog
- Verified all sources return items both locally and on EC2 (54.234.12.180)
- No regression on 9 previously-working sources

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Jina markdown collector and fix source URLs** - `6263c6c` (feat)
2. **Task 2: Test each source and fix issues iteratively** - `f1d240a` (fix)
3. **Task 3: Verify all sources collect successfully** - auto-approved checkpoint

## Files Created/Modified
- `src/watchman/collectors/jina.py` - New Jina markdown collector using r.jina.ai
- `src/watchman/config/sources.yaml` - Updated URLs and types for 8 broken sources
- `src/watchman/models/raw_item.py` - Added "jina" to collector_type Literal
- `src/watchman/models/source.py` - Added "jina" to SourceConfig type Literal
- `src/watchman/collectors/__init__.py` - Registered jina collector import

## Test Results

| Source | Items | Status |
|--------|-------|--------|
| Anthropic Blog | 12 | OK (jina /research) |
| Meta AI Blog | 51 | OK (jina /blog/) |
| Product Hunt AI | 1 | OK (jina, single-item fallback) |
| GitHub Trending | 1 | OK (jina, single-item fallback) |
| BetaList | 20 | OK (jina, link-based parsing) |
| VentureBeat AI | 7 | OK (RSS /category/ai/feed/) |
| Linear Changelog | 86 | OK (jina, heading-based parsing) |
| Stripe Changelog | 18 | OK (jina, heading-based parsing) |

## Decisions Made
- Anthropic has no public RSS feed (all paths return 404); switched to Jina scraping of /research page
- Meta AI has no public RSS feed (all paths return 404); switched to Jina scraping of /blog/ page
- VentureBeat main /feed/ URL times out; /category/ai/feed/ works and returns AI-specific entries
- Product Hunt and GitHub Trending return single items (fallback mode) since their page structures don't match heading/link patterns well -- acceptable as they still capture content

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Anthropic and Meta AI RSS feeds don't exist**
- **Found during:** Task 2 (Testing)
- **Issue:** Plan suggested trying alternate RSS URLs first, but Anthropic (feed.xml, rss.xml, blog/feed, news/rss) and Meta AI (blog/rss/, blog/feed/, about.fb.com) all return 404
- **Fix:** Switched both to type: jina pointing at their blog/research listing pages
- **Files modified:** src/watchman/config/sources.yaml
- **Committed in:** f1d240a

**2. [Rule 1 - Bug] VentureBeat main feed URL times out**
- **Found during:** Task 2 (Testing)
- **Issue:** Plan suggested /feed/ (main feed), but it times out. The original /category/ai/feed/ URL actually works
- **Fix:** Restored /category/ai/feed/ URL
- **Files modified:** src/watchman/config/sources.yaml
- **Committed in:** f1d240a

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs in planned URLs)
**Impact on plan:** Both fixes necessary -- planned URLs simply didn't work. No scope creep.

## Issues Encountered
- Google AI Blog RSS returns 0 items -- pre-existing issue, not caused by this task (out of scope)

## User Setup Required
None - no external service configuration required.

## Next Steps
- Consider improving Product Hunt and GitHub Trending Jina parsing to extract more granular items
- Google AI Blog RSS may need investigation separately

---
*Quick Task: 6-fix-broken-source-urls-and-crawling-meth*
*Completed: 2026-02-28*
