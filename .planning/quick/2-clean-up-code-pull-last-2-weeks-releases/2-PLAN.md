---
phase: quick-02
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/scripts/reset_and_collect.py
  - src/watchman/collectors/base.py
autonomous: false

must_haves:
  truths:
    - "Database is empty of all old testing data (raw_items, cards, source_health all have 0 rows)"
    - "A fresh collection runs against all enabled sources, collecting only items published in the last 2 weeks"
    - "Collected items are normalized into signal cards and scored"
    - "Scored cards are delivered to the fresh Slack channel (C0AJ05BRVLY)"
  artifacts:
    - path: "src/watchman/scripts/reset_and_collect.py"
      provides: "One-shot script: wipe DB, collect, normalize, score, deliver"
      contains: "async def run_full_pipeline"
    - path: "watchman.db"
      provides: "Fresh database with only recent (last 2 weeks) signal cards"
  key_links:
    - from: "src/watchman/scripts/reset_and_collect.py"
      to: "src/watchman/collectors/base.py"
      via: "Calls collector.run() for each enabled source"
      pattern: "collector.run"
    - from: "src/watchman/scripts/reset_and_collect.py"
      to: "src/watchman/processing/normalizer.py"
      via: "Calls process_unprocessed to create signal cards"
      pattern: "process_unprocessed"
    - from: "src/watchman/scripts/reset_and_collect.py"
      to: "src/watchman/slack/delivery.py"
      via: "Calls deliver_daily_review to post cards to Slack"
      pattern: "deliver_daily_review"
---

<objective>
Wipe the database of all old testing data, run a one-time collection from all sources filtering to only the last 2 weeks of releases, normalize/score/deliver those cards to the fresh Slack channel.

Purpose: The existing DB has 1669 stale testing cards dating back to year 2000. The system is meant to monitor NEW releases. This resets everything and does a clean initial pull of recent content to the new Slack channel.
Output: Clean database with only last-2-weeks signal cards, delivered to Slack for review.
</objective>

<execution_context>
@/Users/salfaqih/.claude/get-shit-done/workflows/execute-plan.md
@/Users/salfaqih/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/watchman/main.py
@src/watchman/collectors/base.py
@src/watchman/storage/database.py
@src/watchman/storage/repositories.py
@src/watchman/processing/normalizer.py
@src/watchman/scoring/scorer.py
@src/watchman/slack/delivery.py
@src/watchman/config/sources.yaml
@.env
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create one-shot reset-and-collect script with 2-week date filter</name>
  <files>src/watchman/scripts/__init__.py, src/watchman/scripts/reset_and_collect.py, src/watchman/collectors/base.py</files>
  <action>
**1. Create `src/watchman/scripts/__init__.py`** (empty file for package).

**2. Add date filtering to BaseCollector.run()** in `src/watchman/collectors/base.py`:

Modify the `run()` method to accept an optional `max_age_days: int | None = None` parameter. When provided, after `collect()` returns items, filter out any item whose `published_date` is older than `max_age_days` days ago. Log how many items were filtered. This keeps the filter at the base class level so all collector types (rss, api, scrape) benefit.

```python
async def run(self, max_age_days: int | None = None) -> int:
    """Execute collection: fetch items, optionally filter by age, write to database, return count."""
    try:
        items = await self.collect()
        if not items:
            logger.info("Source '%s' returned 0 items", self.source.name)
            return 0

        # Filter by age if specified
        if max_age_days is not None:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            original_count = len(items)
            items = [
                item for item in items
                if item.published_date and item.published_date.replace(tzinfo=timezone.utc if item.published_date.tzinfo is None else item.published_date.tzinfo) >= cutoff
            ]
            filtered = original_count - len(items)
            if filtered > 0:
                logger.info(
                    "Source '%s': filtered %d items older than %d days (%d remaining)",
                    self.source.name, filtered, max_age_days, len(items),
                )
            if not items:
                return 0

        async with get_connection(self.db_path) as db:
            repo = RawItemRepository(db)
            for item in items:
                await repo.insert(item)

        logger.info("Source '%s' collected %d items", self.source.name, len(items))
        return len(items)

    except Exception:
        logger.exception("Error collecting from source '%s'", self.source.name)
        return 0
```

The existing `run()` signature had no `max_age_days` so the default `None` is fully backward-compatible -- the scheduler calls `collector.run()` without arguments and behavior is unchanged.

**3. Create `src/watchman/scripts/reset_and_collect.py`**:

A standalone script that:
1. Loads .env via dotenv
2. Wipes all data from raw_items, cards, source_health tables (DELETE FROM, not DROP -- preserves schema)
3. Re-initializes DB (ensures schema is current with all migrations)
4. Runs collection for all enabled sources with `max_age_days=14`
5. Runs normalizer (process_unprocessed)
6. Runs scoring (score_unscored_cards)
7. Runs delivery (deliver_daily_review) to post to Slack
8. Prints summary stats

