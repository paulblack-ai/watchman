---
phase: quick-11
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/notion/poller.py
  - src/watchman/notion/delivery.py
  - src/watchman/notion/setup.py
  - tests/test_notion_poller.py
autonomous: true
requirements: [FIX-POLLER-SELECT]

must_haves:
  truths:
    - "Poller reads Review Status and Gate 2 values from select-type Notion properties"
    - "Notion query filter uses select syntax to find actioned pages"
    - "Approval triggers enrichment pipeline"
    - "Snooze triggers 30-day snooze"
    - "Gate 2 approval triggers JSON output"
  artifacts:
    - path: "src/watchman/notion/poller.py"
      provides: "Fixed poller reading select properties"
      contains: "prop.get(\"select\")"
    - path: "tests/test_notion_poller.py"
      provides: "Unit tests for _extract_status_name and poll_notion_status"
  key_links:
    - from: "src/watchman/notion/poller.py"
      to: "Notion API response"
      via: "_extract_status_name reads select property"
      pattern: 'prop\.get\("select"\)'
    - from: "src/watchman/notion/poller.py"
      to: "Notion API query"
      via: "query_database filter uses select syntax"
      pattern: '"select".*does_not_equal'
---

<objective>
Fix the Notion poller to correctly read Review Status and Gate 2 as `select` type properties instead of `status` type.

Purpose: The Notion API only allows `status` type properties to be created via UI. Since we created Review Status and Gate 2 via API, they are `select` type. The poller's `_extract_status_name()` looks for `prop.get("status")` which returns None for select properties, and the query filter uses `"status": {"does_not_equal": ...}` which is invalid for select types.

Output: Working poller that reads select-type properties, correct query filters, and unit tests.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/watchman/notion/poller.py
@src/watchman/notion/delivery.py
@src/watchman/notion/setup.py

<interfaces>
From src/watchman/notion/delivery.py:
```python
def _build_review_status_property(status_name: str) -> dict:
    """Build a Notion status property value dict."""
    return {"status": {"name": status_name}}

def _build_select_property(value: str) -> dict:
    """Build a Notion select property value dict."""
    return {"select": {"name": value}}
```

From src/watchman/notion/setup.py:
```python
REQUIRED_PROPERTIES: dict[str, str] = {
    ...
    "Review Status": "status",   # BUG: actually select in Notion
    ...
    "Gate 2": "status",          # BUG: actually select in Notion
    ...
}
```

Notion API select property response format:
```json
{
  "properties": {
    "Review Status": {
      "type": "select",
      "select": {
        "name": "Approved",
        "id": "...",
        "color": "..."
      }
    }
  }
}
```

Notion API status property response format (what the code currently expects):
```json
{
  "properties": {
    "Review Status": {
      "type": "status",
      "status": {
        "name": "Approved",
        "id": "...",
        "color": "..."
      }
    }
  }
}
```

