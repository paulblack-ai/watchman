---
phase: quick-11
plan: "01"
subsystem: notion-poller
tags: [bugfix, notion, select-property, poller, tests]
dependency_graph:
  requires: [quick-10]
  provides: [working-notion-poller-select-reads]
  affects: [src/watchman/notion/poller.py, src/watchman/notion/delivery.py, src/watchman/notion/setup.py]
tech_stack:
  patterns: [select-property-fallback, unittest-mock-patch]
key_files:
  modified:
    - src/watchman/notion/poller.py
    - src/watchman/notion/delivery.py
    - src/watchman/notion/setup.py
  created:
    - tests/test_notion_poller.py
decisions:
  - "_extract_status_name reads select first then falls back to status for resilience against future Notion property type changes"
  - "_build_review_status_property removed entirely since Review Status and Gate 2 are select types"
metrics:
  duration: ~10 min
  completed: "2026-03-15T02:59:57Z"
  tasks_completed: 2
  files_modified: 3
  files_created: 1
---

# Quick Task 11: Fix Notion Poller for Select Properties — Summary

**One-liner:** Fixed Notion poller to read API-created select properties for Review Status and Gate 2 instead of status type, with select query filter syntax and 8 unit tests.

## What Was Done

Notion properties created via API (Review Status, Gate 2) are `select` type, not `status` type as the UI suggests. The poller was reading `prop.get("status")` returning None, and the query filter used `"status": {"does_not_equal": ...}` which is invalid for select properties.

### Changes Made

**`src/watchman/notion/poller.py`**
- `_extract_status_name()`: changed from `prop.get("status")` to `prop.get("select") or prop.get("status")` (select first, status fallback for resilience)
- `poll_notion_status()`: both query filter conditions changed from `"status": {"does_not_equal": ...}` to `"select": {"does_not_equal": ...}`

**`src/watchman/notion/delivery.py`**
- `_build_card_properties()`: Review Status and Gate 2 now use `_build_select_property` instead of `_build_review_status_property`
- `deliver_gate2_to_notion()`: Gate 2 "To Review" updates use `_build_select_property`
- Removed `_build_review_status_property` function entirely (no longer referenced)

**`src/watchman/notion/setup.py`**
- `REQUIRED_PROPERTIES`: Review Status and Gate 2 changed from `"status"` to `"select"`
- `print_setup_instructions()`: table updated to show `Select` type for both properties

**`tests/test_notion_poller.py`** (new file)
- 5 unit tests for `_extract_status_name`: select extraction, status fallback, missing property, no value, select-over-status precedence
- 3 integration tests for `poll_notion_status`: query filter uses select syntax, Approved triggers enrichment, Snoozed triggers 30-day snooze

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix poller property reading and query filter | 71158bf | poller.py, delivery.py, setup.py |
| 2 | Add unit tests for poller select property handling | 2feb012 | tests/test_notion_poller.py |

## Verification Results

All 8 new tests pass:
```
tests/test_notion_poller.py::test_extract_status_name_from_select_property PASSED
tests/test_notion_poller.py::test_extract_status_name_from_status_property_fallback PASSED
tests/test_notion_poller.py::test_extract_status_name_returns_none_when_property_missing PASSED
tests/test_notion_poller.py::test_extract_status_name_returns_none_when_no_select_or_status_value PASSED
tests/test_notion_poller.py::test_extract_status_name_prefers_select_over_status PASSED
tests/test_notion_poller.py::test_poll_notion_status_query_uses_select_filter PASSED
tests/test_notion_poller.py::test_poll_notion_status_approved_triggers_enrichment PASSED
tests/test_notion_poller.py::test_poll_notion_status_snoozed_triggers_snooze PASSED
```

All existing tests unaffected (88 pass, 1 pre-existing failure in test_collector_registry unrelated to this work).

## Deviations from Plan

### Auto-fixed Issues

**[Rule 3 - Blocking] Rebuilt broken venv with correct Python interpreter path**
- Found during: Task 2 (test execution)
- Issue: `.venv/bin/python3.13` pointed to `/Users/salfaqih/...` (different username), making `pytest` and `py.test` fail with "bad interpreter"
- Fix: Ran `/usr/local/bin/python3.13 -m venv --clear .venv && pip install -e ".[dev]"` to rebuild with correct local interpreter
- This was a known issue (noted in project memory as "Venv rebuild needed")

## Self-Check: PASSED

- src/watchman/notion/poller.py: FOUND
- src/watchman/notion/delivery.py: FOUND
- src/watchman/notion/setup.py: FOUND
- tests/test_notion_poller.py: FOUND
- Commit 71158bf: FOUND
- Commit 2feb012: FOUND
