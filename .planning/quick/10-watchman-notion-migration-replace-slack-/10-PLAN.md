---
phase: quick-10
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/notion/__init__.py
  - src/watchman/notion/client.py
  - src/watchman/notion/delivery.py
  - src/watchman/notion/poller.py
  - src/watchman/notion/setup.py
  - src/watchman/models/signal_card.py
  - src/watchman/storage/database.py
  - src/watchman/storage/repositories.py
  - src/watchman/enrichment/pipeline.py
  - src/watchman/scheduler/jobs.py
  - src/watchman/main.py
  - pyproject.toml
autonomous: false
requirements: [NOTION-MIGRATE]

must_haves:
  truths:
    - "Scored signal cards appear as Notion database rows with correct properties"
    - "Changing Review Status in Notion to Approved/Rejected/Snoozed updates SQLite review_state"
    - "Approved cards trigger enrichment and enrichment results appear as Notion page content"
    - "Gate 2 status changes in Notion update SQLite gate2_state"
    - "Watchman starts and runs with NOTION_TOKEN + NOTION_DATABASE_ID instead of Slack tokens"
  artifacts:
    - path: "src/watchman/notion/client.py"
      provides: "Notion API client wrapper with rate limiting"
    - path: "src/watchman/notion/delivery.py"
      provides: "Push scored cards to Notion database"
    - path: "src/watchman/notion/poller.py"
      provides: "Poll Notion for status changes, sync back to SQLite"
    - path: "src/watchman/notion/setup.py"
      provides: "Notion database property schema validation/setup"
    - path: "src/watchman/main.py"
      provides: "Updated entry point with Notion instead of Slack"
  key_links:
    - from: "src/watchman/notion/delivery.py"
      to: "src/watchman/storage/repositories.py"
      via: "CardRepository queries for scored cards"
      pattern: "find_top_scored_today|find_enriched_pending_gate2"
    - from: "src/watchman/notion/poller.py"
      to: "src/watchman/storage/repositories.py"
      via: "Updates review_state and gate2_state from Notion status"
      pattern: "set_review_state|set_gate2_state"
    - from: "src/watchman/notion/poller.py"
      to: "src/watchman/enrichment/pipeline.py"
      via: "Triggers enrichment when card approved in Notion"
      pattern: "enrich_approved_card"
    - from: "src/watchman/scheduler/jobs.py"
      to: "src/watchman/notion/delivery.py"
      via: "Scheduled delivery job calls Notion delivery"
      pattern: "deliver_daily_review_notion"
    - from: "src/watchman/scheduler/jobs.py"
      to: "src/watchman/notion/poller.py"
      via: "Scheduled polling job checks Notion for status changes"
      pattern: "poll_notion_status"
---

<objective>
Replace Slack as Watchman's review surface with Notion interactive card layout.

Purpose: Slack is too laggy for signal triage. Notion provides faster, richer card-based interaction
with persistent, filterable, sortable database views. Signal cards become Notion database rows with
status properties that Paul updates directly. A polling loop syncs Notion status changes back to
SQLite to trigger enrichment and Gate 2 workflows.

Output: Complete Notion integration replacing all Slack review functionality. Slack module retained
but disabled by default (no Slack tokens needed). Watchman starts with NOTION_TOKEN and
NOTION_DATABASE_ID environment variables.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/watchman/models/signal_card.py
@src/watchman/storage/database.py
@src/watchman/storage/repositories.py
@src/watchman/slack/delivery.py
@src/watchman/slack/actions.py
@src/watchman/slack/blocks.py
@src/watchman/slack/app.py
@src/watchman/enrichment/pipeline.py
@src/watchman/scheduler/jobs.py
@src/watchman/main.py
@pyproject.toml

<interfaces>
<!-- Existing interfaces the executor needs -->

