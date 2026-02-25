# Architecture Research

**Domain:** AI ecosystem monitoring / intelligence pipeline with human-in-the-loop review
**Researched:** 2026-02-24
**Confidence:** HIGH (pattern is well-established; adapted from medallion ETL + HITL agent patterns)

## Standard Architecture

### System Overview

The standard architecture for this class of system is a **staged pipeline with a human gate**. Raw signals flow in, get progressively refined, and a human decides what graduates to enrichment and output.

This maps cleanly to the medallion architecture (Bronze → Silver → Gold) widely used in data pipelines, adapted for a cron-driven, single-process, local service.

```
┌──────────────────────────────────────────────────────────────────┐
│                        COLLECTION LAYER                          │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ RSS/Atom │  │ JSON API │  │  Scraper │  │  Future  │         │
│  │Collector │  │Collector │  │Collector │  │Collector │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       └─────────────┴─────────────┴─────────────┘               │
│                            ↓                                     │
│                   Source Registry (config.yaml)                  │
│                   Scheduler (APScheduler/cron)                   │
├──────────────────────────────────────────────────────────────────┤
│                      NORMALIZATION LAYER                         │
│                                                                  │
│  Raw items → Normalizer → Signal Cards (title, url, source,      │
│              Deduplicator    date, summary, raw_text)            │
│              (hash + semantic)                                   │
├──────────────────────────────────────────────────────────────────┤
│                       SCORING LAYER                              │
│                                                                  │
│  Signal Cards → LLM Scorer (Haiku) → Scored Cards               │
│                 (taxonomy fit, novelty,  (score 0-100,           │
│                  traction, credibility)   rationale, tier)       │
├──────────────────────────────────────────────────────────────────┤
│                      REVIEW LAYER (HITL)                         │
│                                                                  │
│  Scored Cards → Slack Bot → Lauren's Queue                       │
│  (above threshold)          [approve / reject / snooze]         │
│                                    ↓ approved                    │
├──────────────────────────────────────────────────────────────────┤
│                     ENRICHMENT LAYER                             │
│                                                                  │
│  Approved Signal → Enricher → Enriched Card                      │
│                    (LLM + web)  (capabilities, pricing,          │
│                                  API surface, integrations)      │
│                                    ↓                             │
│                 Schema Generator → Draft Tool Entry              │
│                 (structured output  (IcebreakerAI format)        │
│                  from Haiku/Sonnet)                              │
├──────────────────────────────────────────────────────────────────┤
│                   SECOND GATE + OUTPUT LAYER                     │
│                                                                  │
│  Draft Entry → Slack Bot (Gate 2) → Approved Entry              │
│                Lauren approves →    Emitted to output/           │
│                                     (file drop for now)          │
├──────────────────────────────────────────────────────────────────┤
│                       PERSISTENCE LAYER                          │
│                                                                  │
│  ┌─────────────────┐  ┌────────────────┐  ┌─────────────────┐   │
│  │  signals.db     │  │  sources.yaml  │  │  output/        │   │
│  │  (SQLite)       │  │  (config)      │  │  (tool entries) │   │
│  └─────────────────┘  └────────────────┘  └─────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| Source Registry | Declares sources, scan frequency, tier, collector type | Scheduler reads it; Collectors are instantiated from it |
| Scheduler | Triggers collectors on per-source cadence | Reads Source Registry; dispatches Collectors |
| Collectors (RSS/API/Scrape) | Fetch raw items from external sources | Write raw rows to SQLite `raw_items` table |
| Normalizer | Converts raw items into uniform Signal Card schema | Reads `raw_items`; writes `signal_cards` table |
| Deduplicator | Prevents duplicate signals (URL hash + content similarity) | Reads/writes `signal_cards`; marks duplicates |
| LLM Scorer | Classifies each card against relevance rubric | Reads un-scored `signal_cards`; writes scores back; calls Haiku API |
| Review Queue Manager | Surfaces scored cards to Slack; handles approve/reject/snooze | Reads scored cards; writes review decisions; sends Slack messages |
| Slack Bot | Interactive interface for Lauren's review queue | Receives Slack interactions; calls Review Queue Manager |
| Enricher | Deep-dives approved signals (capabilities, pricing, API) | Reads approved `signal_cards`; calls LLM + optional web fetch |
| Schema Generator | Produces structured IcebreakerAI-compatible tool entries | Reads enriched cards; calls Sonnet; writes draft entries |
| Output Emitter | Writes approved tool entries to output directory | Reads second-gate-approved entries; writes JSON files |

## Recommended Project Structure

```
watchman/
├── config/
│   ├── sources.yaml          # Source registry — tier, URL, type, frequency
│   └── rubric.yaml           # Scoring rubric — criteria and weights
├── watchman/
│   ├── __init__.py
│   ├── main.py               # Entry point — boots scheduler and Slack bot
│   ├── scheduler.py          # APScheduler setup; dispatches collectors by source config
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py           # BaseCollector abstract class
│   │   ├── rss.py            # RSS/Atom via feedparser
│   │   ├── api.py            # JSON API sources (e.g. Product Hunt, HN Algolia)
│   │   └── scraper.py        # HTML scrape sources via httpx + BeautifulSoup
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── normalizer.py     # Raw item → Signal Card schema
│   │   ├── deduplicator.py   # URL hash + semantic fingerprint check
│   │   ├── scorer.py         # LLM scoring via rubric (Haiku)
│   │   ├── enricher.py       # Enrichment on approval (Haiku/Sonnet)
│   │   └── schema_gen.py     # IcebreakerAI tool entry generation
│   ├── review/
│   │   ├── __init__.py
│   │   ├── queue.py          # Review queue state management
│   │   └── slack_bot.py      # Bolt-based Slack bot; blocks, interactions
│   ├── output/
│   │   └── emitter.py        # Writes approved entries to output/
│   └── db/
│       ├── __init__.py
│       ├── models.py         # SQLAlchemy models (raw_items, signal_cards, etc.)
│       └── migrations/       # Alembic migrations
├── output/                   # Emitted tool entries (JSON)
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── .env.example
└── README.md
```

### Structure Rationale

- **config/:** Source registry and rubric live outside `watchman/` package so they can be edited without touching code. Adding a source = adding a YAML entry.
- **collectors/:** One file per collector type. `BaseCollector` defines the interface (`fetch() -> list[RawItem]`). New source types are new files, not modifications to existing ones.
- **pipeline/:** Each stage is a standalone module. Stages communicate through the database, not direct function calls — this makes each stage independently runnable and testable.
- **review/:** Slack bot and queue state are colocated. The bot is thin — it delegates all state changes to `queue.py`.
- **db/:** Centralized persistence. All stages read/write through SQLAlchemy models. No stage owns the DB; the DB is the integration bus.

## Architectural Patterns

### Pattern 1: Database as Integration Bus

**What:** Each pipeline stage reads from and writes to SQLite. No stage calls another stage directly. The scheduler triggers stages; stages communicate through shared state in the DB.

**When to use:** Small single-process services where simplicity beats throughput. Eliminates message queue overhead, makes state visible and inspectable.

**Trade-offs:** Simple to debug (query the DB to see state); harder to scale horizontally (but that's not a requirement here). Works well for cron cadences.

**Example:**
```python
# Scorer reads un-scored cards, writes scores back — no coupling to Normalizer
def run_scoring_pass(db: Session) -> int:
    unscored = db.query(SignalCard).filter(
        SignalCard.score.is_(None),
        SignalCard.is_duplicate == False
    ).all()
    for card in unscored:
        result = score_card(card)
        card.score = result.score
        card.score_rationale = result.rationale
        card.scored_at = datetime.utcnow()
    db.commit()
    return len(unscored)
