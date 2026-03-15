---
phase: quick-12
plan: 01
subsystem: scoring
tags: [llm, openrouter, gemini, cost-reduction, scoring]
dependency_graph:
  requires: []
  provides: [configurable-scoring-model, json-sanitization]
  affects: [src/watchman/scoring/scorer.py, tests/test_scoring.py]
tech_stack:
  added: []
  patterns: [env-var-driven model selection, JSON sanitization before parse]
key_files:
  created: []
  modified:
    - src/watchman/scoring/scorer.py
    - tests/test_scoring.py
decisions:
  - "google/gemini-2.0-flash-001 chosen as default scoring model (~10x cheaper than Haiku)"
  - "WATCHMAN_SCORING_MODEL env var allows runtime override without code changes"
  - "Haiku retained as documented fallback in comment, not deleted"
  - "JSON sanitization applied unconditionally before json.loads() in score_card()"
metrics:
  duration: ~8 min
  completed: "2026-03-15"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Quick Task 12: Swap Watchman Scoring Model from Haiku to Gemini Flash Summary

## One-liner

Replaced hardcoded `anthropic/claude-haiku-4.5` with `google/gemini-2.0-flash-001` as the scoring model default, with WATCHMAN_SCORING_MODEL env var for runtime override and JSON escape sanitization for Flash quirks.

## What Was Done

### Task 1: Add configurable model and JSON sanitization to scorer (d8abdce)

Updated `src/watchman/scoring/scorer.py`:

- Added `import os` (needed for `os.environ.get`)
- Removed direct `import anthropic` (no longer needed)
- Added `DEFAULT_SCORING_MODEL = "google/gemini-2.0-flash-001"` with Haiku fallback comment
- Added `_get_scoring_model()` reading from `WATCHMAN_SCORING_MODEL` env var
- Added `_sanitize_json_escapes()` fixing Flash-specific `\/` and `\'` escape quirks
- Updated `score_card()` to use `_get_scoring_model()` instead of hardcoded Haiku string
- Applied `_sanitize_json_escapes(text)` before `json.loads(text)` in `score_card()`
- Updated module, function, and docstrings to be LLM-agnostic

### Task 2: Update tests for new model default and add sanitization tests (3fe9c4b)

Updated `tests/test_scoring.py`:

- Extended import to include `_get_scoring_model`, `_sanitize_json_escapes`, `DEFAULT_SCORING_MODEL`
- Renamed `test_score_card_uses_correct_model` to `test_score_card_uses_default_model`
- Updated model assertion from `anthropic/claude-haiku-4.5` to `google/gemini-2.0-flash-001`
- Added 6 new unit tests: default model constant, env var absent/present, sanitize forward slash, sanitize single quote, sanitize clean input
- Added 1 new integration test: env var model override verified via mock call_kwargs

Total: 22 tests, all passing.

## Verification

- `python -m pytest tests/test_scoring.py -x -v` — 22 passed in 0.25s
- `DEFAULT_SCORING_MODEL` prints `google/gemini-2.0-flash-001`
- `grep -c 'haiku' scorer.py` returns 1 (only in fallback comment, not active code)
- `WATCHMAN_SCORING_MODEL` confirmed in env var lookup

## Decisions Made

1. **Gemini 2.0 Flash as default** — Haiku was 77% of API spend; Flash is ~10x cheaper with comparable quality for scoring tasks.
2. **Env var override** — `WATCHMAN_SCORING_MODEL` allows reverting to Haiku at runtime without code changes, making rollback trivial.
3. **Haiku retained as comment** — Not deleted; documented as `WATCHMAN_SCORING_MODEL=anthropic/claude-haiku-4.5` fallback.
4. **Unconditional sanitization** — `_sanitize_json_escapes()` applied before every `json.loads()` call; negligible overhead, prevents silent parse failures on Flash output.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `/Users/paul/paul/Projects/watchman/src/watchman/scoring/scorer.py` — exists, contains `gemini-2.0-flash-001` and `WATCHMAN_SCORING_MODEL`
- `/Users/paul/paul/Projects/watchman/tests/test_scoring.py` — exists, contains `WATCHMAN_SCORING_MODEL` and 22 tests passing
- Commit d8abdce — exists (feat: swap scoring model)
- Commit 3fe9c4b — exists (test: update scoring tests)