From src/watchman/models/signal_card.py:
```python
class SignalCard(BaseModel):
    id: int | None = None
    title: str
    source_name: str
    date: datetime
    url: str
    tier: Literal[1, 2, 3]
    summary: str | None = None
    collector_type: Literal["rss", "api", "scrape", "jina", "youtube"]
    url_hash: str
    relevance_score: float | None = None
    score_breakdown: str | None = None  # JSON string
    top_dimension: str | None = None
    review_state: str = "pending"
    snooze_until: datetime | None = None
    enrichment_state: str = "pending"
    enrichment_data: str | None = None  # JSON string of IcebreakerToolEntry
    gate2_state: str = "pending"
    enrichment_attempt_count: int = 1
    # New field to add:
    # notion_page_id: str | None = None
```

From src/watchman/storage/repositories.py:
```python
class CardRepository:
    async def find_top_scored_today(self, limit: int) -> list[SignalCard]
    async def count_scored_today(self) -> int
    async def set_review_state(self, card_id, state, slack_ts=None, slack_channel=None)
    async def find_enriched_pending_gate2(self) -> list[SignalCard]
    async def set_gate2_state(self, card_id, state, slack_ts=None)
    async def save_enrichment(self, card_id, entry)
    async def snooze_card(self, card_id, days=30)
    async def find_approved_unenriched(self) -> list[SignalCard]
```

From src/watchman/scoring/models.py:
```python
class RubricScore(BaseModel):
    composite_score: float
    top_dimension: str
    taxonomy_fit: DimensionScore
    novel_capability: DimensionScore
    adoption_traction: DimensionScore
    credibility: DimensionScore
```

Notion API property mapping (from task spec):
| SQLite Column          | Notion Property  | Type                    |
|------------------------|------------------|-------------------------|
| title                  | Title            | title                   |
| source_name            | Source           | select                  |
| tier                   | Tier             | select (1/2/3)          |
| relevance_score        | Score            | number                  |
| top_dimension          | Top Dimension    | select                  |
| review_state           | Review Status    | status                  |
| date                   | Published        | date                    |
| url                    | URL              | url                     |
| summary                | Summary          | rich_text (page body)   |
| score_breakdown        | Rubric           | rich_text (page body)   |
| enrichment_state       | Enrichment       | select                  |
| enrichment_data        | (page body)      | rich_text               |
| gate2_state            | Gate 2           | status                  |
| snooze_until           | Snooze Until     | date                    |
| enrichment_attempt_count | Attempts       | number                  |
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create Notion client module, database setup, and SQLite migration</name>
  <files>
    src/watchman/notion/__init__.py
    src/watchman/notion/client.py
    src/watchman/notion/setup.py
    src/watchman/models/signal_card.py
    src/watchman/storage/database.py
    src/watchman/storage/repositories.py
    pyproject.toml
  </files>
  <action>
    1. Add `notion-client>=2.0` to pyproject.toml dependencies (official Notion SDK for Python).

    2. Create `src/watchman/notion/__init__.py` (empty).

    3. Create `src/watchman/notion/client.py` — a thin wrapper around the Notion SDK:
       - `NotionClient` class that takes `token: str` and `database_id: str`
       - Uses `notion_client.Client(auth=token)` internally
       - Rate limiting: simple time.sleep(0.35) between API calls (stays under 3 req/sec)
       - Methods:
         - `create_page(properties: dict, children: list[dict] | None = None) -> str` — creates a Notion database page, returns page_id
         - `update_page(page_id: str, properties: dict) -> None` — updates page properties
         - `update_page_content(page_id: str, children: list[dict]) -> None` — appends blocks to a page (for enrichment data)
         - `query_database(filter: dict | None = None, sorts: list[dict] | None = None) -> list[dict]` — queries the database with optional filter/sort, handles pagination (Notion returns max 100 per request)
         - `get_page(page_id: str) -> dict` — get a single page by ID
       - All methods wrap calls in try/except, log errors, re-raise as `NotionAPIError(message, status_code)` custom exception
       - Include a module-level `NotionAPIError(Exception)` class

    4. Create `src/watchman/notion/setup.py` — database schema validation:
       - `validate_database_schema(client: NotionClient) -> dict[str, bool]` — queries the database metadata, checks that required properties exist with correct types
       - Required properties to check: Title (title), Source (select), Tier (select), Score (number), Top Dimension (select), Review Status (status), Published (date), URL (url), Enrichment (select), Gate 2 (status), Snooze Until (date), Attempts (number)
       - Returns dict mapping property_name -> exists_with_correct_type
       - Logs warnings for missing/mistyped properties but does NOT auto-create them (user sets up Notion DB manually)
       - `print_setup_instructions() -> None` — prints instructions for creating the Notion database with all required properties and their types

    5. Add `notion_page_id` field to SignalCard model:
       - Add `notion_page_id: str | None = None` field to SignalCard in `src/watchman/models/signal_card.py`

    6. Add SQLite migration in `src/watchman/storage/database.py`:
       - Create `migrate_notion(db_path: Path)` async function (idempotent, same pattern as migrate_phase2/3/4)
       - Add column: `ALTER TABLE cards ADD COLUMN notion_page_id TEXT`
       - Add index: `CREATE INDEX IF NOT EXISTS idx_cards_notion_page_id ON cards(notion_page_id)`
       - Call `await migrate_notion(db_path)` at the end of `init_db()`

    7. Update `CardRepository._row_to_card()` in `src/watchman/storage/repositories.py`:
       - Add `notion_page_id=safe_get("notion_page_id")` to the SignalCard constructor
       - Add `save_notion_page_id(self, card_id: int, page_id: str) -> None` method — `UPDATE cards SET notion_page_id = ? WHERE id = ?`
       - Add `find_cards_with_notion_page(self) -> list[SignalCard]` method — `SELECT * FROM cards WHERE notion_page_id IS NOT NULL AND review_state = 'pending' ORDER BY created_at DESC` (used by poller to check for status changes)
       - Add `find_cards_needing_notion_sync(self) -> list[SignalCard]` method — finds scored cards that have no notion_page_id yet: `SELECT * FROM cards WHERE relevance_score IS NOT NULL AND duplicate_of IS NULL AND notion_page_id IS NULL ORDER BY relevance_score DESC`
  </action>
  <verify>
    <automated>cd /Users/paul/paul/Projects/watchman && python -c "