```

### Pattern 2: BaseCollector Protocol

**What:** All collectors implement the same interface. Scheduler instantiates the correct collector class based on `type` field in `sources.yaml`. Adding a new source type = new class, zero changes to scheduler.

**When to use:** When source diversity is expected to grow. Enforces consistency without over-engineering.

**Trade-offs:** Light overhead for very simple sources; but the consistency payoff is worth it from day 1.

**Example:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RawItem:
    source_id: str
    url: str
    title: str
    published_at: datetime
    raw_content: str

class BaseCollector(ABC):
    def __init__(self, source_config: dict):
        self.source_id = source_config["id"]
        self.config = source_config

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Fetch raw items from source. Must be idempotent."""
        ...
```

### Pattern 3: Two-Gate HITL Review

**What:** Human approval is required twice — once to approve a signal for enrichment, once to approve the generated tool entry for output. The two gates serve different purposes: Gate 1 is a relevance filter (cheap), Gate 2 is a quality gate (after LLM enrichment cost is sunk).

**When to use:** Whenever LLM costs are non-trivial and output quality matters. Avoids enriching signals that would be rejected anyway.

**Trade-offs:** Adds latency between collection and output. Acceptable because this is not a real-time system.

## Data Flow

### Primary Flow: Collection to Output

```
[Cron / APScheduler trigger]
        ↓
[Collector.fetch()] → RawItem list
        ↓
[Normalizer] → SignalCard (title, url, source, date, summary)
        ↓
[Deduplicator] → mark duplicate=True if seen (URL hash first, semantic fallback)
        ↓
[LLM Scorer] → score 0-100, rationale, taxonomy tags
        ↓  (only cards above threshold, e.g. score >= 60)
[Review Queue] → Slack message to Lauren (card summary + score)
        ↓  (on approve)
[Enricher] → enriched_capabilities, pricing, api_surface, integrations
        ↓
[Schema Generator] → draft JSON in IcebreakerAI tool entry format
        ↓
[Second Slack Gate] → draft entry posted for final approval
        ↓  (on approve)
[Output Emitter] → output/{tool_id}.json written to disk
```

