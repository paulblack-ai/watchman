# Phase 7: Audit Gap Closure — Runtime Fixes - Research

**Researched:** 2026-02-25
**Domain:** Python runtime bug fixes — import-time side effects, datetime awareness, SQLite conditional updates
**Confidence:** HIGH

## Summary

Phase 7 closes three runtime bugs identified by the v1.0 milestone audit. The bugs are surgical and well-characterized with exact file/line citations. No new libraries are required. All fixes touch existing production code only; no new modules, no new schemas, no migrations.

The most critical bug (COLL-01 through COLL-04) is a single-line import change in `scheduler/jobs.py`. The current import `from watchman.collectors.base import get_collector` bypasses `watchman/collectors/__init__.py`, which is the only place the three concrete collectors (`rss.py`, `api.py`, `scrape.py`) register themselves via `@register_collector`. At runtime, `COLLECTOR_REGISTRY` is therefore empty and every `collect_source()` call raises `ValueError: No collector registered for type: rss`. Changing the import to `from watchman.collectors import get_collector` causes the `__init__.py` to execute, which imports the concrete collector modules and fires all three `@register_collector` decorators. The registry is then populated and collection works.

The second bug is in two model files: `models/raw_item.py:23` and `models/signal_card.py:29` use `datetime.utcnow` (deprecated, produces timezone-naive datetimes) as `Field(default_factory=...)`. The deduplicator uses `datetime.now(timezone.utc)` (timezone-aware). Comparing naive and aware datetimes raises `TypeError` in Python 3.11+. The fix is `Field(default_factory=lambda: datetime.now(timezone.utc))` in both files — requires adding `timezone` to the `datetime` import.

The third bug is in `storage/repositories.py:454-462`. `set_gate2_state()` always writes `gate2_reviewed_at = datetime('now')` — even when called with `state='pending'` during Gate 2 card delivery. This incorrectly records delivery time as review time. The fix is to conditionally include the `gate2_reviewed_at = datetime('now')` clause only when `state != 'pending'`.

**Primary recommendation:** Apply all three fixes in a single plan wave with targeted test coverage: one new test file for collector registration E2E and one new test for the Gate 2 timestamp conditional; datetime model fix is covered by existing deduplicator tests once datetimes are aware.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COLL-01 | System runs scheduled collectors on per-source cron frequencies using APScheduler | Fix: change import in `jobs.py` so `COLLECTOR_REGISTRY` is populated at runtime; existing `setup_scheduler()` and `collect_source()` logic is correct once registry is populated |
| COLL-02 | RSS collector parses RSS/Atom feeds and writes raw items to the database | Satisfied by existing `rss.py` implementation; unblocked entirely by COLL-01 import fix |
| COLL-03 | HTTP/API collector fetches structured API responses and writes raw items to the database | Satisfied by existing `api.py` implementation; unblocked entirely by COLL-01 import fix |
| COLL-04 | Scrape collector extracts article content from web pages and writes raw items to the database | Satisfied by existing `scrape.py` implementation; unblocked entirely by COLL-01 import fix |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `datetime` + `timezone` | Python 3.11+ built-in | Timezone-aware datetime defaults | PEP 615 added `datetime.UTC`; `timezone.utc` is the standard aware sentinel |
| `aiosqlite` | >=0.20 (already in project) | Async SQLite access for repositories | Already in use across all repository methods |
| `pytest` | >=7.0 (already in project) | Test framework | Project standard — all 79 existing tests use pytest |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `feedparser` | >=6.0 (already in project) | RSS collection | Already used by `RSSCollector` — no change needed |
| `httpx` | >=0.28 (already in project) | HTTP/API collection | Already used by `APICollector` — no change needed |
| `trafilatura` | >=2.0 (already in project) | Scrape collection | Already used by `ScrapeCollector` — no change needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Conditional SQL string in `set_gate2_state` | Separate `set_gate2_pending` function | Single function with conditional is simpler, less API surface, matches existing pattern |
| `datetime.now(UTC)` (Python 3.11+ alias) | `datetime.now(timezone.utc)` | Both work; `timezone.utc` works on Python 3.6+ and matches existing deduplicator usage in this project |

