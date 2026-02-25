---
phase: quick-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/config/sources.yaml
  - src/watchman/processing/normalizer.py
  - src/watchman/slack/blocks.py
  - src/watchman/slack/delivery.py
  - src/watchman/storage/repositories.py
autonomous: true
requirements: [QT3-01, QT3-02, QT3-03, QT3-04, QT3-05]
must_haves:
  truths:
    - "HuggingFace sources are not collected"
    - "Changelog pages are split into individual feature cards with specific titles"
    - "Cards have descriptive titles and summaries, not generic page titles"
    - "Slack footer shows a View More Signals button when more scored cards exist beyond the cap"
    - "Full pipeline runs end-to-end producing specific, split cards in Slack"
  artifacts:
    - path: "src/watchman/config/sources.yaml"
      provides: "No HuggingFace sources with enabled: true"
    - path: "src/watchman/processing/normalizer.py"
      provides: "LLM-powered changelog splitting and card specificity"
    - path: "src/watchman/slack/blocks.py"
      provides: "View More Signals button in footer"
    - path: "src/watchman/slack/delivery.py"
      provides: "Passes remaining card count and triggers view-more footer"
  key_links:
    - from: "normalizer.py"
      to: "llm_client.get_client()"
      via: "LLM call for changelog splitting"
    - from: "delivery.py"
      to: "blocks.build_review_footer()"
      via: "view more button when total > showing"
---

<objective>
Improve signal quality by: disabling HuggingFace sources, splitting changelog pages into individual feature cards via LLM, improving card specificity, adding "View More Signals" to Slack delivery, and re-running the full pipeline.

Purpose: Current changelogs produce single vague cards (e.g., "What's New - Notion" with "Product improvements, updates, and fixes"). Each changelog entry should become its own card with a specific title and description.

Output: Updated normalizer with LLM-powered changelog splitting, updated Slack delivery with "view more" option, fresh pipeline run with improved cards.
</objective>

<execution_context>
@/Users/salfaqih/.claude/get-shit-done/workflows/execute-plan.md
@/Users/salfaqih/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/watchman/config/sources.yaml
@src/watchman/processing/normalizer.py
@src/watchman/slack/delivery.py
@src/watchman/slack/blocks.py
@src/watchman/storage/repositories.py
@src/watchman/scoring/scorer.py
@src/watchman/llm_client.py
@src/watchman/models/signal_card.py
@src/watchman/models/raw_item.py
@src/watchman/collectors/scrape.py
@src/watchman/scripts/reset_and_collect.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Disable HuggingFace, add LLM changelog splitting to normalizer, improve card specificity</name>
  <files>
    src/watchman/config/sources.yaml
    src/watchman/processing/normalizer.py
  </files>
  <action>
**1a. Disable HuggingFace in sources.yaml:**
There are no HuggingFace sources currently in sources.yaml (confirmed by reading it). No changes needed here. If user meant something else, skip this sub-task.

**1b. Add LLM-powered changelog splitting to normalizer.py:**