### Review Flow: Slack Interactions

```
[Slack Block Kit message] → Lauren clicks Approve/Reject/Snooze
        ↓
[Slack Bolt interaction handler]
        ↓
[queue.py: update_decision(signal_id, decision)]
        ↓  (if approved)
[Trigger enrichment pipeline for this signal_id]
        ↓
[Update Slack message to show decision + status]
```

### Deduplication Flow

```
[New SignalCard arrives]
        ↓
1. URL normalization + SHA-256 hash
2. Check hash against seen_urls table → exact duplicate? → mark and skip
        ↓  (if not exact duplicate)
3. Generate content embedding (title + summary, all-MiniLM-L6-v2 or Haiku)
4. Compare against recent embeddings (last 7 days) via cosine similarity
5. If similarity > 0.85 → cluster with existing signal, mark as duplicate
        ↓  (if novel)
6. Store hash + embedding → proceed to scoring
```

## Build Order (Phase Dependencies)

This is the critical ordering for the roadmap. Each layer depends on the one before it.

| Build Order | Component | Depends On | Why First |
|-------------|-----------|------------|-----------|
| 1 | DB schema + models | Nothing | All stages write to DB |
| 2 | Source Registry (config.yaml) + loader | DB | Collectors need source config |
| 3 | BaseCollector + RSS Collector | Source Registry | Prove collection works end-to-end |
| 4 | Normalizer | Collector output in DB | Signals can't be scored without normalization |
| 5 | Deduplicator | Normalizer | Must dedupe before scoring to avoid LLM waste |
| 6 | Scheduler (APScheduler) | Collectors working | Wire up periodic execution |
| 7 | LLM Scorer | Normalized, deduped cards | Scoring is the first LLM touch |
| 8 | Slack Bot + Gate 1 Review Queue | Scored cards | HITL can't function without scored inputs |
| 9 | Enricher | Gate 1 approval state | Only runs on approved signals |
| 10 | Schema Generator | Enriched cards | Depends on enrichment |
| 11 | Second Slack Gate + Output Emitter | Draft entries | Final quality gate before output |
| 12 | API/Scrape Collectors | BaseCollector | Expand source types after RSS proven |

**Key dependency insight:** The Slack bot (step 8) is a blocking dependency for validating the full pipeline. Everything before it can be built and tested in isolation. Everything after it depends on the approval state it produces.

## Scaling Considerations

| Scale | Architecture Adjustment |
|-------|------------------------|
| Current (15-20 sources, local cron) | SQLite + APScheduler in single process. No changes needed. |
| 50-100 sources | APScheduler still fine. Add connection pooling. Consider WAL mode for SQLite concurrency if enrichment runs overlap with collection. |
| 100+ sources or multi-machine | Replace SQLite with PostgreSQL. Replace APScheduler with Celery + Redis for distributed job execution. |

**First bottleneck:** SQLite write locking if collection runs overlap with scoring (both try to write simultaneously). Prevention: run stages sequentially within each cron tick, or enable SQLite WAL mode.

**Second bottleneck:** LLM API rate limits during scoring passes if many signals arrive at once. Prevention: batch scoring with `asyncio` + rate limiting via `tenacity`.

## Anti-Patterns

### Anti-Pattern 1: Enriching Before Human Review