**Installation:** No new packages required. All fixes use existing dependencies.

## Architecture Patterns

### Recommended Project Structure

No structural changes. All changes are in-place edits to existing files:

```
src/watchman/
├── scheduler/jobs.py          # Fix: import line 11
├── models/raw_item.py         # Fix: line 23, fetched_at default_factory
├── models/signal_card.py      # Fix: line 29, created_at default_factory
└── storage/repositories.py    # Fix: lines 454-462, set_gate2_state SQL
tests/
├── test_collectors.py         # New: collector registration E2E test (Wave 0 gap)
└── test_gate2.py              # Extend: add pending-state timestamp test
```

### Pattern 1: Import-Time Side Effects for Registry Population

**What:** Python modules run their top-level code when first imported. The `@register_collector` decorator at module level in `rss.py`, `api.py`, `scrape.py` mutates `COLLECTOR_REGISTRY` as a side effect of import. The `__init__.py` triggers these imports. Importing directly from `base.py` skips this entirely.

**When to use:** Any registry/plugin pattern where concrete implementations must be discovered before use.

**Current broken state:**
```python
# scheduler/jobs.py line 11 — BROKEN
from watchman.collectors.base import get_collector
# Result: COLLECTOR_REGISTRY = {} — registry never populated
```

**Fixed state:**
```python
# scheduler/jobs.py line 11 — CORRECT
from watchman.collectors import get_collector
# Result: __init__.py executes → imports rss, api, scrape → decorators fire
# COLLECTOR_REGISTRY = {'rss': RSSCollector, 'api': APICollector, 'scrape': ScrapeCollector}
```

**Verification:** After fix, `from watchman.collectors import COLLECTOR_REGISTRY; assert len(COLLECTOR_REGISTRY) == 3`

### Pattern 2: Timezone-Aware Datetime Defaults in Pydantic

**What:** Pydantic `Field(default_factory=...)` accepts a zero-argument callable. The factory is called fresh for each model instance — important for mutable defaults.

**Current broken state:**
```python
# models/raw_item.py line 23
from datetime import datetime
fetched_at: datetime = Field(default_factory=datetime.utcnow)
# Produces naive datetime — no timezone info
```

**Fixed state:**
```python
# models/raw_item.py
from datetime import datetime, timezone
fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
# Produces aware datetime — UTC timezone attached
```

**Same fix applies to `models/signal_card.py` line 29 (`created_at` field).**

**Why it matters:** Python 3.12+ raises `DeprecationWarning` for `utcnow()`; comparing naive vs. aware datetimes raises `TypeError`. The deduplicator already uses `datetime.now(timezone.utc)` — fix makes models consistent.

### Pattern 3: Conditional SQL Clause for Timestamp Fields

**What:** Avoid updating a timestamp field when its semantic meaning has not yet occurred (review has not happened when state is pending delivery).

**Current broken state:**
```python
# repositories.py lines 454-462 — sets gate2_reviewed_at even for pending state
await self.db.execute(
    """UPDATE cards
       SET gate2_state = ?,
           gate2_reviewed_at = datetime('now'),
           gate2_slack_ts = COALESCE(?, gate2_slack_ts)
       WHERE id = ?""",
    (state, slack_ts, card_id),
)
```

**Fixed state — Option A (conditional Python, preferred):**
```python
async def set_gate2_state(
    self, card_id: int, state: str, slack_ts: str | None = None
) -> None:
    if state == "pending":
        await self.db.execute(
            """UPDATE cards
               SET gate2_state = ?,
                   gate2_slack_ts = COALESCE(?, gate2_slack_ts)
               WHERE id = ?""",
            (state, slack_ts, card_id),
        )
    else:
        await self.db.execute(
            """UPDATE cards
               SET gate2_state = ?,
                   gate2_reviewed_at = datetime('now'),
                   gate2_slack_ts = COALESCE(?, gate2_slack_ts)
               WHERE id = ?""",
            (state, slack_ts, card_id),
        )
    await self.db.commit()
```

