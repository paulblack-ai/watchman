# Phase 1: Collection Pipeline - Research

**Researched:** 2026-02-24
**Domain:** Signal ingestion pipeline (RSS/API/scrape collectors, SQLite storage, deduplication, health monitoring)
**Confidence:** HIGH

## Summary

Phase 1 builds the complete signal ingestion path: a YAML-driven source registry, scheduled collectors (RSS, HTTP/API, scrape), normalization into structured signal cards, two-layer deduplication (URL hash + content fingerprint), per-source health monitoring with Slack DM alerts, and SQLite as the integration bus. The IcebreakerAI tool registry schema must also be encoded as Pydantic models.

The Python ecosystem has mature, stable libraries for every component. feedparser (6.0.x) handles RSS/Atom parsing, httpx (0.28.x) provides async HTTP, trafilatura extracts article content from web pages, APScheduler 3.x manages cron-like scheduling, and Pydantic v2 handles all data validation. SQLite with aiosqlite provides async database access. PyYAML loads the source registry configuration.

**Primary recommendation:** Build a collector abstract base class with RSS/API/Scrape implementations, each writing raw items to SQLite. A separate normalization step converts raw items to signal cards. Deduplication runs as a post-normalization pass. Health monitoring tracks consecutive zero-yield runs per source and alerts via Slack SDK.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single `sources.yaml` file with tier as a field per source (not split by tier)
- Scan frequency expressed as human-readable intervals: `4h`, `12h`, `24h` (not cron expressions)
- Each source has an `enabled: true/false` toggle for pausing without deleting
- Claude curates the 15-20 starter sources based on tier definitions (Tier 1: structured/official AI releases, Tier 2: launch platforms, Tier 3: SaaS changelogs)
- Normalized card fields: title, source name, date, URL, tier, raw summary/description from feed, collector type (rss/api/scrape)
- Raw feed items kept in a separate `raw_items` table after normalization
- Missing publish dates fall back to fetch timestamp
- Collector type tracked on each card
- Two-layer dedup: URL exact hash match + content fingerprint (normalized title similarity >85%) within 7-day window
- Conservative matching to minimize false positives
- Duplicate handling: first card is canonical; later duplicates linked but not surfaced
- Duplicate count ("seen across N sources") visible on canonical card
- Health alerts sent as DM to Paul (not Lauren's review channel)
- Alert threshold: 2 consecutive zero-yield runs per source
- Alert cadence: alert once on first detection, then roll failures into daily digest
- Alerts include suggested action based on source type

### Claude's Discretion
- Exact YAML schema field names and structure
- SQLite table schema design
- Collector abstract class hierarchy
- Normalization algorithm details
- Exact duplicate fingerprint implementation (hashing approach)

### Deferred Ideas (OUT OF SCOPE)
- None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRC-01 | System loads sources from YAML config with type, URL, tier, frequency | PyYAML safe_load + Pydantic validation of source schema |
| SRC-02 | Adding new source requires only YAML entry, zero code changes | Registry pattern: collector factory dispatches by source type field |
| SRC-03 | 15-20 starter sources across Tier 1/2/3 | Curated sources.yaml with tier field; Claude populates during implementation |
| SRC-04 | Health alerts via Slack when source yields zero for 2+ runs | Slack SDK `chat_postMessage` to Paul's DM; health tracker in SQLite |
| COLL-01 | Scheduled collectors on per-source frequencies using APScheduler | APScheduler 3.x IntervalTrigger with human-readable interval parsing |
| COLL-02 | RSS collector parses feeds and writes raw items | feedparser 6.0.x parses RSS/Atom; raw items to `raw_items` table |
| COLL-03 | HTTP/API collector fetches structured responses | httpx AsyncClient for API calls; JSON response parsing |
| COLL-04 | Scrape collector extracts article content | trafilatura for content extraction; httpx for page fetching |
| PROC-01 | Normalize raw items into signal cards | Pydantic SignalCard model; normalization function maps raw fields |
| PROC-02 | Deduplicate by URL hash | SHA-256 of normalized URL; unique constraint on cards table |
| PROC-03 | Deduplicate by content fingerprint (title+date) | Normalized title lowercased+stripped + date; similarity >85% within 7-day window |
| INFRA-01 | SQLite as integration bus | aiosqlite for async access; well-defined schema for raw_items, cards, duplicates |
| INFRA-02 | IcebreakerAI schema as Pydantic models | Placeholder Pydantic models based on expected tool registry fields; flagged as needing real schema |
| INFRA-03 | Single-process cron agent | APScheduler BackgroundScheduler in main process; no distributed setup needed |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedparser | 6.0.11 | RSS/Atom feed parsing | Universal feed parser; handles all RSS/Atom variants; normalizes across formats |
| httpx | 0.28.1 | HTTP client (sync + async) | Modern requests replacement with async support, HTTP/2, connection pooling |
| trafilatura | 2.0.x | Web page content extraction | Outperforms alternatives in benchmarks; used by HuggingFace, IBM, Microsoft Research |
| APScheduler | 3.11.2 | Task scheduling | Production-stable 3.x; interval/cron triggers; job persistence to SQLite |
| pydantic | 2.x | Data validation and models | 5-50x faster than v1 (Rust core); schema generation; used for all data models |
| aiosqlite | 0.20.x | Async SQLite access | Bridges sqlite3 to asyncio; connection pooling; context manager pattern |
| PyYAML | 6.0.x | YAML configuration loading | Standard Python YAML library; safe_load for security |
| slack-sdk | 3.x | Slack API (health alerts) | Official Slack Python SDK; chat_postMessage for DMs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib (stdlib) | - | URL and content hashing | SHA-256 for URL dedup fingerprints |
| difflib (stdlib) | - | Title similarity comparison | SequenceMatcher for >85% title similarity threshold |
| pathlib (stdlib) | - | File path handling | Source config and database paths |
| logging (stdlib) | - | Structured logging | All collector and pipeline logging |
| datetime (stdlib) | - | Date parsing and fallbacks | Publish date normalization, fetch timestamp fallback |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| feedparser | fastfeedparser (Kagi) | 10x faster but newer, less battle-tested; feedparser sufficient for 15-20 sources |
| httpx | aiohttp | aiohttp is async-only; httpx provides both sync+async with simpler API |
| trafilatura | beautifulsoup4 + readability | More manual work; trafilatura combines extraction + metadata in one call |
| aiosqlite | sqlite3 (sync) | Sync sqlite3 blocks the event loop; aiosqlite wraps it safely for async |
| difflib | rapidfuzz | rapidfuzz is faster for bulk fuzzy matching; difflib is stdlib and sufficient for card-level dedup |

**Installation:**
```bash
pip install feedparser httpx trafilatura "APScheduler>=3.10,<4" pydantic aiosqlite pyyaml slack-sdk
```

## Architecture Patterns

### Recommended Project Structure
```
src/watchman/
├── __init__.py
├── main.py              # Entry point, scheduler setup
├── config/
│   ├── __init__.py
│   ├── loader.py        # YAML loading + Pydantic validation
│   └── sources.yaml     # Source registry
├── collectors/
│   ├── __init__.py
│   ├── base.py          # Abstract BaseCollector
│   ├── rss.py           # RSSCollector
│   ├── api.py           # APICollector
│   └── scrape.py        # ScrapeCollector
├── models/
│   ├── __init__.py
│   ├── source.py        # Source Pydantic model
│   ├── raw_item.py      # RawItem model
│   ├── signal_card.py   # SignalCard model
│   └── icebreaker.py    # IcebreakerAI registry schema (Pydantic)
├── processing/
│   ├── __init__.py
│   ├── normalizer.py    # Raw item -> signal card
│   └── deduplicator.py  # URL hash + content fingerprint
├── storage/
│   ├── __init__.py
│   ├── database.py      # SQLite connection, migrations
│   └── repositories.py  # CRUD operations for raw_items, cards
├── health/
│   ├── __init__.py
│   ├── tracker.py       # Per-source health tracking
│   └── alerter.py       # Slack DM alerting
└── scheduler/
    ├── __init__.py
    └── jobs.py           # APScheduler job definitions
```

### Pattern 1: Collector Factory
**What:** Factory pattern dispatches to correct collector based on source type field in YAML.
**When to use:** Every collection cycle -- source type determines which collector runs.
**Example:**
```python
from abc import ABC, abstractmethod
from watchman.models.source import Source
from watchman.models.raw_item import RawItem

class BaseCollector(ABC):
    def __init__(self, source: Source):
        self.source = source

    @abstractmethod
    async def collect(self) -> list[RawItem]:
        """Fetch raw items from the source."""
        ...

COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {}

def register_collector(source_type: str):
    def decorator(cls: type[BaseCollector]):
        COLLECTOR_REGISTRY[source_type] = cls
        return cls
    return decorator

def get_collector(source: Source) -> BaseCollector:
    collector_cls = COLLECTOR_REGISTRY.get(source.type)
    if not collector_cls:
        raise ValueError(f"No collector registered for type: {source.type}")
    return collector_cls(source)
```

### Pattern 2: Repository Pattern for SQLite
**What:** Encapsulate all database operations behind repository classes.
**When to use:** All database reads and writes.
**Example:**
```python
import aiosqlite
from watchman.models.signal_card import SignalCard

class CardRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def insert(self, card: SignalCard) -> SignalCard:
        await self.db.execute(
            "INSERT INTO cards (title, source_name, date, url, tier, summary, collector_type, url_hash, content_fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (card.title, card.source_name, card.date.isoformat(), card.url, card.tier, card.summary, card.collector_type, card.url_hash, card.content_fingerprint)
        )
        await self.db.commit()
        return card

    async def find_by_url_hash(self, url_hash: str) -> SignalCard | None:
        async with self.db.execute(
            "SELECT * FROM cards WHERE url_hash = ?", (url_hash,)
        ) as cursor:
            row = await cursor.fetchone()
            return SignalCard.from_row(row) if row else None
```

### Pattern 3: Two-Layer Deduplication
**What:** First check URL hash (fast, exact), then content fingerprint (slower, fuzzy) within 7-day window.
**When to use:** After normalization, before inserting signal card.
**Example:**
```python
import hashlib
from difflib import SequenceMatcher
from datetime import datetime, timedelta

def url_hash(url: str) -> str:
    normalized = url.strip().lower().rstrip("/")
    return hashlib.sha256(normalized.encode()).hexdigest()

def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

async def is_duplicate(card: SignalCard, repo: CardRepository) -> tuple[bool, SignalCard | None]:
    # Layer 1: Exact URL match
    existing = await repo.find_by_url_hash(card.url_hash)
    if existing:
        return True, existing

    # Layer 2: Content fingerprint (title similarity within 7-day window)
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_cards = await repo.find_since(cutoff)
    for recent in recent_cards:
        if title_similarity(card.title, recent.title) > 0.85:
            if card.date and recent.date and abs((card.date - recent.date).days) <= 1:
                return True, recent

    return False, None
```

### Anti-Patterns to Avoid
- **Polling without backoff:** Always add exponential backoff for failed HTTP requests; sources may rate-limit or temporarily fail
- **Blocking the event loop:** Never use sync sqlite3 calls in async code; always use aiosqlite
- **Storing raw HTML in signal cards:** Keep raw content in `raw_items` table; signal cards hold normalized text only
- **Global state for health tracking:** Use SQLite to persist health counters; in-memory counters reset on process restart

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSS/Atom parsing | Custom XML parser | feedparser | Handles 9+ feed formats, encoding detection, date normalization, malformed feed recovery |
| Web content extraction | BeautifulSoup + manual selectors | trafilatura | Handles boilerplate removal, metadata extraction, multiple fallback algorithms |
| HTTP connection pooling | Manual socket management | httpx AsyncClient | Connection reuse, retry logic, timeout handling, HTTP/2 |
| Job scheduling | Custom sleep loops or cron | APScheduler 3.x | Interval triggers, missed job handling, job persistence, thread safety |
| Data validation | Manual type checking | Pydantic v2 | Automatic type coercion, JSON schema generation, 5-50x faster than v1 |
| YAML loading | Manual file parsing | PyYAML safe_load | Security (no code execution), automatic type conversion, standard format |

**Key insight:** Every component in this pipeline has a mature library. The risk is not in choosing libraries but in gluing them together poorly -- the architecture patterns above prevent that.

## Common Pitfalls

### Pitfall 1: feedparser Date Parsing Inconsistency
**What goes wrong:** feedparser returns dates in different formats depending on feed type; some feeds have no dates at all.
**Why it happens:** RSS/Atom specs are loosely followed; many feeds use non-standard date formats.
**How to avoid:** Always access `entry.published_parsed` (struct_time) or `entry.updated_parsed`; fall back to fetch timestamp when both are None. Convert struct_time to datetime immediately after parsing.
**Warning signs:** `None` date values in signal cards; dates in year 1970 (epoch fallback).

### Pitfall 2: APScheduler 3.x vs 4.x Import Confusion
**What goes wrong:** Installing APScheduler without version pinning gets 4.x pre-release, which has a completely different API.
**Why it happens:** PyPI serves pre-releases when explicitly requested, and some dependency resolvers may pick 4.x.
**How to avoid:** Pin `"APScheduler>=3.10,<4"` in requirements. Use `from apscheduler.schedulers.background import BackgroundScheduler` (3.x path).
**Warning signs:** Import errors on `BackgroundScheduler`; unfamiliar `AsyncScheduler` class.

### Pitfall 3: SQLite Write Contention
**What goes wrong:** Multiple collectors writing simultaneously cause "database is locked" errors.
**Why it happens:** SQLite allows one writer at a time; concurrent async writes from parallel collectors can conflict.
**How to avoid:** Use WAL mode (`PRAGMA journal_mode=WAL`); serialize writes through a single database connection; or use a write queue.
**Warning signs:** `OperationalError: database is locked` in logs.

### Pitfall 4: Trafilatura Timeout on Slow Pages
**What goes wrong:** trafilatura.fetch_url hangs on unresponsive pages, blocking the collector.
**Why it happens:** Default timeout may be too generous; some SaaS changelog pages are slow.
**How to avoid:** Use httpx to fetch the page with explicit timeout, then pass HTML to `trafilatura.extract()` instead of using `trafilatura.fetch_url()`.
**Warning signs:** Collector jobs exceeding expected duration; scheduler job overlap warnings.

### Pitfall 5: Dedup False Positives on Short Titles
**What goes wrong:** Short titles like "Update" or "Release Notes" match at >85% similarity, merging unrelated signals.
**Why it happens:** SequenceMatcher ratio is high for short strings with common words.
**How to avoid:** Set a minimum title length threshold (e.g., 20 chars) before applying title similarity; require source to be different for content-fingerprint dedup (same-source dupes are handled by URL hash).
**Warning signs:** Unrelated signals from different sources being marked as duplicates.

### Pitfall 6: YAML safe_load Security
**What goes wrong:** Using `yaml.load()` instead of `yaml.safe_load()` allows arbitrary code execution from config files.
**Why it happens:** Old tutorials and examples use `yaml.load()`.
**How to avoid:** Always use `yaml.safe_load()`. Validate loaded config through Pydantic model immediately after loading.
**Warning signs:** PyYAML deprecation warning about `Loader` parameter.

## Code Examples

### Source Configuration Schema (Pydantic)
```python
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Literal

class SourceConfig(BaseModel):
    name: str
    type: Literal["rss", "api", "scrape"]
    url: HttpUrl
    tier: Literal[1, 2, 3]
    frequency: str  # "4h", "12h", "24h"
    enabled: bool = True

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        import re
        if not re.match(r"^\d+[hmd]$", v):
            raise ValueError(f"Invalid frequency format: {v}. Use e.g. '4h', '12h', '1d'")
        return v

class SourceRegistry(BaseModel):
    sources: list[SourceConfig]
```

### Loading YAML Config
```python
import yaml
from pathlib import Path
from watchman.models.source import SourceRegistry

def load_sources(config_path: Path) -> SourceRegistry:
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)
    return SourceRegistry.model_validate(raw)
```

### APScheduler 3.x Interval Setup
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import re

def parse_interval(freq: str) -> dict:
    """Parse '4h', '30m', '1d' into APScheduler kwargs."""
    match = re.match(r"^(\d+)([hmd])$", freq)
    if not match:
        raise ValueError(f"Invalid frequency: {freq}")
    value, unit = int(match.group(1)), match.group(2)
    unit_map = {"h": "hours", "m": "minutes", "d": "days"}
    return {unit_map[unit]: value}

def setup_scheduler(sources: list[SourceConfig]) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    for source in sources:
        if not source.enabled:
            continue
        interval_kwargs = parse_interval(source.frequency)
        scheduler.add_job(
            collect_source,
            trigger=IntervalTrigger(**interval_kwargs),
            args=[source],
            id=f"collect-{source.name}",
            replace_existing=True,
        )
    return scheduler
```

### SQLite Schema
```sql
-- Enable WAL mode for concurrent read/write
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS raw_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    collector_type TEXT NOT NULL,
    title TEXT,
    url TEXT,
    summary TEXT,
    published_date TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    raw_data TEXT,  -- JSON blob of full feed entry
    processed BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    date TEXT NOT NULL,
    url TEXT NOT NULL,
    tier INTEGER NOT NULL CHECK(tier IN (1, 2, 3)),
    summary TEXT,
    collector_type TEXT NOT NULL,
    url_hash TEXT NOT NULL UNIQUE,
    content_fingerprint TEXT,
    duplicate_of INTEGER REFERENCES cards(id),
    seen_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS source_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    run_at TEXT NOT NULL DEFAULT (datetime('now')),
    items_found INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    consecutive_zeros INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cards_url_hash ON cards(url_hash);
CREATE INDEX IF NOT EXISTS idx_cards_date ON cards(date);
CREATE INDEX IF NOT EXISTS idx_cards_created_at ON cards(created_at);
CREATE INDEX IF NOT EXISTS idx_raw_items_processed ON raw_items(processed);
CREATE INDEX IF NOT EXISTS idx_source_health_name ON source_health(source_name);
```

### Slack DM Health Alert
```python
from slack_sdk import WebClient

def send_health_alert(
    client: WebClient,
    user_id: str,
    source_name: str,
    source_type: str,
    consecutive_zeros: int,
) -> None:
    action_suggestions = {
        "rss": "Check if the feed URL has changed or the site is down",
        "api": "Check if the API key has expired or the endpoint has moved",
        "scrape": "Check if the page structure or CSS selectors have changed",
    }
    suggestion = action_suggestions.get(source_type, "Check the source configuration")

    client.chat_postMessage(
        channel=user_id,
        text=f"Source health alert: {source_name} has returned zero results for {consecutive_zeros} consecutive runs.\n\nSuggested action: {suggestion}",
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| feedparser + requests (sync) | feedparser + httpx (async) | httpx 0.20+ (2022) | Non-blocking I/O for concurrent source fetching |
| Pydantic v1 (pure Python) | Pydantic v2 (Rust core) | Pydantic 2.0 (2023) | 5-50x validation speed improvement |
| APScheduler 3.x | APScheduler 4.x (pre-release) | Still pre-release (2025) | 4.x not production-ready; stick with 3.x |
| BeautifulSoup scraping | trafilatura extraction | trafilatura 1.0+ (2021) | Academic-grade content extraction with metadata |
| sqlite3 sync | aiosqlite async | aiosqlite 0.17+ (2021) | Safe async SQLite without blocking event loop |

**Deprecated/outdated:**
- APScheduler 4.x: Pre-release, backwards-incompatible API, not for production use
- feedparser `parse(url)` with built-in HTTP: Use httpx to fetch, then feedparser to parse the content
- `yaml.load()` without Loader: Security hazard, always use `yaml.safe_load()`

## Open Questions

1. **IcebreakerAI Tool Registry Schema**
   - What we know: Schema must be encoded as Pydantic models (INFRA-02); used for enrichment validation in Phase 3
   - What's unclear: The actual schema fields, structure, and format -- marked as a blocker in STATE.md
   - Recommendation: Create placeholder Pydantic models with expected fields (name, description, capabilities, pricing, api_surface, integration_hooks). Flag for update when real schema is obtained. This does not block Phase 1 execution.

2. **Starter Source Selection**
   - What we know: 15-20 sources across Tier 1 (official AI releases), Tier 2 (launch platforms), Tier 3 (SaaS changelogs)
   - What's unclear: Exact sources to include
   - Recommendation: Claude curates during implementation (per CONTEXT.md). Suggested starting points:
     - Tier 1: OpenAI blog RSS, Anthropic blog RSS, Google AI blog, Meta AI blog, HuggingFace blog
     - Tier 2: Product Hunt AI category, Hacker News (Algolia API), GitHub Trending, BetaList
     - Tier 3: Notion changelog, Figma changelog, Linear changelog, Vercel changelog, Supabase changelog

3. **Async vs Sync Architecture**
   - What we know: httpx supports both; aiosqlite requires async; APScheduler 3.x BackgroundScheduler is thread-based
   - What's unclear: Whether to go fully async or use sync collectors with async DB
   - Recommendation: Use sync collectors called from APScheduler's thread pool (simplest), with aiosqlite wrapped for sync access via `asyncio.run()` inside each job. Full async is unnecessary for 15-20 sources running every 4-24 hours. Keep the option to migrate to async if volume grows.

## Sources

### Primary (HIGH confidence)
- [feedparser PyPI](https://pypi.org/project/feedparser/) - version 6.0.11, feature set
- [httpx official docs](https://www.python-httpx.org/) - version 0.28.1, async/sync API
- [trafilatura GitHub](https://github.com/adbar/trafilatura) - content extraction capabilities
- [APScheduler 3.x docs](https://apscheduler.readthedocs.io/en/3.x/) - version 3.11.2, scheduler types
- [Pydantic docs](https://docs.pydantic.dev/latest/) - v2 validation, model_validate
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) - async SQLite bridge
- [Slack SDK docs](https://docs.slack.dev/tools/python-slack-sdk/web/) - chat_postMessage for DMs

### Secondary (MEDIUM confidence)
- [trafilatura benchmarks](https://www.blog.brightcoding.dev/2025/10/03/trafilatura-the-python-library-that-turns-messy-html-into-clean-research-ready-text/) - performance claims verified by multiple sources
- [PyYAML safe_load best practices](https://betterstack.com/community/guides/scaling-python/yaml-files-in-python/) - security guidance

### Tertiary (LOW confidence)
- IcebreakerAI tool registry schema: No public documentation found. Placeholder models recommended.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries are well-established, actively maintained, widely used
- Architecture: HIGH - patterns are standard Python project structure; collector/repository/factory are well-proven
- Pitfalls: HIGH - documented in official docs and community experience; SQLite WAL mode, APScheduler version pinning, feedparser date handling are well-known issues

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain; libraries change slowly)