The core problem: `ScrapeCollector` produces ONE `RawItem` per changelog page (e.g., Notion's /releases page becomes one item with title "What's New - Notion" and a 500-char summary snippet). The normalizer currently does a 1:1 mapping from RawItem to SignalCard.

Add a new async function `split_changelog_item(item: RawItem) -> list[dict]` that:
- Detects changelog-style raw items by checking: (a) source_name contains "Changelog" (from sources.yaml tier 3 names like "Notion Changelog", "Linear Changelog", etc.), or (b) the summary/raw_data contains multiple date-stamped entries or release headings.
- For detected changelogs, calls the LLM (via `get_client()` from `watchman.llm_client`) with Claude Haiku (`anthropic/claude-haiku-4.5`) to extract individual features. Use `asyncio.to_thread` for the sync client call (same pattern as scorer.py).
- Prompt should be: "Extract individual features/updates from this changelog page. For each feature, provide a specific title and a 1-2 sentence description of what it does. Return JSON array: [{\"title\": \"...\", \"description\": \"...\"}]. If there's only one feature or this isn't a changelog, return a single item with a more specific title/description than the page title."
- Pass the item's title, URL, and full summary text to the LLM.
- Parse the JSON array response (handle markdown code fences like scorer.py does).
- Return list of dicts with `title` and `description` keys.

**1c. Modify `normalize_raw_item` to accept optional override title/summary:**
Add optional parameters `override_title: str | None = None` and `override_summary: str | None = None` to `normalize_raw_item()`. When provided, use them instead of `item.title` and `item.summary`.

**1d. Modify `process_unprocessed` to use splitting:**
In the main loop of `process_unprocessed`, before calling `normalize_raw_item`:
- Check if the item is a changelog candidate (source_name contains "Changelog" or collector_type == "scrape" and tier == 3).
- If yes, call `await split_changelog_item(item)`.
- If splitting returns multiple entries, create one SignalCard per entry using `normalize_raw_item(item, tier, override_title=entry["title"], override_summary=entry["description"])`. Each card gets its own URL (same URL but different title/fingerprint) and distinct content_fingerprint.
- If splitting returns a single entry, still use the improved title/description from the LLM (fixes the specificity problem).
- If the LLM call fails, fall back to the original 1:1 normalization with a warning log.

**1e. Improve specificity for non-changelog items too:**
For ALL scrape-type items (not just changelogs), add an LLM call to generate a more specific title and summary if the current title looks generic. Detect generic titles by checking if the title matches common patterns like the source/site name without specifics, or if summary is very short/generic (< 50 chars or matches patterns like "Product improvements, updates, and fixes").

Use a lightweight prompt: "Given this signal title and summary, provide a more specific and descriptive title (max 80 chars) and a 1-2 sentence summary. Return JSON: {\"title\": \"...\", \"summary\": \"...\"}". Only call this for items where the title appears generic. If the title already looks specific (contains version numbers, feature names, etc.), skip the LLM call.
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/Projects/watchman && python -c "from watchman.processing.normalizer import split_changelog_item, normalize_raw_item, process_unprocessed; print('imports OK')"</automated>
  </verify>
  <done>
    - Normalizer has `split_changelog_item()` that calls LLM to extract individual features from changelog pages
    - `process_unprocessed` creates multiple cards from a single changelog raw item
    - Generic titles get improved via LLM before card creation
    - Fallback to original behavior if LLM fails
  </done>
</task>

<task type="auto">
  <name>Task 2: Add "View More Signals" button to Slack delivery footer</name>
  <files>
    src/watchman/slack/blocks.py
    src/watchman/slack/delivery.py
    src/watchman/storage/repositories.py
  </files>
  <action>
**2a. Update `build_review_footer` in blocks.py:**

Modify `build_review_footer(showing: int, total: int)` to include a "View More Signals" button when `total > showing`. The button should use action_id `view_more_signals`. The button value should be a JSON string with `{"offset": showing, "remaining": total - showing}`.

When `total <= showing`, keep the current footer without a button (just the context line).

The updated footer should show:
- Context line: ":page_facing_up: Showing {showing} of {total} signals today"
- If more exist: An actions block with a button: "View {remaining} more signals" (using `total - showing` for the count).

**2b. Add `find_next_scored_batch` to CardRepository in repositories.py:**

Add a new method `find_next_scored_batch(self, offset: int, limit: int) -> list[SignalCard]` that returns the next batch of scored cards after the initial delivery. Query should be similar to `find_top_scored_today` but with OFFSET:

```sql
SELECT * FROM cards
WHERE relevance_score IS NOT NULL
AND (
    (review_state = 'pending' AND date(created_at) = date('now'))
    OR (review_state = 'snoozed' AND snooze_until <= datetime('now'))
)
ORDER BY relevance_score DESC, tier ASC
LIMIT ? OFFSET ?
```

**2c. No changes needed to delivery.py** — the footer function already receives `showing` and `total` from `deliver_daily_review`, and the Slack action handler for `view_more_signals` will be handled by the existing Bolt action handler infrastructure. The action handler registration can be added as a follow-up if needed, but the button and query infrastructure should be in place.

Note: The actual action handler for `view_more_signals` would need to be added to the Slack action handlers (likely in `src/watchman/slack/actions.py` or similar). For now, just ensure the button is rendered and the repository method exists. The handler can post the next batch of cards when clicked.
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/Projects/watchman && python -c "from watchman.slack.blocks import build_review_footer; blocks = build_review_footer(5, 20); assert any(b.get('type') == 'actions' for b in blocks), 'Missing actions block'; print('View more button OK')"</automated>
  </verify>
  <done>
    - Footer shows "View More Signals" button when total > showing
    - Button includes offset and remaining count in value
    - CardRepository has `find_next_scored_batch` for paginated retrieval
    - When total <= showing, footer renders without a button (existing behavior)
  </done>
</task>

<task type="auto">
  <name>Task 3: Re-run full pipeline with fresh DB</name>
  <files>
    src/watchman/scripts/reset_and_collect.py
  </files>
  <action>
Run the existing `reset_and_collect.py` script which already performs the full pipeline: wipe DB, collect last 2 weeks, normalize (now with changelog splitting), score, and deliver to Slack.

The .env already has a fresh SLACK_CHANNEL_ID (C0AGZHW27NX). No changes needed to the .env or the script itself — the script already calls `process_unprocessed` which will now use the new changelog splitting logic.

Execute:
```bash
cd /Users/salfaqih/paul/Projects/watchman && python src/watchman/scripts/reset_and_collect.py
```

Monitor the output for:
- Successful collection from all enabled sources (HuggingFace should not appear since it was never in sources.yaml)
- Changelog sources (Notion, Figma, Linear, Vercel, Supabase, Stripe) producing MULTIPLE cards instead of one
- Specific card titles (not "What's New - Notion" but individual feature names)
- Successful scoring and Slack delivery
- Footer message showing "View More Signals" if total > cap

If the pipeline fails at any step, debug and fix. Common issues:
- LLM rate limits: Add small delays between changelog splitting calls if needed
- JSON parse errors from LLM: Ensure robust fallback to original behavior
- Slack delivery errors: Check token/channel validity
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/Projects/watchman && python -c "
import asyncio, sqlite3
db = sqlite3.connect('watchman.db')
db.row_factory = sqlite3.Row
cards = db.execute('SELECT title, source_name FROM cards WHERE duplicate_of IS NULL AND source_name LIKE \"%Changelog%\" LIMIT 10').fetchall()
for c in cards:
    print(f'{c[\"source_name\"]}: {c[\"title\"]}')
assert len(cards) > 0, 'No changelog cards found'
# Check that titles are specific, not just page names
generic_titles = [c for c in cards if c['title'] in ('What\\'s New – Notion', 'Figma Changelog', 'Linear Changelog')]
assert len(generic_titles) == 0, f'Found generic titles: {[c[\"title\"] for c in generic_titles]}'
print(f'Found {len(cards)} specific changelog cards - OK')
"</automated>
  </verify>
  <done>
    - Pipeline ran end-to-end successfully
    - Changelog sources produced multiple specific cards (not one vague card per page)
    - Cards have specific, descriptive titles about actual features
    - Slack channel shows review cards with improved specificity
    - Footer shows "View More Signals" button if applicable
  </done>
</task>

</tasks>

<verification>
1. No HuggingFace sources in the collection (was never in sources.yaml, confirmed)
2. Changelog pages (Notion, Figma, Linear, etc.) produce multiple cards with specific titles
3. Card titles describe actual features, not just page names
4. Slack footer includes "View More Signals" button when there are more cards than the daily cap
5. Full pipeline completes without errors
</verification>

<success_criteria>
- Changelog sources produce 3+ cards each (not 1 vague card)
- Zero cards with titles like "What's New - Notion" or "Figma Changelog" (must be specific feature titles)
- Slack delivery footer has "View More" button when total scored > daily cap
- Pipeline runs end-to-end: collect -> normalize (with splitting) -> score -> deliver
</success_criteria>

<output>
After completion, create `.planning/quick/3-disable-huggingface-split-changelogs-int/3-SUMMARY.md`
</output>