**Fixed state — Option B (single SQL with CASE expression):**
```python
await self.db.execute(
    """UPDATE cards
       SET gate2_state = ?,
           gate2_reviewed_at = CASE WHEN ? != 'pending' THEN datetime('now') ELSE gate2_reviewed_at END,
           gate2_slack_ts = COALESCE(?, gate2_slack_ts)
       WHERE id = ?""",
    (state, state, slack_ts, card_id),
)
```

**Recommendation:** Option A (conditional Python branches) is more readable and easier to test independently. Option B is more concise but the repeated `state` parameter is easy to miscord. Either works correctly.

### Anti-Patterns to Avoid

- **Re-exporting `get_collector` from `base` in `__init__.py` and importing from `base` anyway:** The `__init__.py` already exports `get_collector` via `from watchman.collectors.base import COLLECTOR_REGISTRY, get_collector` — the point is that `__init__.py` must be the import target so its side-effect imports of `rss`, `api`, `scrape` execute.
- **Using `datetime.UTC` instead of `timezone.utc`:** `datetime.UTC` was added in Python 3.11. The project already uses `timezone.utc` in `deduplicator.py` and collectors — use the same for consistency.
- **Writing a migration for the Gate 2 fix:** The bug is in query logic, not schema. No migration needed — `gate2_reviewed_at` column already exists and is nullable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collector plugin discovery | Custom file scanning / importlib | Python `__init__.py` import side effects | Already the architecture; just fix the import site |
| Timezone conversion | Custom UTC offset math | `datetime.now(timezone.utc)` | stdlib, zero-dependency, idiomatic Python 3.x |
| Conditional SQL update | Raw string concatenation | Python if/else branches or SQL `CASE` expression | String concat risks SQL injection; both alternatives are safe |

**Key insight:** All three bugs are one-line fixes rooted in well-understood Python semantics. No library changes, no new abstractions.

## Common Pitfalls

### Pitfall 1: Import Fix Silently Fails in Already-Running Process

**What goes wrong:** If `watchman.collectors.base` was imported before the fix takes effect (e.g., cached `*.pyc` files), the registry could still appear empty in tests.
**Why it happens:** Python module import cache (`sys.modules`) — once a module is imported, subsequent imports return the cached version. The key is that `__init__.py` must be the first importer so side-effect imports execute before any call to `get_collector`.
**How to avoid:** Tests should import from `watchman.collectors` (not `watchman.collectors.base`) and verify `len(COLLECTOR_REGISTRY) == 3` before calling `get_collector`.
**Warning signs:** `ValueError: No collector registered for type: rss` in tests even after fix applied.

### Pitfall 2: Naive Datetime Comparison Failure is Silently Hidden by SQLite

**What goes wrong:** SQLite stores datetimes as strings. `aiosqlite` returns them as strings. `datetime.fromisoformat()` in `_row_to_card()` parses them without timezone info if they were stored without `+00:00`. The Python-level comparison in `deduplicator.py` will raise `TypeError` if one datetime has `tzinfo` and another does not.
**Why it happens:** `datetime.utcnow()` produces `2026-02-25T10:00:00` (no timezone). `datetime.now(timezone.utc)` produces `2026-02-25T10:00:00+00:00`. `fromisoformat` on the first gives naive; on the second gives aware.
**How to avoid:** After the fix, verify that `RawItem().fetched_at.tzinfo is not None` and `SignalCard().created_at.tzinfo is not None`.
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` in deduplicator tests or normalizer job.

### Pitfall 3: Gate 2 Timestamp Fix Breaks Existing Tests

**What goes wrong:** The existing test `test_gate2_approve_updates_state` in `tests/test_gate2.py:168-188` asserts `card.gate2_reviewed_at is not None` after calling `set_gate2_state(card_id, "gate2_approved")`. This test passes both before and after the fix (non-pending state still sets the timestamp). However, there is no test asserting that `set_gate2_state(card_id, "pending")` does NOT set `gate2_reviewed_at`. A new test is needed.
**Why it happens:** The test was written to verify the happy path (approval sets timestamp), not the negative case (delivery does not set timestamp).
**How to avoid:** Add a test: call `set_gate2_state(card_id, "pending")`, then verify `gate2_reviewed_at IS NULL` in the DB.
**Warning signs:** No test catches the regression if the fix is reverted.

### Pitfall 4: Two-Parameter CASE in Option B

**What goes wrong:** Option B SQL passes `state` twice as positional parameters — `(state, state, slack_ts, card_id)`. If the parameter order is wrong, the CASE condition silently evaluates incorrectly.
**Why it happens:** aiosqlite uses `?` positional placeholders; easy to miscord repeated params.
**How to avoid:** Use Option A (Python if/else) — it's explicit and the parameters are not duplicated.

## Code Examples

Verified patterns from official sources:

### Fix 1: Collector Import (jobs.py line 11)

```python
# BEFORE (broken)
from watchman.collectors.base import get_collector