**What people do:** Run full enrichment (web scrape + LLM) on every collected signal automatically, then surface the enriched result for review.

**Why it's wrong:** Enrichment is expensive (LLM tokens + time). Most collected signals get rejected. You waste cost on signals that would never graduate.

**Do this instead:** Surface a cheap Signal Card (title, URL, LLM-generated summary only) for Gate 1. Only enrich on approval. This is the architecture described above.

### Anti-Pattern 2: Stage-to-Stage Direct Calls

**What people do:** `normalizer.normalize(collector.fetch())` chained in a single function, bypassing the DB.

**Why it's wrong:** Makes stages impossible to run independently. Debugging requires running the full pipeline. State is invisible (no DB to query). Re-running a stage after a failure means re-running everything upstream.

**Do this instead:** Each stage writes its output to the DB. The scheduler invokes stages independently. Any stage can be replayed by re-processing its input table.

### Anti-Pattern 3: Monolithic Source Config in Code

**What people do:** Hardcode source URLs, frequencies, and types as Python constants or dictionaries inside the collector modules.

**Why it's wrong:** Adding a source requires a code change, a git commit, and a restart. Source configs also often differ between environments.

**Do this instead:** `config/sources.yaml` is the single source of truth. Adding a source = editing YAML only. The source loader and collector factory read from it at startup.

### Anti-Pattern 4: Ignoring Deduplication Until It Hurts

**What people do:** Skip deduplication in v1 ("we'll add it later"), then discover that the same Tool X launch appears in 8 sources and Lauren gets 8 identical Slack notifications.

**Why it's wrong:** Signal fatigue is the primary cause of review queue abandonment. Once Lauren stops reviewing, the system is useless.

**Do this instead:** Build URL-hash deduplication in the same phase as normalization. Semantic clustering can be added later, but exact URL dedup is trivially cheap and must be in from day 1.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| RSS/Atom feeds | feedparser library via HTTP GET | Battle-tested; handles malformed XML; 15+ years stable |
| Product Hunt API | REST + API key | Rate-limited; daily fetch sufficient for Tier 1 |
| HN Algolia API | REST, no auth required | `hn.algolia.com/api/v1/search` |
| Anthropic API (Haiku) | anthropic Python SDK | Scoring + enrichment; use async client for batching |
| Slack | slack_sdk Bolt (Python) | Socket Mode for local dev; avoids public webhook URL requirement |
| Web scraping | httpx + BeautifulSoup | Use httpx for async; respect robots.txt; add delays |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Collector → Normalizer | SQLite `raw_items` table | Collector writes, Normalizer reads |
| Normalizer → Deduplicator | SQLite `signal_cards` table | Same table; deduplicator updates `is_duplicate` flag |
| Deduplicator → Scorer | SQLite `signal_cards` table | Scorer filters `is_duplicate=False, score IS NULL` |
| Scorer → Slack Bot | SQLite `signal_cards` table | Bot reads `score >= threshold, review_status IS NULL` |
| Slack Bot → Enricher | SQLite `review_decisions` table | Enricher polls for `decision='approved', enriched=False` |
| Enricher → Schema Generator | SQLite `enriched_cards` table | Generator reads un-generated enriched cards |
| Schema Generator → Slack Gate 2 | SQLite `draft_entries` table | Bot reads `gate2_status IS NULL` |
| Slack Gate 2 → Output Emitter | SQLite `draft_entries` table | Emitter reads `gate2_status='approved', emitted=False` |

## Sources

- [Databricks: Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture) — Bronze/Silver/Gold layering pattern (HIGH confidence)
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — Scheduling library docs (HIGH confidence)
- [APScheduler SQLAlchemy jobstore](https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html) — Persistent job storage (HIGH confidence)
- [feedparser PyPI](https://pypi.org/project/feedparser/) — RSS/Atom parsing (HIGH confidence)
- [LangChain Human-in-the-Loop docs](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) — HITL patterns (HIGH confidence)
- [n8n HITL automation patterns](https://blog.n8n.io/human-in-the-loop-automation/) — Slack approval workflow patterns (MEDIUM confidence)
- [ETL Pipeline Architecture 101](https://www.mage.ai/blog/etl-pipeline-architecture-101-building-scalable-data-pipelines-with-python-sql-cloud) — ETL pipeline patterns (MEDIUM confidence)

---
*Architecture research for: AI ecosystem monitoring / intelligence pipeline (Watchman)*
*Researched: 2026-02-24*
