---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/slack/actions.py
  - src/watchman/slack/app.py
  - tests/test_view_more_signals.py
autonomous: true
requirements: ["QUICK-4"]
must_haves:
  truths:
    - "Clicking 'View More Signals' posts the next 5 cards to the channel"
    - "A new footer with updated 'Showing X of Y' and another 'View More' button appears if cards remain"
    - "When all cards have been shown, no 'View More' button appears in the final footer"
  artifacts:
    - path: "src/watchman/slack/actions.py"
      provides: "view_more_signals action handler"
      contains: "view_more_signals"
    - path: "src/watchman/slack/app.py"
      provides: "Registration of view_more handler"
      contains: "view_more_signals"
  key_links:
    - from: "src/watchman/slack/actions.py"
      to: "src/watchman/storage/repositories.py"
      via: "CardRepository.find_next_scored_batch(offset, limit=5)"
      pattern: "find_next_scored_batch"
    - from: "src/watchman/slack/actions.py"
      to: "src/watchman/slack/blocks.py"
      via: "build_signal_card_blocks + build_review_footer"
      pattern: "build_review_footer"
---

<objective>
Wire up the "View More Signals" button to paginate through scored cards in increments of 5.

Purpose: The button and the paginated DB query already exist (from quick task 3). The missing piece is the Slack action handler that responds to button clicks, fetches the next batch, posts cards, and shows an updated footer.

Output: Working pagination — clicking "View More Signals" delivers the next 5 cards with a new footer, repeating until all cards are shown.
</objective>

<execution_context>
@/Users/salfaqih/.claude/get-shit-done/workflows/execute-plan.md
@/Users/salfaqih/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/watchman/slack/actions.py (existing action handlers — follow the same asyncio.run pattern)
@src/watchman/slack/blocks.py (build_signal_card_blocks, build_review_footer already exist)
@src/watchman/slack/app.py (register_actions, register_gate2_actions — add new registration)
@src/watchman/storage/repositories.py (find_next_scored_batch and count_scored_today already exist)
@src/watchman/scoring/models.py (RubricScore for parsing score_breakdown)

<interfaces>
<!-- Key existing contracts the executor needs -->

From src/watchman/storage/repositories.py:
```python
async def find_next_scored_batch(self, offset: int, limit: int) -> list[SignalCard]:
    """Uses same criteria as find_top_scored_today but with OFFSET for pagination."""

async def count_scored_today(self) -> int:
    """Count all scored cards created today."""
```

From src/watchman/slack/blocks.py:
```python
def build_signal_card_blocks(card: SignalCard, score: RubricScore) -> list[dict]:
    """Build Block Kit blocks for an unreviewed signal card."""

def build_review_footer(showing: int, total: int) -> list[dict]:
    """Footer with 'View More Signals' button when remaining > 0.
    Button value: json.dumps({"offset": showing, "remaining": remaining})
    action_id: "view_more_signals"
    """
```

