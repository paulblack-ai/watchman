# Quick Task 1: Switch to OpenRouter

**Completed:** 2026-02-25
**Commit:** 76f9351

## Changes

| File | Change |
|------|--------|
| `src/watchman/llm_client.py` | New shared client factory — reads `OPENROUTER_API_KEY`, sets `base_url` to OpenRouter |
| `src/watchman/scoring/scorer.py` | Uses `get_client()`, model ID `anthropic/claude-haiku-4-5-20251001` |
| `src/watchman/enrichment/extractor.py` | Uses `get_client()`, model ID `anthropic/claude-sonnet-4-20250514` |
| `.env.example` | Added `OPENROUTER_API_KEY` |
| `tests/test_scoring.py` | Mock targets updated to `get_client`, model assertion updated |
| `tests/test_enrichment.py` | Mock target updated to `get_client` |

## Verification

- 23/23 tests pass (15 scoring + 8 enrichment)
- No direct `anthropic.Anthropic()` calls remain in src/
