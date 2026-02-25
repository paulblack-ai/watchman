---
phase: 01-collection-pipeline
plan: 02
subsystem: collectors, scheduler
tags: [feedparser, httpx, trafilatura, apscheduler, factory-pattern]

requires:
  - phase: 01-collection-pipeline/01
    provides: Pydantic models, source registry, SQLite database, repositories
provides:
  - RSS/Atom feed collector
  - HTTP/API collector with HN Algolia support
  - Web scrape collector using trafilatura
  - APScheduler automation with per-source intervals
  - Main entry point
affects: [01-03]

tech-stack:
  added: []
  patterns: [factory-pattern, abc-collectors, async-collection]

key-files:
  created:
    - src/watchman/collectors/base.py
    - src/watchman/collectors/rss.py
    - src/watchman/collectors/api.py
    - src/watchman/collectors/scrape.py
    - src/watchman/scheduler/jobs.py
    - src/watchman/main.py
  modified: []

key-decisions:
  - "Used factory pattern with decorator registration for collector dispatch"
  - "Fetch HTML with httpx then pass to trafilatura (avoid built-in fetcher hangs)"
  - "Sync wrapper with asyncio.run() for APScheduler thread pool compatibility"

patterns-established:
  - "Collector factory: register_collector decorator + get_collector factory"
  - "Async collectors with sync scheduler wrapper"
  - "httpx AsyncClient with 30s timeout and follow_redirects"

requirements-completed: [COLL-01, COLL-02, COLL-03, COLL-04, INFRA-03]

duration: 6min
completed: 2026-02-24
---

# Phase 1 Plan 02: Collectors and Scheduler Summary

**RSS/API/scrape collectors with factory pattern, APScheduler automation for 17 sources at per-source intervals**

## Performance

- **Duration:** 6 min
- **Tasks:** 2
- **Files created:** 8

## Accomplishments
- Three collector types: RSS (feedparser), API (httpx + JSON), Scrape (trafilatura)
- Factory pattern with decorator registration for zero-code source addition
- APScheduler creates interval jobs per enabled source
- Main entry point wires config, DB, and scheduler

## Task Commits

1. **Task 1: Collectors** - `8c12556` (feat)
2. **Task 2: Scheduler and main** - (same commit, combined)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added collector imports to __init__.py**
- **Found during:** Task 1 verification
- **Issue:** Collector decorators don't fire without importing the modules
- **Fix:** Added explicit imports in collectors/__init__.py
- **Verification:** All 3 types in COLLECTOR_REGISTRY

---

**Total deviations:** 1 auto-fixed (1 blocking)

## Issues Encountered
None.

## Next Phase Readiness
- All collectors ready to fetch from 17 sources
- Scheduler automates collection at configured intervals
- Raw items flow to database for Plan 03 processing

---
*Phase: 01-collection-pipeline*
*Completed: 2026-02-24*