From src/watchman/slack/actions.py:
```python
def _get_db_path() -> Path:
async def _load_card_by_id(repo: CardRepository, card_id: int) -> SignalCard | None:
def _post_error_ephemeral(client, body: dict, message: str) -> None:
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add view_more_signals action handler and register it</name>
  <files>
    src/watchman/slack/actions.py
    src/watchman/slack/app.py
  </files>
  <action>
In `src/watchman/slack/actions.py`:

1. Add `build_review_footer` and `build_signal_card_blocks` to the existing imports from `watchman.slack.blocks` (line 14-18). `build_signal_card_blocks` is already imported at the top level but only used in delivery.py — confirm it is in the import list.

2. Create a new function `register_view_more_action(app: App) -> None:` that registers a handler for `action_id="view_more_signals"`. Follow the exact same pattern as `register_actions` and `register_gate2_actions`.

3. The handler logic (`_handle_view_more_signals`):
   - `ack()` immediately (required by Slack within 3s)
   - Parse the button value: `json.loads(action["value"])` to get `{"offset": int, "remaining": int}`
   - Set `PAGE_SIZE = 5`
   - Use `asyncio.run()` to call an async inner function that:
     a. Opens DB via `get_connection(_get_db_path())`
     b. Calls `repo.find_next_scored_batch(offset=offset, limit=PAGE_SIZE)`
     c. Calls `repo.count_scored_today()` for total
   - For each card in the batch:
     - Parse `card.score_breakdown` into `RubricScore` (skip card if None or parse fails, same pattern as delivery.py lines 78-87)
     - Build blocks via `build_signal_card_blocks(card, score)`
     - Post to channel via `client.chat_postMessage(channel=channel_id, blocks=blocks, text=f"Signal: {card.title}")`
     - Save `slack_message_ts` and review state via `repo.set_review_state(card.id, "pending", slack_ts=message_ts, slack_channel=channel_id)` (same as delivery.py lines 100-109)
   - After posting all cards, compute `total_shown = offset + delivered_count`
   - Post a new footer via `build_review_footer(total_shown, total)` — this automatically includes another "View More" button if `total > total_shown`
   - Get `channel_id` from `body["channel"]["id"]`
   - Wrap everything in try/except, log errors, post ephemeral on failure

4. In `src/watchman/slack/app.py`:
   - Add `register_view_more_action` to the import from `watchman.slack.actions`
   - Call `register_view_more_action(app)` after the existing `register_gate2_actions(app)` call (around line 31)

IMPORTANT: The set_review_state DB call for each posted card needs its own `async with get_connection()` block (same pattern as delivery.py lines 102-109), since each card post is a separate operation.

Do NOT modify the existing footer message (the one with the old "View More" button) — Slack keeps it as-is. The new cards and new footer are posted as new messages below.
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/Projects/watchman && python -c "from watchman.slack.actions import register_view_more_action; print('import OK')" && python -c "from watchman.slack.app import create_slack_app; print('app creation OK')"</automated>
  </verify>
  <done>
    - `view_more_signals` action handler exists in actions.py
    - Handler is registered in app.py via `register_view_more_action`
    - Handler fetches next 5 cards, posts them as signal cards, posts updated footer
    - Footer includes another "View More" button when cards remain
    - No "View More" button when all cards have been shown
  </done>
</task>

<task type="auto">
  <name>Task 2: Add unit test for view_more handler logic</name>
  <files>
    tests/test_view_more_signals.py
  </files>
  <action>
Create `tests/test_view_more_signals.py` with pytest tests:

1. **test_handle_view_more_posts_next_batch**: Mock the DB to return 3 cards (simulating a partial last page), mock the Slack client. Build a fake `body` payload matching Slack's action format:
   ```python
   body = {
       "actions": [{"value": json.dumps({"offset": 5, "remaining": 8})}],
       "channel": {"id": "C123"},
       "user": {"id": "U123"},
       "message": {"ts": "1234.5678"},
   }
   ```
   Verify: `client.chat_postMessage` called 3 times for cards + 1 time for footer (4 total). Footer call's blocks should contain "View More" button since remaining > 3.

2. **test_handle_view_more_final_page_no_button**: Mock DB to return 2 cards with total=7 and offset=5. Verify the footer posted does NOT contain a "View More" button (total_shown=7 == total=7).

3. **test_handle_view_more_skips_cards_without_score**: Mock DB to return 2 cards, one with `score_breakdown=None`. Verify only 1 card message posted (the one with valid score), plus 1 footer.

Use `unittest.mock.patch` and `unittest.mock.AsyncMock` for DB operations. Use `unittest.mock.MagicMock` for the Slack client. Import `build_review_footer` to verify button presence in the footer blocks.

Follow existing test patterns in the project (pytest, no classes needed).
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/Projects/watchman && python -m pytest tests/test_view_more_signals.py -v</automated>
  </verify>
  <done>
    - 3 test cases pass covering: normal pagination, final page (no button), skip cards without scores
    - Tests verify correct number of Slack API calls and footer content
  </done>
</task>

</tasks>

<verification>
1. Import check: `python -c "from watchman.slack.actions import register_view_more_action"`
2. App creation: `python -c "from watchman.slack.app import create_slack_app; print('OK')"`
3. Tests pass: `python -m pytest tests/test_view_more_signals.py -v`
</verification>

<success_criteria>
- Clicking "View More Signals" in Slack posts the next 5 scored cards as reviewable signal cards
- A new footer appears showing updated "Showing X of Y signals today"
- If more cards remain beyond the new batch, the footer includes another "View More Signals" button
- If all cards have been shown, the footer has no button
- Cards without valid score_breakdown are silently skipped
- All 3 unit tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/4-view-more-signals-in-increments-of-5/4-SUMMARY.md`
</output>