from watchman.notion.client import NotionClient, NotionAPIError
from watchman.notion.setup import validate_database_schema, print_setup_instructions
from watchman.models.signal_card import SignalCard
# Verify notion_page_id field exists
card = SignalCard(title='test', source_name='test', date='2024-01-01T00:00:00Z', url='http://test.com', tier=1, collector_type='rss', url_hash='abc123', notion_page_id='page-123')
assert card.notion_page_id == 'page-123'
print('All imports and model field OK')
"</automated>
  </verify>
  <done>
    - NotionClient class exists with create_page, update_page, update_page_content, query_database, get_page methods
    - NotionAPIError exception class exists
    - Database schema validation function exists with print_setup_instructions
    - SignalCard has notion_page_id field
    - SQLite migration adds notion_page_id column (idempotent)
    - CardRepository has save_notion_page_id, find_cards_with_notion_page, find_cards_needing_notion_sync methods
    - notion-client added to pyproject.toml
  </done>
</task>

<task type="auto">
  <name>Task 2: Create Notion delivery and polling modules, replace Slack in enrichment pipeline</name>
  <files>
    src/watchman/notion/delivery.py
    src/watchman/notion/poller.py
    src/watchman/enrichment/pipeline.py
    src/watchman/scheduler/jobs.py
  </files>
  <action>
    1. Create `src/watchman/notion/delivery.py` — replaces `src/watchman/slack/delivery.py`:
       - `async def deliver_daily_review_notion(db_path: Path, rubric_path: Path) -> int` — main delivery function:
         - Reads NOTION_TOKEN and NOTION_DATABASE_ID from env vars
         - Raises EnvironmentError if either is missing
         - Loads daily_cap from rubric.yaml (same _load_daily_cap pattern as Slack delivery)
         - Creates NotionClient instance
         - Queries CardRepository.find_top_scored_today(limit=cap) + count_scored_today()
         - For each card with score_breakdown:
           - Parses RubricScore from card.score_breakdown
           - Builds Notion properties dict: Title=card.title, Source=card.source_name, Tier=str(card.tier), Score=card.relevance_score, Top Dimension=score.top_dimension, Review Status="To Review" (Notion status), Published=card.date.isoformat(), URL=card.url, Enrichment=card.enrichment_state, Gate 2="Not Started" (Notion status), Attempts=card.enrichment_attempt_count
           - Builds page children (body content): Heading "Summary" + paragraph with card.summary, Heading "Rubric Breakdown" + paragraph blocks with each dimension score and rationale
           - Calls client.create_page(properties, children) -> page_id
           - Saves notion_page_id to DB via repo.save_notion_page_id(card.id, page_id)
           - Keeps review_state as "pending" in SQLite (Notion shows "To Review")
         - Logs delivery count
         - Returns number of cards delivered
       - `deliver_daily_review_notion_sync(db_path, rubric_path) -> None` — sync wrapper with asyncio.run() for APScheduler (same pattern as Slack's deliver_daily_review_sync)
       - `async def deliver_gate2_to_notion(card_id: int, db_path: Path) -> None` — replaces async_deliver_gate2_card:
         - Loads card from DB, validates enrichment_data exists
         - Parses IcebreakerToolEntry from card.enrichment_data
         - If card already has notion_page_id: UPDATE existing page properties (set Enrichment="complete", Gate 2="To Review") and APPEND enrichment content blocks (Heading "Enrichment: {entry.name}", paragraphs for description, capabilities list, pricing, API surface, integration hooks)
         - If card has no notion_page_id (edge case): create new page with all properties + enrichment content
         - Update gate2_state to "pending" in SQLite

    2. Create `src/watchman/notion/poller.py` — replaces Slack action handlers:
       - `async def poll_notion_status(db_path: Path) -> int` — main polling function:
         - Creates NotionClient from env vars
         - Queries Notion database for pages where Review Status != "To Review" (i.e., user changed it)
         - For each page, extracts: page_id, Review Status, Gate 2 status
         - Loads matching card from SQLite by notion_page_id
         - Maps Notion status values to SQLite states:
           - Review Status: "Approved" -> "approved", "Rejected" -> "rejected", "Snoozed" -> "snoozed", "To Review" -> "pending" (no-op)
           - Gate 2: "Approved" -> "gate2_approved", "Rejected" -> "gate2_rejected", "To Review" -> "pending" (no-op)
         - For each card whose review_state changed:
           - Updates review_state in SQLite via repo.set_review_state()
           - If newly approved: triggers enrichment via `enrich_approved_card(card_id, db_path)` (same as Slack approve handler)
           - If newly snoozed: calls repo.snooze_card(card_id, days=30) and updates Notion page Snooze Until property
         - For each card whose gate2_state changed:
           - Updates gate2_state in SQLite via repo.set_gate2_state()
           - If gate2_approved: writes JSON output via write_tool_entry() + saves output_path (same as Slack Gate 2 approve handler)
           - Updates Notion page Enrichment property to reflect final state
         - Returns count of status changes processed
       - `poll_notion_status_sync(db_path: Path) -> None` — sync wrapper for APScheduler

    3. Update `src/watchman/enrichment/pipeline.py`:
       - In `enrich_approved_card()`: Replace the Gate 2 Slack delivery call at the bottom (lines 96-103) with Notion delivery:
         - Replace `await async_deliver_gate2_card(card_id, db_path)` with:
           ```python
           notion_token = os.environ.get("NOTION_TOKEN")
           if notion_token:
               from watchman.notion.delivery import deliver_gate2_to_notion
               await deliver_gate2_to_notion(card_id, db_path)
           else:
               # Fall back to Slack if Notion not configured
               await async_deliver_gate2_card(card_id, db_path)
           ```
         - Keep the existing async_deliver_gate2_card and deliver_gate2_card functions (Slack fallback) but they become dormant when NOTION_TOKEN is set

    4. Update `src/watchman/scheduler/jobs.py`:
       - Add `run_notion_delivery_job(db_path, rubric_path)` — sync wrapper calling deliver_daily_review_notion_sync
       - Add `schedule_notion_delivery_job(scheduler, db_path, rubric_path)` — schedules at 9 AM daily (same as Slack delivery), job id "deliver-daily-review-notion"
       - Add `run_notion_poll_job(db_path)` — sync wrapper calling poll_notion_status_sync
       - Add `schedule_notion_poll_job(scheduler, db_path)` — schedules every 45 seconds via IntervalTrigger, job id "poll-notion-status"
       - Keep existing Slack schedule functions (they will not be called when Notion is active)
  </action>
  <verify>
    <automated>cd /Users/paul/paul/Projects/watchman && python -c "
from watchman.notion.delivery import deliver_daily_review_notion, deliver_daily_review_notion_sync, deliver_gate2_to_notion
from watchman.notion.poller import poll_notion_status, poll_notion_status_sync
from watchman.scheduler.jobs import schedule_notion_delivery_job, schedule_notion_poll_job
print('All Notion delivery and poller imports OK')
"</automated>
  </verify>
  <done>
    - Notion delivery module creates database rows from scored cards with all properties and page content
    - Notion poller reads status changes and syncs back to SQLite (approve/reject/snooze for Gate 1, approve/reject for Gate 2)
    - Poller triggers enrichment on approval (same as Slack approve handler did)
    - Poller triggers JSON output write on Gate 2 approval (same as Slack Gate 2 approve handler did)
    - Enrichment pipeline delivers Gate 2 results to Notion instead of Slack (with Slack fallback)
    - Scheduler has Notion delivery job (daily 9 AM) and Notion poll job (every 45 seconds)
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Wire Notion into main.py and verify end-to-end</name>
  <files>
    src/watchman/main.py
  </files>
  <action>
    Update `src/watchman/main.py` to use Notion instead of Slack as the primary review surface:

    1. Add Notion integration block (after DB init, similar position to Slack block):
       ```python
       # Notion integration (replaces Slack as review surface)
       notion_token = os.environ.get("NOTION_TOKEN")
       notion_db_id = os.environ.get("NOTION_DATABASE_ID")
       notion_enabled = bool(notion_token and notion_db_id)

       if notion_enabled:
           from watchman.notion.setup import validate_database_schema
           from watchman.notion.client import NotionClient
           # Validate Notion database schema on startup
           try:
               client = NotionClient(token=notion_token, database_id=notion_db_id)
               schema_check = asyncio.run(validate_database_schema(client))
               missing = [k for k, v in schema_check.items() if not v]
               if missing:
                   logger.warning("Notion database missing properties: %s", ", ".join(missing))
               else:
                   logger.info("Notion database schema validated")
           except Exception:
               logger.exception("Failed to validate Notion database schema")
       else:
           logger.warning("NOTION_TOKEN/NOTION_DATABASE_ID not set, Notion features disabled")
       ```

    2. Keep Slack block but make it secondary — Slack runs only if tokens are set AND Notion is NOT enabled:
       ```python
       # Slack integration (legacy — only active if Notion is not configured)
       slack_enabled = False
       if not notion_enabled:
           slack_token = os.environ.get("SLACK_BOT_TOKEN")
           slack_app_token = os.environ.get("SLACK_APP_TOKEN")
           slack_enabled = bool(slack_token and slack_app_token)
           if slack_enabled:
               from watchman.slack.app import create_slack_app, start_socket_mode
               slack_app = create_slack_app()
               start_socket_mode(slack_app)
               logger.info("Slack listener started (legacy mode)")
           else:
               logger.warning("No review surface configured (set NOTION_TOKEN or SLACK_BOT_TOKEN)")
       ```

    3. Update scheduler wiring:
       - If notion_enabled: call `schedule_notion_delivery_job(scheduler, db_path, rubric_path)` and `schedule_notion_poll_job(scheduler, db_path)` — do NOT schedule Slack delivery
       - If slack_enabled (and not notion_enabled): keep existing Slack delivery + digest scheduling
       - Import the new schedule functions at the top of the conditional block

    4. Log which review surface is active: `logger.info("Review surface: %s", "Notion" if notion_enabled else "Slack" if slack_enabled else "None")`
  </action>
  <what-built>
    Complete Notion migration: Watchman now uses Notion as review surface instead of Slack.
    - Signal cards appear as Notion database rows with Title, Source, Tier, Score, etc.
    - Rubric breakdown and summary are in page body content
    - Polling job checks Notion every 45 seconds for Review Status / Gate 2 changes
    - Approval in Notion triggers enrichment pipeline
    - Enrichment results are appended to the Notion page
    - Gate 2 approval in Notion writes JSON output file
    - Slack code remains but is dormant when NOTION_TOKEN is set
  </what-built>
  <how-to-verify>
    1. Set environment variables: NOTION_TOKEN and NOTION_DATABASE_ID (create Notion database first with required properties per setup instructions)
    2. Remove or unset SLACK_BOT_TOKEN/SLACK_APP_TOKEN to ensure Slack is not used
    3. Run: `cd /Users/paul/paul/Projects/watchman && python -m watchman.main`
    4. Verify startup logs show:
       - "Notion database schema validated" (or warnings about missing properties)
       - "Review surface: Notion"
       - Scheduled jobs include "deliver-daily-review-notion" and "poll-notion-status"
       - No Slack-related errors
    5. Manually trigger delivery by temporarily modifying the delivery schedule or running:
       `python -c "import asyncio; from watchman.notion.delivery import deliver_daily_review_notion; from pathlib import Path; print(asyncio.run(deliver_daily_review_notion(Path('watchman.db'), Path('src/watchman/config/rubric.yaml'))))"`
    6. Check Notion database — cards should appear with all properties filled in
    7. In Notion, change a card's Review Status from "To Review" to "Approved"
    8. Wait up to 60 seconds — check logs for enrichment trigger
    9. Verify enrichment data appears in the Notion page body
  </how-to-verify>
  <resume-signal>Type "approved" if Notion cards appear correctly and status sync works, or describe issues</resume-signal>
</task>

</tasks>

<verification>
- `python -c "from watchman.notion.client import NotionClient; from watchman.notion.delivery import deliver_daily_review_notion; from watchman.notion.poller import poll_notion_status; print('OK')"` passes
- `python -m watchman.main` starts without errors when NOTION_TOKEN and NOTION_DATABASE_ID are set
- Startup logs show "Review surface: Notion" and scheduled Notion jobs
- Cards appear in Notion database with correct properties after delivery
- Status changes in Notion sync back to SQLite within 60 seconds
</verification>

<success_criteria>
- Notion database rows are created for scored signal cards with all property mappings from the spec
- Review Status changes in Notion (Approved/Rejected/Snoozed) are polled and synced to SQLite review_state
- Approval triggers enrichment pipeline; enrichment results appear as Notion page content
- Gate 2 status changes in Notion sync to SQLite gate2_state; approval writes JSON output
- Watchman starts cleanly with only NOTION_TOKEN + NOTION_DATABASE_ID (no Slack tokens needed)
- Slack code remains intact but dormant — can be re-enabled by unsetting NOTION_TOKEN and setting Slack tokens
</success_criteria>

<output>
After completion, create `.planning/quick/10-watchman-notion-migration-replace-slack-/10-SUMMARY.md`
</output>
