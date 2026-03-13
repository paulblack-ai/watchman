---
phase: quick
plan: 8
subsystem: collection
tags: [sources, rss, jina, venturebeat, figma]
key-files:
  modified:
    - src/watchman/config/sources.yaml
decisions:
  - "VentureBeat: switched from /category/ai/feed/ (stale since Jan 2026, only 7 old entries) to /feed/ (fresh daily content)"
  - "Figma: switched from scrape collector on /whats-new/ (JS-rendered, 1266 chars) to jina collector on /release-notes/ (structured entries with dates)"
metrics:
  duration: ~2 min
  completed: 2026-03-13
---

# Quick Task 8: Fix Broken Watchman Sources (VentureBeat, Figma)

VentureBeat RSS feed URL updated from stale /category/ai/feed/ (last entry Jan 22, 2026) to active /feed/; Figma changelog switched from scrape to Jina on new /release-notes/ URL.

## Problem

Two sources were producing zero usable signals:

1. **VentureBeat AI** (RSS, tier 2): The `/category/ai/feed/` endpoint only returned 7 entries, all from January 2026. Every collection run parsed 7 entries then filtered all 7 as older than 14 days (0 remaining). VentureBeat appears to have restructured their feed paths.

2. **Figma Changelog** (scrape, tier 3): The `/whats-new/` URL redirects (301) to `/release-notes/`, and the page is fully JavaScript-rendered. Trafilatura could only extract ~1266 chars of content, producing a single item that was consistently filtered as old.

## Root Cause

- **VentureBeat**: The category-specific feed path (`/category/ai/feed/`) went stale. The main feed at `/feed/` contains fresh AI content (VentureBeat is now AI-focused).
- **Figma**: The page moved from `/whats-new/` to `/release-notes/` and became a JS-rendered SPA. The scrape collector (trafilatura) cannot extract meaningful content from JS-rendered pages.

## Changes

### sources.yaml

| Source | Before | After |
|--------|--------|-------|
| VentureBeat AI | `rss`, `venturebeat.com/category/ai/feed/` | `rss`, `venturebeat.com/feed/` |
| Figma Changelog | `scrape`, `figma.com/whats-new/` | `jina`, `figma.com/release-notes/` |

## Verification

- **VentureBeat /feed/**: Confirmed 7 fresh articles with today's dates (Mar 13, 2026) via direct curl
- **Figma /release-notes/ via Jina**: Confirmed structured entries with recent dates (Mar 12, 2026) via Jina reader API
- **Service restart**: Watchman restarted cleanly on EC2, both sources registered with correct collector types
- **No other sources affected**: All 25 sources loaded successfully

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Update VentureBeat and Figma source configs | `763a8d7` |

## Deviations from Plan

None -- no formal plan file existed. Task was derived from the directory name and diagnosed from production logs.