```python
"""One-shot script: wipe DB, collect last 2 weeks, normalize, score, deliver to Slack."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


async def run_full_pipeline() -> None:
    """Execute the full pipeline: wipe -> collect -> normalize -> score -> deliver."""
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")

    from watchman.collectors import get_collector
    from watchman.config.loader import get_enabled_sources, load_sources
    from watchman.processing.normalizer import process_unprocessed
    from watchman.scoring.scorer import score_unscored_cards
    from watchman.slack.delivery import deliver_daily_review
    from watchman.storage.database import get_connection, init_db

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("reset_and_collect")

    db_path = Path("watchman.db")
    config_path = Path("src/watchman/config/sources.yaml")
    rubric_path = Path("src/watchman/config/rubric.yaml")

    # Step 1: Wipe all data
    logger.info("=== Step 1: Wiping all existing data ===")
    async with get_connection(db_path) as db:
        await db.execute("DELETE FROM cards")
        await db.execute("DELETE FROM raw_items")
        await db.execute("DELETE FROM source_health")
        await db.commit()
    logger.info("All tables cleared")

    # Step 2: Re-init DB (ensures schema is current)
    logger.info("=== Step 2: Re-initializing database schema ===")
    await init_db(db_path)
    logger.info("Schema verified")

    # Step 3: Collect from all enabled sources (last 2 weeks only)
    logger.info("=== Step 3: Collecting from all sources (last 14 days) ===")
    registry = load_sources(config_path)
    enabled = get_enabled_sources(registry)
    total_items = 0

    for source in enabled:
        try:
            collector = get_collector(source, db_path)
            count = await collector.run(max_age_days=14)
            total_items += count
            logger.info("  %s: %d items", source.name, count)
        except Exception:
            logger.exception("  %s: FAILED", source.name)

    logger.info("Collection complete: %d total items from %d sources", total_items, len(enabled))

    # Step 4: Normalize raw items into signal cards
    logger.info("=== Step 4: Normalizing raw items into signal cards ===")
    source_configs = {s.name: s for s in registry.sources}
    new_cards = await process_unprocessed(db_path, source_configs)
    logger.info("Normalization complete: %d new cards", new_cards)

    # Step 5: Score all cards
    logger.info("=== Step 5: Scoring signal cards ===")
    scored = await score_unscored_cards(db_path, rubric_path)
    logger.info("Scoring complete: %d cards scored", scored)

    # Step 6: Deliver to Slack
    logger.info("=== Step 6: Delivering to Slack ===")
    try:
        delivered = await deliver_daily_review(db_path, rubric_path)
        logger.info("Delivery complete: %d cards sent to Slack", delivered)
    except Exception:
        logger.exception("Delivery failed (check SLACK_BOT_TOKEN and SLACK_CHANNEL_ID)")

    # Summary
    logger.info("=== PIPELINE COMPLETE ===")
    logger.info("  Raw items collected: %d", total_items)
    logger.info("  Signal cards created: %d", new_cards)
    logger.info("  Cards scored: %d", scored)


if __name__ == "__main__":
    asyncio.run(run_full_pipeline())
```

Key design decisions:
- Uses DELETE FROM (not DROP TABLE) to preserve schema -- avoids needing to recreate tables
- Calls `init_db` after wipe to ensure all migrations are applied (idempotent)
- Passes `max_age_days=14` to each collector's `run()` to filter at collection time
- Sequential source collection (not parallel) to avoid overwhelming APIs
- Loads .env explicitly so it works standalone outside the scheduler
- The delivery step uses `find_top_scored_today` which filters by `date(created_at) = date('now')` -- since we just created them, they qualify
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/projects/watchman && python -c "
# Verify script exists and is importable
import ast
with open('src/watchman/scripts/reset_and_collect.py') as f:
    tree = ast.parse(f.read())
funcs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
assert 'run_full_pipeline' in funcs, 'Missing run_full_pipeline'
print('Script structure OK')

# Verify BaseCollector.run accepts max_age_days
import inspect
# Need to check the source directly since importing triggers collector registration
with open('src/watchman/collectors/base.py') as f:
    content = f.read()
assert 'max_age_days' in content, 'Missing max_age_days parameter in base.py'
print('BaseCollector.run has max_age_days parameter OK')
print('ALL CHECKS PASSED')
"</automated>
  </verify>
  <done>Reset-and-collect script exists with full pipeline (wipe, collect with 14-day filter, normalize, score, deliver). BaseCollector.run() accepts optional max_age_days for date filtering.</done>
</task>

<task type="auto">
  <name>Task 2: Execute the reset-and-collect pipeline</name>
  <files>watchman.db</files>
  <action>
