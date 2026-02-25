# Phase 6: Tech Debt and Doc Sync - Research

**Researched:** 2026-02-25
**Status:** Complete

## RESEARCH COMPLETE

## 1. datetime.utcnow() Replacement

### Files requiring changes (source code only):

| File | Line | Current Usage |
|------|------|--------------|
| `src/watchman/collectors/rss.py` | 51 | `now = datetime.utcnow()` |
| `src/watchman/collectors/api.py` | 38 | `now = datetime.utcnow()` |
| `src/watchman/collectors/scrape.py` | 32 | `now = datetime.utcnow()` |
| `src/watchman/processing/deduplicator.py` | 63 | `cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)` |
| `src/watchman/storage/repositories.py` | 370 | `snooze_until = (datetime.utcnow() + timedelta(days=days)).isoformat()` |
| `src/watchman/enrichment/extractor.py` | 118 | `discovered_at=datetime.utcnow(),` |

### Test files requiring changes:

| File | Lines | Current Usage |
|------|-------|--------------|
| `tests/test_enrichment.py` | 203, 235 | `discovered_at=datetime.utcnow(),` |

### Replacement pattern:
- Import: `from datetime import datetime, timezone` (add `timezone` to existing imports)
- Replace: `datetime.utcnow()` -> `datetime.now(timezone.utc)`
- Note: Python 3.12+ deprecates `datetime.utcnow()` with a DeprecationWarning

### Risk: None - both produce the same UTC timestamp, just different awareness levels

## 2. SUMMARY Doc API Key References

### Files referencing ANTHROPIC_API_KEY that need updating:

| File | Content |
|------|---------|
| `.planning/phases/02-scoring-and-slack-review/02-01-SUMMARY.md` | Line 139: references `ANTHROPIC_API_KEY` |
| `.planning/phases/03-enrichment-pipeline/03-01-SUMMARY.md` | Line 98: references `ANTHROPIC_API_KEY` |
| `.planning/phases/03-enrichment-pipeline/03-02-SUMMARY.md` | Line 85: references `ANTHROPIC_API_KEY` |

### Actual state: Code uses `OPENROUTER_API_KEY` via `src/watchman/llm_client.py` (switched in quick task #1)

## 3. REQUIREMENTS.md Checkbox Updates

### Current state (incorrectly unchecked):
- SLCK-01, SLCK-02, SLCK-03, SLCK-04 — implemented in Phase 2, marked Pending
- OUT-01, OUT-02, OUT-03 — implemented in Phase 4, marked as Complete in traceability but unchecked in main list

### Evidence of completion:
- SLCK-01-04: Phase 2 completed with 02-01 and 02-02 plans (Slack review interface fully built)
- OUT-01-03: Phase 4 completed with 04-01 and 04-02 plans (Gate 2 and JSON output)

### Also need to check (from Phase 5):
- PROC-01, PROC-02, PROC-03 — Phase 5 implemented normalizer wiring
- SRC-04 — Phase 5 implemented daily digest with health alerts

## 4. Missing VERIFICATION.md Files

### Existing verification files:
- Phase 2: `02-VERIFICATION.md` (exists)
- Phase 4: `04-VERIFICATION.md` (exists)
- Phase 5: `05-VERIFICATION.md` (exists)

### Missing (required by success criteria):
- Phase 1: No `01-VERIFICATION.md`
- Phase 3: No `03-VERIFICATION.md`

### Format reference: Phase 2 verification uses frontmatter (phase, verified, status, score, human_verification), followed by Goal Achievement with Observable Truths table, Must-Have Analysis, Code Quality, and Known Issues sections.

---

*Phase: 06-tech-debt-and-doc-sync*
*Research completed: 2026-02-25*
