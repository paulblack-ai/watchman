---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/llm_client.py
  - src/watchman/scoring/scorer.py
  - src/watchman/enrichment/extractor.py
  - .env.example
  - tests/test_scoring.py
  - tests/test_enrichment.py
autonomous: true
requirements: [OPENROUTER-SWITCH]

must_haves:
  truths:
    - "All LLM calls route through OpenRouter instead of direct Anthropic API"
    - "Scorer and extractor use OpenRouter model IDs"
    - "A single shared client factory configures base_url and API key"
    - "All existing tests pass with updated mock targets"
  artifacts:
    - path: "src/watchman/llm_client.py"
      provides: "Shared Anthropic client factory pointing at OpenRouter"
      exports: ["get_client"]
    - path: "src/watchman/scoring/scorer.py"
      provides: "Scorer using shared client with OpenRouter model ID"
      contains: "anthropic/claude-haiku-4-5-20251001"
    - path: "src/watchman/enrichment/extractor.py"
      provides: "Extractor using shared client with OpenRouter model ID"
      contains: "anthropic/claude-sonnet-4-20250514"
  key_links:
    - from: "src/watchman/scoring/scorer.py"
      to: "src/watchman/llm_client.py"
      via: "import get_client"
      pattern: "from watchman\\.llm_client import get_client"
    - from: "src/watchman/enrichment/extractor.py"
      to: "src/watchman/llm_client.py"
      via: "import get_client"
      pattern: "from watchman\\.llm_client import get_client"
---

<objective>
Switch all LLM calls from direct Anthropic API to OpenRouter by creating a shared client factory and updating the two call sites.

Purpose: Use OpenRouter as the LLM gateway for cost tracking, model flexibility, and unified billing across providers.
Output: All Claude API calls route through OpenRouter; existing tests pass.
</objective>

<execution_context>
@/Users/salfaqih/.claude/get-shit-done/workflows/execute-plan.md
@/Users/salfaqih/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/watchman/scoring/scorer.py
@src/watchman/enrichment/extractor.py
@tests/test_scoring.py
@tests/test_enrichment.py
@.env.example
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create shared OpenRouter client factory</name>
  <files>src/watchman/llm_client.py, .env.example</files>
  <action>
Create `src/watchman/llm_client.py` with a `get_client()` function that returns an `anthropic.Anthropic` instance configured for OpenRouter:

```python
import anthropic
import os

def get_client() -> anthropic.Anthropic:
    """Create an Anthropic client configured to use OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")
    return anthropic.Anthropic(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
```

Update `.env.example` to add `OPENROUTER_API_KEY=sk-or-your-openrouter-key` and remove any `ANTHROPIC_API_KEY` reference if present (there is none currently, so just add the new var).
  </action>
  <verify>
    <automated>python -c "from watchman.llm_client import get_client; print('import ok')"</automated>
  </verify>
  <done>llm_client.py exists, exports get_client, reads OPENROUTER_API_KEY, sets base_url to OpenRouter. .env.example includes OPENROUTER_API_KEY.</done>
</task>

<task type="auto">
  <name>Task 2: Update scorer.py and extractor.py to use shared client and OpenRouter model IDs</name>
  <files>src/watchman/scoring/scorer.py, src/watchman/enrichment/extractor.py</files>
  <action>
In `scorer.py`:
- Replace `import anthropic` at module level with `from watchman.llm_client import get_client` (keep `import anthropic` only if needed for exception types like `anthropic.APIError` in docstrings/type hints -- check usage).
- In `score_card()`, replace `client = anthropic.Anthropic()` with `client = get_client()`.
- Change model string from `"claude-haiku-4-5-20251001"` to `"anthropic/claude-haiku-4-5-20251001"` (OpenRouter model ID format).
- Keep `betas`, `output_config`, `max_tokens` params as-is. OpenRouter passes these through to Anthropic.

In `extractor.py`:
- Same pattern: import `get_client` from `watchman.llm_client`.
- Replace `client = anthropic.Anthropic()` with `client = get_client()`.
- Change model string from `"claude-sonnet-4-20250514"` to `"anthropic/claude-sonnet-4-20250514"`.
- Keep `betas`, `output_config`, `max_tokens` params as-is.

Both files should still `import anthropic` if they reference `anthropic.APIError` in raises docs or type annotations. Check each file -- scorer.py mentions `anthropic.APIError` in its docstring so keep the import.
  </action>
  <verify>
    <automated>python -c "from watchman.scoring.scorer import score_card; from watchman.enrichment.extractor import enrich_card; print('imports ok')"</automated>
  </verify>
  <done>Both files use get_client() instead of anthropic.Anthropic() directly. Model strings use OpenRouter format (anthropic/ prefix).</done>
</task>

<task type="auto">
  <name>Task 3: Update test mocks to target new client factory</name>
  <files>tests/test_scoring.py, tests/test_enrichment.py</files>
  <action>
Tests currently mock `watchman.scoring.scorer.anthropic.Anthropic` and `watchman.enrichment.extractor.anthropic.Anthropic`. Since scorer.py and extractor.py now use `get_client()` from `watchman.llm_client`, update the mock targets:

In `tests/test_scoring.py`:
- Change all `patch("watchman.scoring.scorer.anthropic.Anthropic")` to `patch("watchman.scoring.scorer.get_client")`.
- The mock now returns a mock client directly (not `mock_cls.return_value`). Update: `mock_get_client.return_value = mock_client` where `mock_client.messages.create.return_value = mock_response`.
- Update the model assertion in `test_score_card_uses_correct_model` to check for `"anthropic/claude-haiku-4-5-20251001"` (with prefix).

In `tests/test_enrichment.py`:
- Change `patch("watchman.enrichment.extractor.anthropic.Anthropic")` to `patch("watchman.enrichment.extractor.get_client")`.
- Same pattern: `mock_get_client.return_value = mock_client`.

Ensure all existing test assertions still hold. The mock structure stays the same (mock_client.messages.create.return_value), just the entry point changes from mocking the class constructor to mocking get_client.
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/Projects/watchman && python -m pytest tests/test_scoring.py tests/test_enrichment.py -x -v 2>&1 | tail -30</automated>
  </verify>
  <done>All tests in test_scoring.py and test_enrichment.py pass. Mocks target get_client instead of anthropic.Anthropic. Model ID assertions use OpenRouter format.</done>
</task>

</tasks>

<verification>
Run full test suite to confirm no regressions:
```bash
cd /Users/salfaqih/paul/Projects/watchman && python -m pytest tests/ -x -v
```
Verify no remaining direct `anthropic.Anthropic()` calls in scorer or extractor:
```bash
grep -n "anthropic.Anthropic()" src/watchman/scoring/scorer.py src/watchman/enrichment/extractor.py
```
(Should return no results.)
</verification>

<success_criteria>
- All LLM calls go through OpenRouter (base_url set, OPENROUTER_API_KEY used)
- Model IDs use OpenRouter format (anthropic/ prefix)
- Single shared client factory in llm_client.py
- All existing tests pass with updated mocks
- .env.example documents OPENROUTER_API_KEY
</success_criteria>

<output>
After completion, create `.planning/quick/1-switch-to-openrouter/1-SUMMARY.md`
</output>
