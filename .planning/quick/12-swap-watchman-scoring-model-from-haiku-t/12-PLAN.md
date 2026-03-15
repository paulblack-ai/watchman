---
phase: quick-12
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/scoring/scorer.py
  - tests/test_scoring.py
autonomous: true
requirements: [QUICK-12]

must_haves:
  truths:
    - "Scoring pipeline uses google/gemini-2.0-flash-001 via OpenRouter by default"
    - "WATCHMAN_SCORING_MODEL env var overrides the default model"
    - "Flash JSON output quirks are sanitized before parsing"
    - "Existing tests pass with updated model assertions"
  artifacts:
    - path: "src/watchman/scoring/scorer.py"
      provides: "Scoring with configurable model, Flash as default, JSON sanitization"
      contains: "gemini-2.0-flash"
    - path: "tests/test_scoring.py"
      provides: "Updated model assertions and JSON sanitization tests"
      contains: "WATCHMAN_SCORING_MODEL"
  key_links:
    - from: "src/watchman/scoring/scorer.py"
      to: "os.environ / WATCHMAN_SCORING_MODEL"
      via: "os.environ.get with default"
      pattern: "os\\.environ\\.get.*WATCHMAN_SCORING_MODEL"
---

<objective>
Swap the Watchman scoring model from Claude Haiku to Gemini 2.0 Flash via OpenRouter, making the model configurable via env var with Flash as default.

Purpose: Haiku was 77% of API spend in icebreaker and was already replaced there. Watchman processes 1,700+ signals and needs the same cost reduction (~10x cheaper).
Output: Updated scorer.py with Flash default, JSON sanitization for Flash quirks, updated tests.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/watchman/scoring/scorer.py
@src/watchman/scoring/models.py
@src/watchman/llm_client.py
@tests/test_scoring.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add configurable model and JSON sanitization to scorer</name>
  <files>src/watchman/scoring/scorer.py</files>
  <action>
Make these changes to `src/watchman/scoring/scorer.py`:

1. **Add `os` import** at the top (already imported via `llm_client` but scorer.py needs it directly):
   ```python
   import os
   ```

2. **Add default model constant and JSON sanitizer** after the `SCORING_CONCURRENCY` constant:
   ```python
   DEFAULT_SCORING_MODEL = "google/gemini-2.0-flash-001"

   def _get_scoring_model() -> str:
       """Return scoring model from WATCHMAN_SCORING_MODEL env var or default."""
       return os.environ.get("WATCHMAN_SCORING_MODEL", DEFAULT_SCORING_MODEL)

   def _sanitize_json_escapes(text: str) -> str:
       """Fix Flash-specific JSON escape quirks before parsing.

       Gemini Flash sometimes produces invalid JSON escape sequences:
       - \\/ instead of / (escaped forward slash, valid in JSON spec but can cause issues)
       - \\' instead of ' (invalid JSON escape)
       """
       text = text.replace("\\/", "/")
       text = text.replace("\\'", "'")
       return text
   ```

3. **Update `score_card()` function** to use the configurable model and JSON sanitizer:
   - Change the `client.messages.create` call: replace hardcoded `model="anthropic/claude-haiku-4.5"` with `model=_get_scoring_model()`
   - After extracting `text` from the response (after the code-fence stripping block), add `text = _sanitize_json_escapes(text)` BEFORE `_json.loads(text)`

4. **Update docstrings** to reflect the change:
   - Module docstring: Change "Claude Haiku-based" to "LLM-based" (e.g. `"""LLM-based relevance scorer for signal cards."""`)
   - `_build_scoring_prompt` docstring: Change "Build the scoring prompt for Claude Haiku" to "Build the scoring prompt for the LLM scorer"
   - `score_card` docstring: Change "Score a signal card using Claude Haiku structured outputs" to "Score a signal card using LLM structured outputs via OpenRouter"
   - Remove the `anthropic.APIError` from the Raises docstring since it may not be Anthropic anymore; leave just the generic exception handling

5. **Add a comment** near `DEFAULT_SCORING_MODEL` documenting Haiku as fallback:
   ```python
   # Fallback: set WATCHMAN_SCORING_MODEL=anthropic/claude-haiku-4.5 to revert to Haiku
   DEFAULT_SCORING_MODEL = "google/gemini-2.0-flash-001"
   ```
  </action>
  <verify>
    <automated>cd /Users/paul/paul/Projects/watchman && python -c "from watchman.scoring.scorer import _get_scoring_model, _sanitize_json_escapes, DEFAULT_SCORING_MODEL; assert DEFAULT_SCORING_MODEL == 'google/gemini-2.0-flash-001'; assert _get_scoring_model() == 'google/gemini-2.0-flash-001'; assert _sanitize_json_escapes('test\\/path') == 'test/path'; print('OK')"</automated>
  </verify>
  <done>scorer.py uses Gemini Flash by default, model is configurable via WATCHMAN_SCORING_MODEL env var, JSON sanitization handles Flash escape quirks, Haiku documented as fallback option</done>
</task>

<task type="auto">
  <name>Task 2: Update tests for new model default and add sanitization tests</name>
  <files>tests/test_scoring.py</files>
  <action>
