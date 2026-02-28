---
phase: quick-6
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/watchman/config/sources.yaml
  - src/watchman/collectors/jina.py
  - src/watchman/collectors/base.py
  - src/watchman/models/raw_item.py
autonomous: false
requirements: [FIX-URLS, FIX-SCRAPE, JINA-MARKDOWN]

must_haves:
  truths:
    - "All 8 broken sources return >0 items or are disabled with documented reason"
    - "Scrape sources that block direct HTTP requests use r.jina.ai markdown fallback"
    - "RSS sources point to valid, responding feed URLs"
  artifacts:
    - path: "src/watchman/collectors/jina.py"
      provides: "Jina markdown collector using r.jina.ai"
    - path: "src/watchman/config/sources.yaml"
      provides: "Updated source URLs and types"
  key_links:
    - from: "src/watchman/collectors/jina.py"
      to: "src/watchman/collectors/base.py"
      via: "register_collector decorator"
      pattern: "register_collector"
---

<objective>
Fix all 8 broken source URLs and crawling methods so Watchman collects signals from every enabled source.

Purpose: Half the sources are returning 0 items or HTTP errors, making Watchman blind to Anthropic, Meta, Product Hunt, GitHub Trending, BetaList, VentureBeat, Linear, and Stripe signals.

Output: Updated sources.yaml with working URLs, a new Jina markdown collector for sites that block scrapers, and verified collection from all sources.
</objective>

<execution_context>
@/Users/salfaqih/.claude/get-shit-done/workflows/execute-plan.md
@/Users/salfaqih/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/watchman/config/sources.yaml
@src/watchman/collectors/base.py
@src/watchman/collectors/rss.py
@src/watchman/collectors/scrape.py
@src/watchman/collectors/api.py
@src/watchman/models/raw_item.py

<interfaces>
From src/watchman/collectors/base.py:
```python
COLLECTOR_REGISTRY: dict[str, type["BaseCollector"]] = {}

def register_collector(source_type: str):
    """Decorator to register a collector class for a source type."""

class BaseCollector(ABC):
    def __init__(self, source: SourceConfig, db_path: Path) -> None: ...
    async def collect(self) -> list[RawItem]: ...
    async def run(self, max_age_days: int | None = None) -> int: ...
```