# AFTER (fixed) — one line change, triggers __init__.py side effects
from watchman.collectors import get_collector
```

### Fix 2: Timezone-Aware Datetime Defaults

```python
# BEFORE (broken) — models/raw_item.py line 23
from datetime import datetime
fetched_at: datetime = Field(default_factory=datetime.utcnow)

# AFTER (fixed) — models/raw_item.py line 23
from datetime import datetime, timezone
fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Same fix for models/signal_card.py line 29:
# BEFORE:
from datetime import datetime
created_at: datetime = Field(default_factory=datetime.utcnow)

# AFTER:
from datetime import datetime, timezone
created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Fix 3: Gate 2 Timestamp Conditional (repositories.py)

```python
async def set_gate2_state(
    self, card_id: int, state: str, slack_ts: str | None = None
) -> None:
    """Update the Gate 2 review state of a card.

    Only sets gate2_reviewed_at when state is a terminal review state
    (gate2_approved or gate2_rejected), not when delivering the card
    as pending.
    """
    if state == "pending":
        await self.db.execute(
            """UPDATE cards
               SET gate2_state = ?,
                   gate2_slack_ts = COALESCE(?, gate2_slack_ts)
               WHERE id = ?""",
            (state, slack_ts, card_id),
        )
    else:
        await self.db.execute(
            """UPDATE cards
               SET gate2_state = ?,
                   gate2_reviewed_at = datetime('now'),
                   gate2_slack_ts = COALESCE(?, gate2_slack_ts)
               WHERE id = ?""",
            (state, slack_ts, card_id),
        )
    await self.db.commit()
```

### Verification: Collector Registry Populated

```python
# New test (tests/test_collectors.py)
from watchman.collectors import COLLECTOR_REGISTRY, get_collector

def test_collector_registry_populated():
    """COLLECTOR_REGISTRY must have all three types after import."""
    assert "rss" in COLLECTOR_REGISTRY
    assert "api" in COLLECTOR_REGISTRY
    assert "scrape" in COLLECTOR_REGISTRY
    assert len(COLLECTOR_REGISTRY) == 3
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | Python 3.2 (aware datetimes); `utcnow()` deprecated 3.12 | Naive datetimes cause `TypeError` in aware-unaware comparisons |
| Import from concrete module | Import from package `__init__` | N/A — Python idiom for plugin registration | Registry populated correctly at runtime |

**Deprecated/outdated:**
- `datetime.utcnow()`: Deprecated in Python 3.12. Removed in future. Use `datetime.now(timezone.utc)`. Project already uses the correct form in `deduplicator.py` and all three collectors.

## Open Questions

1. **Should existing test fixtures use timezone-aware datetimes?**
   - What we know: `test_gate2.py` uses `datetime(2026, 2, 24)` (naive) in `sample_entry` and `sample_card` fixtures. After the model fix, `SignalCard.created_at` will be aware but other fields may still be naive.
   - What's unclear: Whether the deduplicator tests will surface mixed-awareness issues in test fixtures, or whether they only compare DB-stored datetimes.
   - Recommendation: Fix model defaults first, run the full test suite, and address any test fixture failures as they surface. The model default fix is the root cause; fixture datetime values only matter if compared against `created_at`/`fetched_at`.

2. **Is there a risk of breaking the currently-passing 79 tests?**
   - What we know: None of the 79 tests explicitly test `COLLECTOR_REGISTRY` state or datetime awareness. The import fix is unlikely to break anything. The datetime fix may cause test failures if any test compares aware vs. naive datetimes in fixtures.
   - What's unclear: Whether `test_gate2.py:test_gate2_approve_updates_state` reads `gate2_reviewed_at` back and compares it to a naive datetime.
   - Recommendation: Run `pytest` after each individual fix to isolate regressions.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (via `.venv`) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/ -q` |
