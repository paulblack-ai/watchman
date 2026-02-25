# Stack Research

**Domain:** AI ecosystem monitoring agent (Python, local cron, Slack review interface)
**Researched:** 2026-02-24
**Confidence:** HIGH (core stack) / MEDIUM (library-level specifics)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | Matches IcebreakerAI stack (mandatory constraint). 3.11 gives significant perf over 3.10; 3.12 is stable and fine too. |
| SQLite (stdlib) | built-in | Signal state, dedup index, source registry, approval queue | Zero-dependency, local-cron-appropriate. No Postgres overhead for a single-machine cron job with low write volume. Python's `sqlite3` module is synchronous, which matches the synchronous execution model. |
| APScheduler | 3.11.x | Cron scheduling, per-source frequencies | V3 is production-stable. V4 is pre-release and API-breaking — do NOT use yet. BackgroundScheduler or BlockingScheduler depending on whether the process is foreground. CronTrigger supports per-source cadences. |
| anthropic (SDK) | 0.81.x | LLM classification and enrichment calls | Official Anthropic Python SDK, latest v0.81.0 (Feb 2026). Use `claude-haiku-4-5` for scoring (cheap), `claude-sonnet-4-5` only for enrichment on approved signals. |
| slack-bolt | 1.27.x | Slack bot for review queue | Official Slack framework, handles Block Kit interactions (approve/reject buttons), Socket Mode for local dev, OAuth for hosted. Standard choice for interactive Slack apps in Python. |

### Signal Collection Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| feedparser | 6.0.12 | RSS/Atom feed parsing | All Tier 1 RSS sources (Hacker News, product blogs, LLM tracker feeds). 9.6M monthly downloads, handles malformed feeds gracefully. |
| httpx | 0.27.x | HTTP client for API sources | All API calls (Product Hunt, GitHub trending, etc.). Use synchronous client — matches APScheduler's sync job model. Has HTTP/2 support if needed. |
| trafilatura | 2.0.x | Article text extraction from web pages | Tier 3 SaaS changelog scraping where you need clean text (not raw HTML). Benchmarks as best-in-class for main content extraction accuracy. Handles readability detection, metadata, and dedup via built-in LSH. |
| playwright (python) | 1.49.x | JavaScript-heavy page rendering | Use only when trafilatura+httpx fails (JS-rendered pages, SPAs). Adds complexity and a browser binary — keep as fallback, not default. |
| instructor | 1.x | Structured LLM outputs via Pydantic | Wrap Claude calls for scoring and enrichment. Returns validated Pydantic models instead of raw JSON, handles retries automatically. Works with Anthropic natively. |
| pydantic | 2.x | Data validation and signal card schemas | Define SignalCard, SourceConfig, ScoringResult, ToolEntry schemas. V2 is current standard — do not use V1. |
| pydantic-settings | 2.x | Config and secrets management | Load API keys, source configs, Slack tokens from `.env`. Priority: env vars > .env file. Use `SecretStr` for tokens. |
| datasketch | 1.6.x | MinHash/LSH near-duplicate detection | Deduplicate signals from multiple sources covering the same event. URL-based exact dedup first, MinHash for near-dupe title/summary clustering. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Linting and formatting | Replaces flake8 + black + isort in one tool. Configured via `pyproject.toml`. |
| mypy | Static type checking | Required — all public functions must have type annotations. |
| pytest | Testing | Unit tests for collectors, normalizers, scorer; integration tests against mock Slack/LLM responses. |
| python-dotenv | `.env` file loading | Used through pydantic-settings; also load directly for local dev scripts. |
| uv | Package management | Faster than pip. Use for venv creation and dependency management. Replaces pip + virtualenv. |

---

## Installation