Notion API filter syntax for select:
```json
{"property": "Review Status", "select": {"does_not_equal": "To Review"}}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix poller property reading and query filter for select types</name>
  <files>src/watchman/notion/poller.py, src/watchman/notion/delivery.py, src/watchman/notion/setup.py</files>
  <action>
In `src/watchman/notion/poller.py`:

1. Update `_extract_status_name()` to read `select` type properties instead of `status`. The function currently does `prop.get("status")` on line 44 — change to `prop.get("select")`. Also update the docstring from "status property" to "select property". The function should try `select` first, then fall back to `status` for resilience:
   ```python
   select = prop.get("select") or prop.get("status")
   if not select:
       return None
   return select.get("name")
   ```

2. Update the `query_database` filter in `poll_notion_status()` (lines 103-113). Change both filter conditions from `"status"` to `"select"`:
   - `"status": {"does_not_equal": "To Review"}` becomes `"select": {"does_not_equal": "To Review"}`
   - `"status": {"does_not_equal": "Not Started"}` becomes `"select": {"does_not_equal": "Not Started"}`

In `src/watchman/notion/delivery.py`:

3. Update `_build_card_properties()` to use `_build_select_property` instead of `_build_review_status_property` for Review Status and Gate 2. On line 104, change:
   `"Review Status": _build_review_status_property("To Review")` to `"Review Status": _build_select_property("To Review")`
   On line 108, change:
   `"Gate 2": _build_review_status_property("Not Started")` to `"Gate 2": _build_select_property("Not Started")`
   Also update lines 314 and 334 where Gate 2 is set to "To Review" — change from `_build_review_status_property` to `_build_select_property`.

4. If `_build_review_status_property` is no longer used anywhere after these changes, remove it entirely. (Check for any remaining references first.)

In `src/watchman/notion/setup.py`:

5. Update `REQUIRED_PROPERTIES` to declare Review Status and Gate 2 as `"select"` instead of `"status"`:
   - `"Review Status": "select"`
   - `"Gate 2": "select"`
   Update `print_setup_instructions()` table to show `Select` instead of `Status` for these two properties.
  </action>
  <verify>
    <automated>cd /Users/paul/paul/Projects/watchman && python -c "from watchman.notion.poller import _extract_status_name; page = {'properties': {'Review Status': {'type': 'select', 'select': {'name': 'Approved'}}}}; assert _extract_status_name(page, 'Review Status') == 'Approved', 'select extraction failed'; page2 = {'properties': {'Gate 2': {'type': 'status', 'status': {'name': 'Approved'}}}}; assert _extract_status_name(page2, 'Gate 2') == 'Approved', 'status fallback failed'; print('OK: select and status fallback both work')"</automated>
  </verify>
  <done>
    - `_extract_status_name()` reads select properties (with status fallback)
    - Query filter uses `"select": {"does_not_equal": ...}` syntax
    - Delivery writes Review Status and Gate 2 as select properties
    - Setup.py declares Review Status and Gate 2 as select type
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add unit tests for poller select property handling</name>
  <files>tests/test_notion_poller.py</files>
  <behavior>
    - Test: _extract_status_name extracts name from a select-type property
    - Test: _extract_status_name extracts name from a status-type property (fallback)
    - Test: _extract_status_name returns None when property is missing
    - Test: _extract_status_name returns None when property has no select/status value
    - Test: poll_notion_status query uses select filter syntax (mock NotionClient.query_database, verify filter arg)
    - Test: poll_notion_status processes Approved review status from select property and triggers enrichment
    - Test: poll_notion_status processes Snoozed review status and triggers 30-day snooze
  </behavior>
  <action>
Create `tests/test_notion_poller.py` with unit tests covering the select property fix.

Use `unittest.mock.patch` to mock `NotionClient`, `get_connection`, and `CardRepository`.

For `_extract_status_name` tests: call the function directly with mock page dicts containing select-type and status-type properties.

For `poll_notion_status` integration tests: mock `NotionClient.query_database` to return pages with select-type Review Status and Gate 2 properties. Mock `os.environ` to provide NOTION_TOKEN and NOTION_DATABASE_ID. Verify the filter passed to `query_database` uses `"select"` syntax (not `"status"`). Verify downstream state changes are triggered.

Follow existing test conventions from `tests/test_gate2.py` and `tests/test_enrichment.py` for async test patterns.
  </action>
  <verify>
    <automated>cd /Users/paul/paul/Projects/watchman && python -m pytest tests/test_notion_poller.py -v</automated>
  </verify>
  <done>
    - All tests pass
    - Tests cover select property reading, status fallback, query filter syntax, approval trigger, snooze trigger
    - Tests use mocks (no real Notion API calls)
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_notion_poller.py -v` -- all new tests pass
2. `python -c "from watchman.notion.poller import _extract_status_name"` -- import succeeds
3. `python -c "from watchman.notion.delivery import _build_card_properties"` -- import succeeds
4. `python -c "from watchman.notion.setup import REQUIRED_PROPERTIES; assert REQUIRED_PROPERTIES['Review Status'] == 'select'; assert REQUIRED_PROPERTIES['Gate 2'] == 'select'"` -- setup declares correct types
5. `grep -c '"status"' src/watchman/notion/poller.py` -- should return 0 (no remaining status filter syntax)
</verification>

<success_criteria>
- Poller reads Review Status and Gate 2 from select-type Notion API responses
- Query filter uses `"select": {"does_not_equal": ...}` for both Review Status and Gate 2
- Delivery writes Review Status and Gate 2 as select properties (not status)
- Setup.py declares both as select type
- All tests pass
- Existing tests unaffected
</success_criteria>

<output>
After completion, create `.planning/quick/11-fix-notion-poller-for-select-properties/11-SUMMARY.md`
</output>