From src/watchman/models/raw_item.py:
```python
class RawItem(BaseModel):
    collector_type: Literal["rss", "api", "scrape"]  # NOTE: must add "jina" here
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create Jina markdown collector and fix source URLs</name>
  <files>
    src/watchman/collectors/jina.py
    src/watchman/models/raw_item.py
    src/watchman/config/sources.yaml
    src/watchman/collectors/base.py
  </files>
  <action>
  **1. Create `src/watchman/collectors/jina.py`** — a new collector type "jina" that:
  - Extends BaseCollector, uses `@register_collector("jina")`
  - Fetches `https://r.jina.ai/{source_url}` with httpx (timeout 60s, follow_redirects=True)
  - Sets `Accept: text/markdown` header and `User-Agent: Watchman/1.0`
  - The response is markdown text — parse it to extract individual entries
  - For changelog pages: split on markdown headings (##, ###) — each heading becomes one RawItem with the heading as title and the content below as summary
  - For blog listing pages: look for markdown links `[title](url)` with surrounding text as summary — each link becomes one RawItem
  - Falls back to returning a single RawItem with the full page content if no structure detected (same as current scrape behavior)
  - Uses `collector_type="jina"` in RawItem

  **2. Update `src/watchman/models/raw_item.py`** — add "jina" to the `Literal` type:
  ```python
  collector_type: Literal["rss", "api", "scrape", "jina"]
  ```

  **3. Register the jina collector** — ensure it is imported in the collector package `__init__.py` (check if one exists, if not, ensure `jina.py` is imported where `rss.py`, `scrape.py`, `api.py` are imported — likely in `src/watchman/collectors/__init__.py` or wherever the registry is populated).

  **4. Update `src/watchman/config/sources.yaml`** with these changes:

  **RSS fixes:**
  - Anthropic Blog: Try `https://www.anthropic.com/feed.xml` (common alternate path). If that doesn't work during testing, switch to type: jina with url: `https://www.anthropic.com/research` (their blog listing page)
  - Meta AI Blog: Try `https://ai.meta.com/blog/feed/` or `https://about.fb.com/news/category/ai/feed/`. If neither works, switch to type: jina with url: `https://ai.meta.com/blog/`
  - VentureBeat AI: Try `https://venturebeat.com/feed/` (main feed, includes AI). If that works, keep it. Otherwise disable with `enabled: false` and add comment

  **Scrape-to-Jina conversions (sites that block direct scraping):**
  - Product Hunt AI: Change type to `jina` (Product Hunt returns 403 to scrapers, Jina can render it)
  - GitHub Trending: Change type to `jina` (JavaScript-rendered page, trafilatura can't extract)
  - BetaList: Change type to `jina`
  - Linear Changelog: Change type to `jina`
  - Stripe Changelog: Change type to `jina` with url `https://stripe.com/docs/changelog` (the actual changelog URL, not the blog path)
  </action>
  <verify>
  Run: `cd /Users/salfaqih/paul/projects/watchman && PYTHONPATH=src python -c "from watchman.collectors.jina import JinaCollector; print('JinaCollector imported OK')"`
  Run: `cd /Users/salfaqih/paul/projects/watchman && PYTHONPATH=src python -c "from watchman.collectors.base import COLLECTOR_REGISTRY; print('Registry:', list(COLLECTOR_REGISTRY.keys()))"` — must show 'jina' in registry
  </verify>
  <done>
  - JinaCollector registered and importable
  - RawItem model accepts "jina" collector_type
  - sources.yaml updated with fixed URLs and type changes
  - All collector types registered: rss, api, scrape, jina
  </done>
</task>

<task type="auto">
  <name>Task 2: Test each source and fix issues iteratively</name>
  <files>
    src/watchman/config/sources.yaml
    src/watchman/collectors/jina.py
  </files>
  <action>
  Write and run a test script (inline, not saved to file) that tests each broken source individually:

  ```python
  import asyncio
  from pathlib import Path
  from watchman.config.loader import load_sources, get_enabled_sources
  from watchman.collectors.base import get_collector

  BROKEN_SOURCES = [
      "Anthropic Blog", "Meta AI Blog", "Product Hunt AI",
      "GitHub Trending", "BetaList", "VentureBeat AI",
      "Linear Changelog", "Stripe Changelog"
  ]

  async def test_source(source, db_path):
      collector = get_collector(source, db_path)
      try:
          items = await collector.collect()
          return source.name, len(items), "OK"
      except Exception as e:
          return source.name, 0, str(e)[:100]

  async def main():
      registry = load_sources(Path("src/watchman/config/sources.yaml"))
      sources = get_enabled_sources(registry)
      db_path = Path("/tmp/test_watchman.db")
      for source in sources:
          if source.name in BROKEN_SOURCES:
              name, count, status = await test_source(source, db_path)
              print(f"{name}: {count} items — {status}")

  asyncio.run(main())
  ```

  For each source that still fails:
  - **RSS 404s**: Try alternate feed URLs by fetching the site homepage and looking for `<link rel="alternate" type="application/rss+xml">` in the HTML. Update sources.yaml with working URL
  - **Jina returning 0 items**: Inspect the raw markdown response from r.jina.ai, adjust parsing logic in jina.py if the structure differs from expected format
  - **403/blocking**: Add `X-No-Cache: true` header to Jina requests, or try `s.jina.ai` (search endpoint) as alternative
  - If a source is truly inaccessible (e.g., Product Hunt requires auth), set `enabled: false` in sources.yaml with a YAML comment explaining why

  Re-run the test after each fix until all sources either return >0 items or are explicitly disabled with reason.
  </action>
  <verify>
  Run the test script above — all 8 sources should show either items > 0 with "OK" status, or be disabled in sources.yaml with a comment explaining why.
  </verify>
  <done>
  - Every previously-broken source either returns items or is explicitly disabled with documented reason
  - No HTTP 404 or 403 errors from enabled sources
  - sources.yaml reflects final working state
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Verify all sources collect successfully</name>
  <what-built>Fixed all broken source URLs and added Jina markdown collector. Each source has been individually tested.</what-built>
  <how-to-verify>
    1. Review the test results printed by Task 2 — each source should show item count and status
    2. Run a full collection cycle to confirm end-to-end:
       ```
       cd /Users/salfaqih/paul/projects/watchman
       PYTHONPATH=src python -c "
       import asyncio
       from pathlib import Path
       from watchman.config.loader import load_sources, get_enabled_sources
       from watchman.collectors.base import get_collector
       from watchman.storage.database import init_db

       async def main():
           db = Path('/tmp/verify_watchman.db')
           await init_db(db)
           registry = load_sources(Path('src/watchman/config/sources.yaml'))
           for s in get_enabled_sources(registry):
               c = get_collector(s, db)
               n = await c.run(max_age_days=14)
               print(f'{s.name}: {n} items')

       asyncio.run(main())
       "
       ```
    3. Confirm all enabled sources show > 0 items
    4. Check any disabled sources have reasonable justification in YAML comments
  </how-to-verify>
  <resume-signal>Type "approved" if all sources look good, or list any sources that still need attention</resume-signal>
</task>

</tasks>

<verification>
- All 17 sources in sources.yaml either return items or are disabled with comment
- JinaCollector handles both changelog and blog listing page formats
- No regression in previously-working sources (OpenAI, Google AI, HN, TechCrunch, Notion, Figma, Vercel, Supabase, Crescendo)
</verification>

<success_criteria>
- 8 previously-broken sources fixed: each returns >0 items or is explicitly disabled with documented reason
- JinaCollector created and registered as new collector type
- RawItem model updated to accept "jina" collector_type
- sources.yaml updated with correct URLs and types
- Human verified the collection results
</success_criteria>

<output>
After completion, create `.planning/quick/6-fix-broken-source-urls-and-crawling-meth/6-SUMMARY.md`
</output>