| Full suite command | `.venv/bin/pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COLL-01 | `COLLECTOR_REGISTRY` populated at runtime via `__init__.py` imports | unit | `.venv/bin/pytest tests/test_collectors.py::test_collector_registry_populated -x` | ❌ Wave 0 |
| COLL-01 | `get_collector()` returns correct collector instance for each type | unit | `.venv/bin/pytest tests/test_collectors.py::test_get_collector_rss -x` | ❌ Wave 0 |
| COLL-02 | RSS collector registered and resolvable | unit | `.venv/bin/pytest tests/test_collectors.py::test_registry_has_rss -x` | ❌ Wave 0 |
| COLL-03 | API collector registered and resolvable | unit | `.venv/bin/pytest tests/test_collectors.py::test_registry_has_api -x` | ❌ Wave 0 |
| COLL-04 | Scrape collector registered and resolvable | unit | `.venv/bin/pytest tests/test_collectors.py::test_registry_has_scrape -x` | ❌ Wave 0 |
| COLL-01 | `collect_source()` calls `get_collector()` successfully (no ValueError) | integration | `.venv/bin/pytest tests/test_collectors.py::test_collect_source_resolves_collector -x` | ❌ Wave 0 |
| COLL-01/02 | datetime defaults are timezone-aware in RawItem | unit | `.venv/bin/pytest tests/test_collectors.py::test_raw_item_fetched_at_is_aware -x` | ❌ Wave 0 |
| COLL-01/02 | datetime defaults are timezone-aware in SignalCard | unit | `.venv/bin/pytest tests/test_collectors.py::test_signal_card_created_at_is_aware -x` | ❌ Wave 0 |
| OUT-01/02 | `set_gate2_state('pending')` does NOT set `gate2_reviewed_at` | integration | `.venv/bin/pytest tests/test_gate2.py::test_gate2_pending_does_not_set_reviewed_at -x` | ❌ Wave 0 |
| OUT-01/02 | `set_gate2_state('gate2_approved')` sets `gate2_reviewed_at` | integration | `.venv/bin/pytest tests/test_gate2.py::test_gate2_approve_updates_state -x` | ✅ Exists |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/ -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_collectors.py` — covers COLL-01, COLL-02, COLL-03, COLL-04 registry and E2E resolution
- [ ] `tests/test_gate2.py::test_gate2_pending_does_not_set_reviewed_at` — new test in existing file, covers OUT-01/02 timestamp fix
- [ ] Datetime awareness tests for `RawItem` and `SignalCard` model defaults — can live in `test_collectors.py` or a dedicated `test_models.py`

## Sources

### Primary (HIGH confidence)

- Direct code inspection of `/Users/salfaqih/paul/Projects/watchman/src/watchman/` — audit findings verified by reading exact files
- `/Users/salfaqih/paul/Projects/watchman/.planning/v1.0-MILESTONE-AUDIT.md` — authoritative gap descriptions with file:line citations
- Python stdlib documentation — `datetime.utcnow()` deprecated (verified in Python 3.12 changelog); `timezone.utc` is standard

### Secondary (MEDIUM confidence)

- Existing test suite (79 tests passing) — confirms no regressions from current state; confirms test framework and runner

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all fixes use existing project dependencies, no new libraries
- Architecture: HIGH — exact file:line locations known from audit; Python import mechanics and datetime API are stable, well-documented
- Pitfalls: HIGH — verified against actual code; pitfall 3 (no test for pending state) confirmed by reading `test_gate2.py` test list

**Research date:** 2026-02-25
**Valid until:** 2026-03-27 (stable domain — Python stdlib, no external APIs)