Make these changes to `tests/test_scoring.py`:

1. **Update imports** to include the new functions:
   ```python
   from watchman.scoring.scorer import _build_scoring_prompt, score_card, _get_scoring_model, _sanitize_json_escapes, DEFAULT_SCORING_MODEL
   ```

2. **Update `test_score_card_uses_correct_model`** (line ~213-228):
   - Change the test name to `test_score_card_uses_default_model`
   - Change the assertion from `assert call_kwargs.kwargs["model"] == "anthropic/claude-haiku-4.5"` to `assert call_kwargs.kwargs["model"] == "google/gemini-2.0-flash-001"`
   - Update the docstring to: `"""score_card should use Gemini Flash model via OpenRouter by default."""`

3. **Add new unit tests** after the existing prompt builder tests section (before the integration tests section):

   ```python
   # ---------------------------------------------------------------------------
   # Unit tests: model configuration and JSON sanitization
   # ---------------------------------------------------------------------------

   @pytest.mark.unit
   def test_default_scoring_model_is_gemini_flash() -> None:
       """DEFAULT_SCORING_MODEL should be Gemini 2.0 Flash."""
       assert DEFAULT_SCORING_MODEL == "google/gemini-2.0-flash-001"

   @pytest.mark.unit
   def test_get_scoring_model_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
       """_get_scoring_model should return default when env var is not set."""
       monkeypatch.delenv("WATCHMAN_SCORING_MODEL", raising=False)
       assert _get_scoring_model() == "google/gemini-2.0-flash-001"

   @pytest.mark.unit
   def test_get_scoring_model_respects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
       """_get_scoring_model should return env var value when set."""
       monkeypatch.setenv("WATCHMAN_SCORING_MODEL", "anthropic/claude-haiku-4.5")
       assert _get_scoring_model() == "anthropic/claude-haiku-4.5"

   @pytest.mark.unit
   def test_sanitize_json_escapes_forward_slash() -> None:
       """_sanitize_json_escapes should fix escaped forward slashes."""
       assert _sanitize_json_escapes('{"url":"https:\\/\\/example.com"}') == '{"url":"https://example.com"}'

   @pytest.mark.unit
   def test_sanitize_json_escapes_single_quote() -> None:
       """_sanitize_json_escapes should fix escaped single quotes."""
       assert _sanitize_json_escapes("{\\'key\\': \\'value\\'}") == "{'key': 'value'}"

   @pytest.mark.unit
   def test_sanitize_json_escapes_clean_input() -> None:
       """_sanitize_json_escapes should not modify clean JSON."""
       clean = '{"score": 8.5, "rationale": "Good signal"}'
       assert _sanitize_json_escapes(clean) == clean
   ```

4. **Add an integration test** for env-var-based model override:
   ```python
   @pytest.mark.integration
   async def test_score_card_uses_env_var_model(
       sample_card: SignalCard, rubric: RubricConfig, sample_rubric_score: RubricScore,
       monkeypatch: pytest.MonkeyPatch,
   ) -> None:
       """score_card should use model from WATCHMAN_SCORING_MODEL env var."""
       monkeypatch.setenv("WATCHMAN_SCORING_MODEL", "anthropic/claude-haiku-4.5")
       mock_response = MagicMock()
       mock_response.content = [MagicMock(text=sample_rubric_score.model_dump_json())]

       with patch("watchman.scoring.scorer.get_client") as mock_get_client:
           mock_client = MagicMock()
           mock_get_client.return_value = mock_client
           mock_client.messages.create.return_value = mock_response

           await score_card(sample_card, rubric)

           call_kwargs = mock_client.messages.create.call_args
           assert call_kwargs.kwargs["model"] == "anthropic/claude-haiku-4.5"
   ```
  </action>
  <verify>
    <automated>cd /Users/paul/paul/Projects/watchman && python -m pytest tests/test_scoring.py -x -v 2>&1 | tail -30</automated>
  </verify>
  <done>All existing tests pass with updated model assertions, new tests verify: default model is Flash, env var override works, JSON sanitization handles Flash quirks, clean input passes through unchanged</done>
</task>

</tasks>

<verification>
- `python -m pytest tests/test_scoring.py -x -v` -- all tests pass
- `python -c "from watchman.scoring.scorer import DEFAULT_SCORING_MODEL; print(DEFAULT_SCORING_MODEL)"` prints `google/gemini-2.0-flash-001`
- `grep -c 'haiku' src/watchman/scoring/scorer.py` returns 0 (no hardcoded haiku references in active code; only in fallback comment)
- `grep 'WATCHMAN_SCORING_MODEL' src/watchman/scoring/scorer.py` confirms env var configurability
</verification>

<success_criteria>
- Scoring pipeline defaults to google/gemini-2.0-flash-001 via OpenRouter
- WATCHMAN_SCORING_MODEL env var allows override (including reverting to Haiku)
- Flash JSON escape quirks (\\/, \\') are sanitized before parsing
- All unit and integration tests pass
- Haiku documented as fallback option in a comment, not deleted
</success_criteria>

<output>
After completion, create `.planning/quick/12-swap-watchman-scoring-model-from-haiku-t/12-SUMMARY.md`
</output>