```bash
# Create venv and install with uv
uv venv .venv --python 3.11
source .venv/bin/activate

# Core runtime
uv pip install \
  anthropic==0.81.* \
  slack-bolt==1.27.* \
  apscheduler==3.11.* \
  feedparser==6.0.* \
  httpx==0.27.* \
  trafilatura==2.0.* \
  instructor==1.* \
  pydantic==2.* \
  pydantic-settings==2.* \
  datasketch==1.6.*

# Dev dependencies
uv pip install \
  ruff \
  mypy \
  pytest \
  pytest-mock \
  python-dotenv
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| APScheduler 3.x | system cron (`crontab`) | System cron can't vary frequency per source, no Python-native state, harder to test and reason about |
| APScheduler 3.x | APScheduler 4.x | v4 is explicitly pre-release; "may change in a backwards incompatible fashion without any migration pathway" — do not use in production |
| feedparser | fastfeedparser | feedparser is the ecosystem standard. fastfeedparser is faster but less forgiving with malformed feeds. At 15-20 sources, throughput is not a bottleneck. |
| trafilatura | BeautifulSoup + requests | trafilatura outperforms BS4 in content extraction accuracy and handles readability detection and dedup built-in. BS4 requires more hand-coding per site. |
| SQLite (stdlib) | PostgreSQL | Overkill for a local cron agent with low write volume. PostgreSQL adds an operational dependency (process management, connections). SQLite is sufficient until multi-process or multi-machine scale. |
| SQLite (stdlib) | TinyDB / shelve | SQLite has proper transactions, indexing for dedup queries, and is inspectable with standard tooling. TinyDB is JSON-file-based with no indexing. |
| instructor | raw Claude tool use | instructor wraps tool-use pattern with Pydantic validation and auto-retry on schema violations. Less boilerplate, catches malformed LLM outputs before they propagate. |
| httpx | requests | requests has no async support (not planned). httpx is requests-compatible API with type annotations. For this project's sync model the gain is minimal, but httpx is the forward-looking standard. |
| playwright | Selenium | Playwright is faster, modern, has better Python API, automatic element waiting. If JS rendering is ever needed, use playwright. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| APScheduler 4.x | Explicitly pre-release as of Feb 2026; API is unstable and documented as "may break without migration path" | APScheduler 3.11.x |
| LangChain / LlamaIndex | Massive abstraction over what is a simple classification pipeline. Adds 50+ transitive dependencies, opaque abstractions, frequent breaking changes. Watchman's LLM use is simple: score a card, enrich on approval. | Direct anthropic SDK + instructor |
| Celery | Distributed task queue built for multi-worker deployments. Watchman is a single-machine cron job — Celery requires a broker (Redis/RabbitMQ) and adds unnecessary operational complexity | APScheduler |
| Scrapy | Full crawling framework designed for large-scale multi-page crawls. Watchman scrapes at most one page per source per cycle — Scrapy is overbuilt | trafilatura + httpx for scraping targets |
| aiohttp | asyncio-based HTTP client. Watchman's execution model is synchronous (APScheduler cron jobs run in sequence/threads). Mixing async I/O into sync cron jobs creates complexity without benefit | httpx (sync client) |
| PyPI `schedule` | Simpler than APScheduler but lacks per-job cron syntax, persistent job state, or exception-handling hooks | APScheduler 3.x |

---

## Stack Patterns by Variant

**If running as a long-lived background daemon (always-on process):**
- Use `BlockingScheduler` from APScheduler
- The main thread blocks on the scheduler loop

**If running from a system cron entry (process-per-run):**
- Skip APScheduler entirely
- Use a simple `__main__` entry point that runs all collectors for that cadence tier
- System crontab controls timing
- Simpler but loses per-source frequency granularity

**If Slack Socket Mode is not available (e.g., behind a firewall):**
- Use `slack-bolt` with HTTP mode + ngrok for local dev
- Or: post signals as Slack messages with approval links that hit a lightweight FastAPI endpoint

**If LLM costs become a concern:**
- Scoring: already using Haiku 4.5 (cheapest capable Anthropic model — $1/M input tokens)
- Add prompt caching with Anthropic's beta caching feature for repeated system prompts
- Batch classification by sending multiple signal summaries in one call (score N signals per API call)

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|----------------|-------|
| anthropic 0.81.x | Python 3.9+ | httpx is a transitive dependency — don't also pin httpx separately unless you know the version constraint |
| pydantic 2.x | pydantic-settings 2.x, instructor 1.x | V1 and V2 are incompatible at import level. instructor 1.x requires pydantic v2. |
| slack-bolt 1.27.x | slack-sdk 3.x (transitive) | Do not separately install `slack-sdk` — it comes as a pinned transitive dep via bolt |
| APScheduler 3.11.x | Python 3.6+ | Do not install APScheduler 4.x by mistake; pip may resolve to 4.x if you omit the version pin |
| trafilatura 2.0.x | Python 3.8+ | 2.0 release added built-in LSH deduplication — use this version or later |
| playwright 1.49.x | Python 3.8+ | Requires `playwright install chromium` after pip install — adds ~170MB browser binary |

---

## Sources

- [anthropic PyPI — v0.81.0 confirmed Feb 2026](https://pypi.org/project/anthropic/)
- [APScheduler v4 migration note — "do NOT use in production"](https://apscheduler.readthedocs.io/en/master/migration.html)
- [feedparser 6.0.12 — Sep 2025, 9.6M monthly downloads](https://libraries.io/pypi/feedparser)
- [trafilatura 2.0.0 — best-in-class content extraction benchmarks](https://trafilatura.readthedocs.io/en/latest/)
- [slack-bolt 1.27.0 — latest stable PyPI](https://pypi.org/project/slack-bolt/)
- [instructor — Pydantic-backed structured LLM outputs, Anthropic native support](https://python.useinstructor.com/)
- [httpx vs requests comparison — httpx recommended for modern Python](https://towardsdatascience.com/beyond-requests-why-httpx-is-the-modern-http-client-you-need-sometimes/)
- [datasketch — MinHash/LSH near-duplicate detection](https://yorko.github.io/2023/practical-near-dup-detection/)
- [pydantic-settings 2.x — official docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Anthropic structured outputs — beta header, Pydantic integration](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

---
*Stack research for: Watchman — AI ecosystem monitoring agent*
*Researched: 2026-02-24*
