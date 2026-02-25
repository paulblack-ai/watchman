---
phase: 07-audit-gap-closure-runtime-fixes
status: passed
verified_at: 2026-02-25
verifier: orchestrator
---

# Phase 7: Audit Gap Closure -- Runtime Fixes -- Verification

## Phase Goal
Fix critical runtime bugs found by v1.0 milestone audit -- collector registration, datetime awareness, and Gate 2 timestamp logic.

## Must-Have Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | get_collector() resolves registered collectors at runtime (COLLECTOR_REGISTRY has 3 entries) | PASS | `from watchman.collectors import COLLECTOR_REGISTRY` returns {'api', 'rss', 'scrape'} |
| 2 | RawItem().fetched_at and SignalCard().created_at produce timezone-aware UTC datetimes | PASS | Both `.tzinfo is not None` confirmed |
| 3 | set_gate2_state('pending', ...) does NOT set gate2_reviewed_at | PASS | test_gate2_pending_does_not_set_reviewed_at passes |
| 4 | set_gate2_state('gate2_approved', ...) DOES set gate2_reviewed_at | PASS | test_gate2_approve_updates_state passes |
| 5 | All 79+ existing tests still pass after fixes | PASS | 86 passed (79 original + 7 new), 0 failures |

## Must-Have Artifacts

| # | Path | Contains | Status |
|---|------|----------|--------|
| 1 | src/watchman/scheduler/jobs.py | `from watchman.collectors import get_collector` | PASS |
| 2 | src/watchman/models/raw_item.py | `datetime.now(timezone.utc)` | PASS |
| 3 | src/watchman/models/signal_card.py | `datetime.now(timezone.utc)` | PASS |
| 4 | src/watchman/storage/repositories.py | `if state == "pending"` | PASS |
| 5 | tests/test_collector_registry.py | 6 tests, 67 lines | PASS |

## Key Links

| # | From | To | Pattern | Status |
|---|------|----|---------|--------|
| 1 | jobs.py | collectors/__init__.py | `from watchman\.collectors import get_collector` | PASS |
| 2 | raw_item.py | datetime.now(timezone.utc) | `default_factory=lambda: datetime\.now\(timezone\.utc\)` | PASS |
| 3 | repositories.py | gate2_reviewed_at SQL | `if state == .pending.` | PASS |

## Requirements Traceability

| Req ID | Description | Status |
|--------|-------------|--------|
| COLL-01 | Collector registry populated at runtime | PASS |
| COLL-02 | RSS collector resolves via get_collector | PASS |
| COLL-03 | API collector resolves via get_collector | PASS |
| COLL-04 | Scrape collector resolves via get_collector | PASS |

## Test Results

```
86 passed, 0 failures, 3 warnings
```

## Score: 5/5 must-haves verified

All success criteria met. Phase 7 verification PASSED.
