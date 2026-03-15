---
phase: quick-10
plan: "01"
subsystem: notion-integration
tags: [notion, review-surface, delivery, polling, slack-migration]
dependency_graph:
  requires:
    - src/watchman/models/signal_card.py
    - src/watchman/storage/database.py
    - src/watchman/storage/repositories.py
    - src/watchman/enrichment/pipeline.py
    - src/watchman/scheduler/jobs.py
  provides:
    - Notion API client wrapper
    - Notion database row delivery for scored signal cards
    - Notion status change polling (syncs back to SQLite)
    - Scheduler jobs for Notion delivery and polling
    - Updated main.py entry point with Notion-first review surface
  affects:
    - src/watchman/enrichment/pipeline.py (Gate 2 delivery now Notion-first)
    - src/watchman/main.py (Slack demoted to legacy mode)
tech_stack:
  added:
    - notion-client>=2.0 (official Notion Python SDK)
  patterns:
    - Notion database as review surface with status properties
    - 45-second polling loop to sync Notion status changes to SQLite
    - Graceful fallback: Notion primary, Slack legacy when NOTION_TOKEN absent
key_files:
  created:
    - src/watchman/notion/__init__.py
    - src/watchman/notion/client.py
    - src/watchman/notion/delivery.py
    - src/watchman/notion/poller.py
    - src/watchman/notion/setup.py
  modified:
    - src/watchman/models/signal_card.py (notion_page_id field)
    - src/watchman/storage/database.py (migrate_notion function)
    - src/watchman/storage/repositories.py (3 new CardRepository methods)
    - src/watchman/enrichment/pipeline.py (Notion Gate 2 delivery)
    - src/watchman/scheduler/jobs.py (Notion delivery + poll jobs)
    - src/watchman/main.py (Notion-first wiring)
    - pyproject.toml (notion-client dependency)
decisions:
  - "Notion is primary review surface; Slack kept as legacy fallback (not removed)"
  - "Rate limiting via time.sleep(0.35) between Notion API calls (under 3 req/sec)"
  - "Polling every 45 seconds catches status changes within one minute"
  - "notion_page_id stored in SQLite to enable efficient page updates"
  - "Schema validation at startup warns about missing Notion DB properties without blocking"
  - "Gate 2 delivery: update existing Notion page if notion_page_id exists, create new page as edge case"
metrics:
  duration: "~25 min"
  completed_date: "2026-03-14"
  tasks_completed: 3
  files_changed: 11
---

# Quick Task 10: Watchman Notion Migration (Replace Slack) Summary

**One-liner:** Notion database integration replacing Slack as the review surface, with property-mapped card delivery, 45-second status polling, and Slack demoted to legacy fallback.

## What Was Built

Complete replacement of Slack as the signal review surface with Notion interactive database cards. Signal cards now appear as Notion database rows with all properties (Title, Source, Tier, Score, Review Status, Gate 2, etc.) and rich page body content (summary, rubric breakdown). A polling loop syncs Notion status changes (Approved/Rejected/Snoozed for Gate 1; Approved/Rejected for Gate 2) back to SQLite and triggers downstream workflows.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Notion client, setup, model field, DB migration | 4fa5d18 | notion/client.py, notion/setup.py, signal_card.py, database.py, repositories.py, pyproject.toml |
| 2 | Create Notion delivery, poller, update enrichment + scheduler | 5d8e9c3 | notion/delivery.py, notion/poller.py, pipeline.py, jobs.py |
| 3 | Wire Notion into main.py | cfd5a30 | main.py |

## Architecture

```
Watchman startup
  ├─ NOTION_TOKEN + NOTION_DATABASE_ID set?
  │   YES → validate_database_schema() → log warnings for missing props
  │         schedule_notion_delivery_job() at 9 AM
  │         schedule_notion_poll_job() every 45s
  │   NO  → fall back to Slack (legacy mode) or warn "No review surface"
  │
Daily delivery (9 AM)
  └─ deliver_daily_review_notion()
       → find_top_scored_today(limit=cap)
       → for each card: create_page(properties, body_children)
       → save_notion_page_id() to SQLite

Polling (every 45s)
  └─ poll_notion_status()
       → query Notion where Review Status != "To Review" OR Gate 2 != "Not Started"
       → for each changed card:
           Review Approved → set_review_state("approved") + enrich_approved_card()
           Review Rejected → set_review_state("rejected")
           Review Snoozed  → snooze_card(30d) + update Notion Snooze Until date
           Gate 2 Approved → set_gate2_state("gate2_approved") + write_tool_entry()
           Gate 2 Rejected → set_gate2_state("gate2_rejected")

Enrichment completion
  └─ enrich_approved_card()
       → if NOTION_TOKEN: deliver_gate2_to_notion()
              → update existing page (Enrichment=complete, Gate 2=To Review)
              → append enrichment blocks (description, capabilities, pricing, API surface, hooks)
         else: async_deliver_gate2_card() [Slack, legacy]
```

## Notion Property Mapping

| SQLite Column | Notion Property | Notion Type |
|---------------|-----------------|-------------|
| title | Title | title |
| source_name | Source | select |
| tier | Tier | select (1/2/3) |
| relevance_score | Score | number |
| top_dimension | Top Dimension | select |
| review_state | Review Status | status |
| date | Published | date |
| url | URL | url |
| enrichment_state | Enrichment | select |
| gate2_state | Gate 2 | status |
| snooze_until | Snooze Until | date |
| enrichment_attempt_count | Attempts | number |
| (new) notion_page_id | — stored in SQLite only — | TEXT |

## Deviations from Plan

None — plan executed exactly as written.

## How to Use

1. Create a Notion database with all required properties (run `print_setup_instructions()` for full guide)
2. Share the database with your Notion integration
3. Set environment variables:
   ```
   NOTION_TOKEN=secret_...
   NOTION_DATABASE_ID=<32-char-hex-database-id>
   ```
4. Run `python -m watchman.main` — startup logs will show:
   - "Notion database schema validated" (or warnings about missing properties)
   - "Review surface: Notion"
   - Scheduled jobs include "deliver-daily-review-notion" and "poll-notion-status"
5. Signal cards appear in Notion at 9 AM daily; change Review Status to approve/reject/snooze

## Self-Check: PASSED

All created files verified:
- FOUND: src/watchman/notion/client.py
- FOUND: src/watchman/notion/delivery.py
- FOUND: src/watchman/notion/poller.py
- FOUND: src/watchman/notion/setup.py

All commits verified:
- FOUND: 4fa5d18 (Task 1)
- FOUND: 5d8e9c3 (Task 2)
- FOUND: cfd5a30 (Task 3)