Run the reset-and-collect script from the project root:

```bash
cd /Users/salfaqih/paul/projects/watchman && python src/watchman/scripts/reset_and_collect.py
```

This will:
1. Wipe all 1669 stale cards and raw items from the DB
2. Collect from all 18 enabled sources, keeping only items from the last 14 days
3. Normalize raw items into signal cards with deduplication
4. Score all cards via OpenRouter LLM
5. Deliver the top-scored cards to Slack channel C0AJ05BRVLY

After execution, verify the database state:

```python
import sqlite3
db = sqlite3.connect('watchman.db')
raw = db.execute('SELECT COUNT(*) FROM raw_items').fetchone()[0]
cards = db.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
health = db.execute('SELECT COUNT(*) FROM source_health').fetchone()[0]
date_range = db.execute('SELECT MIN(date), MAX(date) FROM cards').fetchone()
scored = db.execute('SELECT COUNT(*) FROM cards WHERE relevance_score IS NOT NULL').fetchone()[0]
print(f'Raw items: {raw}')
print(f'Cards: {cards}')
print(f'Source health: {health}')
print(f'Date range: {date_range}')
print(f'Scored: {scored}')
db.close()
```

Expected: All cards should have dates within the last 2 weeks. No cards from 2000 or other stale dates. Some sources may return 0 items (scrape sources often return a single page rather than individual items with dates -- this is expected).

If the script fails on specific sources (e.g., scrape sources timing out, API rate limits), that is acceptable -- the pipeline should continue past individual source failures due to the try/except per source. Log the failures and proceed.

If Slack delivery fails (e.g., rate limits for too many messages), note this but consider the DB reset and collection successful.
  </action>
  <verify>
    <automated>cd /Users/salfaqih/paul/projects/watchman && python -c "
import sqlite3
db = sqlite3.connect('watchman.db')

# Verify old data is gone (no dates before 2026-02-11)
old = db.execute(\"SELECT COUNT(*) FROM cards WHERE date < '2026-02-11'\").fetchone()[0]
total = db.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
scored = db.execute('SELECT COUNT(*) FROM cards WHERE relevance_score IS NOT NULL').fetchone()[0]

print(f'Total cards: {total}')
print(f'Old cards (before 2 weeks ago): {old}')
print(f'Scored cards: {scored}')

assert old == 0 or total == 0, f'Found {old} cards older than 2 weeks -- filter did not work'
print('Date filter verified: no stale cards')
print('ALL CHECKS PASSED')
"</automated>
  </verify>
  <done>Database contains only fresh signal cards from the last 2 weeks. All old testing data is cleared. Cards are scored and delivered to the fresh Slack channel.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Verify Slack delivery and card quality</name>
  <action>
Human verifies that signal cards were delivered to the fresh Slack channel and contain recent, relevant content.

What was built: Full pipeline reset -- wiped old DB data, collected releases from last 2 weeks across all 18 sources, normalized into signal cards, scored via LLM, and delivered top cards to the Slack channel.

How to verify:
1. Open Slack and navigate to the Watchman channel (the one with the fresh channel ID C0AJ05BRVLY)
2. Verify that signal cards have been posted with approve/reject/snooze buttons
3. Verify the cards are recent (last 2 weeks of content, not old testing data)
4. Try approving or rejecting one card to confirm the action handlers work
5. Optionally run: python -c "import sqlite3; db=sqlite3.connect('watchman.db'); print('Cards:', db.execute('SELECT COUNT(*) FROM cards').fetchone()[0]); print('Scored:', db.execute('SELECT COUNT(*) FROM cards WHERE relevance_score IS NOT NULL').fetchone()[0])"

Resume signal: Type "approved" if cards appear correctly in Slack, or describe any issues.
  </action>
  <verify>Human confirms cards appear in Slack with recent dates and working action buttons</verify>
  <done>Signal cards from the last 2 weeks are delivered to Slack and verified by human</done>
</task>

</tasks>

<verification>
- All old testing data wiped (0 cards with dates before 2 weeks ago)
- Fresh collection completed with 14-day date filter
- Signal cards normalized and deduplicated
- Cards scored via OpenRouter LLM
- Top cards delivered to fresh Slack channel C0AJ05BRVLY
- BaseCollector.run() backward-compatible (scheduler still works without max_age_days)
</verification>

<success_criteria>
- Database has only cards from the last 2 weeks (no stale testing data)
- Cards are scored and delivered to Slack
- Slack channel shows recent AI releases/updates with review buttons
- The regular scheduler can still run normally after this one-time reset
</success_criteria>

<output>
After completion, create `.planning/quick/2-clean-up-code-pull-last-2-weeks-releases/2-SUMMARY.md`
</output>
