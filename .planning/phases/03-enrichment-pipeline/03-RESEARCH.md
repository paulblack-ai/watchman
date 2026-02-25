# Phase 3: Enrichment Pipeline - Research

**Researched:** 2026-02-24
**Domain:** LLM-powered web scraping and structured extraction
**Confidence:** HIGH

## Summary

Phase 3 adds an enrichment pipeline triggered by Gate 1 approval. When Lauren approves a signal card in Slack, the system scrapes the tool's webpage, feeds the content to Claude Sonnet, extracts structured fields (capabilities, pricing, API surface, integration hooks), and validates the result against the existing `IcebreakerToolEntry` Pydantic schema.

The project already has all necessary dependencies installed: `anthropic` for Claude API access, `httpx` for HTTP requests, `trafilatura` for web content extraction, and `pydantic` for schema validation. The scoring module (`src/watchman/scoring/scorer.py`) provides a proven pattern for Claude API calls with structured output that enrichment can follow directly.

**Primary recommendation:** Build an `enrichment/` module mirroring the `scoring/` module structure. Use `trafilatura` (already a dependency) for webpage scraping, Claude Sonnet with `json_schema` structured output for extraction, and validate against `IcebreakerToolEntry`. Trigger enrichment from the existing `_handle_review_action` in `slack/actions.py` when state is "approved".

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Primary source: scrape the tool's webpage (URL from signal card) and feed page content to the LLM
- Fallback: if the page is inaccessible (403, paywall, JS-heavy SPA), fall back to signal card data (title, summary, URL) for best-effort enrichment
- Do NOT pass scoring breakdown to the LLM -- enrichment extracts facts from content independently, without scoring bias
- Use Claude Sonnet for enrichment extraction (higher reasoning capability for nuanced content like inferring pricing tiers from vague marketing copy)

### Claude's Discretion
- Enrichment field depth (how detailed capabilities, pricing, API surface fields should be)
- Validation failure handling (what happens when LLM output doesn't match the Pydantic schema)
- Pipeline timing (immediate vs batched enrichment after approval)
- Notification behavior (whether to notify Lauren when enrichment completes or silently queue for Gate 2)
- Prompt engineering approach for structured extraction
- Web scraping strategy (library choice, timeout handling, content extraction method)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENRCH-01 | Enrichment triggers only on Gate 1 approval (never on unapproved signals) | Hook into existing `_handle_review_action` in `slack/actions.py` when state == "approved"; add `enrichment_state` column to cards table |
| ENRCH-02 | Enrichment extracts capabilities, pricing, API surface, and integration hooks using LLM | Use `trafilatura` for scraping + Claude Sonnet with `json_schema` structured output matching `IcebreakerToolEntry` schema |
| ENRCH-03 | Enrichment output validated against IcebreakerAI tool registry schema via Pydantic | Use `IcebreakerToolEntry.model_validate()` on LLM output; existing Pydantic model already defines the schema |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.40 | Claude Sonnet API calls for extraction | Already in project deps; proven pattern in scoring module |
| trafilatura | >=2.0 | Web page content extraction | Already in project deps; purpose-built for extracting article/page text from HTML |
| pydantic | >=2.0 | Schema validation for enrichment output | Already in project deps; `IcebreakerToolEntry` model exists |
| httpx | >=0.28 | HTTP requests for page fetching | Already in project deps; async-capable HTTP client |
| aiosqlite | >=0.20 | Database operations | Already in project deps; used everywhere else |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging (stdlib) | - | Structured logging | All enrichment operations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| trafilatura | beautifulsoup4 + requests | trafilatura is already a dep and handles boilerplate/nav extraction automatically |
| json_schema output | Tool use for extraction | json_schema is simpler, proven in scorer, direct Pydantic integration |

**Installation:** No new dependencies needed. All libraries already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
src/watchman/
├── enrichment/
│   ├── __init__.py
│   ├── scraper.py       # Web page fetching + content extraction
│   ├── extractor.py     # Claude Sonnet structured extraction
│   └── pipeline.py      # Orchestrates scrape -> extract -> validate
├── models/
│   └── icebreaker.py    # Existing IcebreakerToolEntry schema (no changes)
├── slack/
│   └── actions.py       # Modified: trigger enrichment on approve
└── storage/
    ├── database.py      # Modified: Phase 3 migration
    └── repositories.py  # Modified: enrichment state queries
```

### Pattern 1: Mirror Scoring Module Structure
**What:** The enrichment module follows the same architecture as `scoring/` -- a focused module with clear input/output, called from a scheduler job or action handler.
**When to use:** Always -- this is the established project pattern.
**Example:**
```python
# enrichment/extractor.py -- mirrors scoring/scorer.py
async def enrich_card(card: SignalCard, page_content: str | None) -> IcebreakerToolEntry:
    client = anthropic.Anthropic()
    prompt = _build_enrichment_prompt(card, page_content)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        betas=["output-128k-2025-02-19"],
        output_config={
            "format": {
                "type": "json_schema",
                "name": "icebreaker_tool_entry",
                "schema": IcebreakerToolEntry.model_json_schema(),
            }
        },
    )
    return IcebreakerToolEntry.model_validate_json(response.content[0].text)
```

### Pattern 2: Trigger-on-Approve with Async Bridge
**What:** When Lauren approves a card in Slack, fire enrichment immediately. Use the same `asyncio.run()` bridge pattern from `slack/actions.py`.
**When to use:** For ENRCH-01 -- enrichment only on approval.
**Example:**
```python
# In slack/actions.py _handle_review_action, after state == "approved":
if state == "approved":
    try:
        asyncio.run(_run_enrichment(card_id, db_path))
    except Exception:
        logger.exception("Enrichment failed for card %d", card_id)
```

### Pattern 3: Graceful Fallback Scraping
**What:** Try to scrape the URL. If scraping fails (403, timeout, empty content), fall back to card metadata for best-effort extraction.
**When to use:** Always -- web scraping is inherently unreliable.
**Example:**
```python
# enrichment/scraper.py
async def scrape_url(url: str, timeout: float = 15.0) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "..."})
            response.raise_for_status()
            return trafilatura.extract(response.text) or None
    except Exception:
        logger.warning("Scrape failed for %s, falling back to card data", url)
        return None
```

### Anti-Patterns to Avoid
- **Enriching before approval:** Never trigger enrichment on scoring or card creation -- only on explicit Gate 1 approval (ENRCH-01)
- **Passing scoring data to enrichment LLM:** The CONTEXT.md explicitly forbids this -- enrichment must extract facts independently
- **Blocking the Slack action handler:** Enrichment may take 5-15 seconds (scrape + LLM call). Consider running it in a background thread or accepting brief blocking since Bolt action handlers run in a thread pool anyway
- **Retrying indefinitely on scrape failure:** Use fallback to card data instead of retry loops

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML content extraction | Custom HTML parser | `trafilatura.extract()` | Handles boilerplate removal, nav stripping, encoding issues |
| Structured LLM output | Manual JSON parsing from free-text | `json_schema` structured output | Guaranteed schema compliance, no parsing errors |
| Schema validation | Manual field checking | `IcebreakerToolEntry.model_validate()` | Pydantic handles type coercion, validation errors, optional fields |

**Key insight:** The project already has all the tools. trafilatura does the hard work of extracting readable text from messy HTML. Claude's json_schema output eliminates parsing fragility. Pydantic validates the result. No custom extraction logic needed.

## Common Pitfalls

### Pitfall 1: Scraping Failures on JS-Heavy Sites
**What goes wrong:** Many AI tool sites are SPAs (React/Vue) where trafilatura gets empty or minimal content.
**Why it happens:** trafilatura works on server-rendered HTML; JS-rendered content is invisible.
**How to avoid:** Design the fallback path as a first-class citizen, not an afterthought. The LLM can still produce useful enrichment from title + summary + URL.
**Warning signs:** Empty or very short (<100 chars) content from trafilatura.

### Pitfall 2: LLM Hallucinating Pricing/Capabilities
**What goes wrong:** Claude may infer or fabricate pricing tiers or capabilities not mentioned on the page.
**Why it happens:** LLMs fill gaps when content is vague; marketing pages often lack specifics.
**How to avoid:** Prompt engineering: instruct Claude to output null/empty for fields it cannot verify from the provided content. Make pricing and api_surface nullable in the schema.
**Warning signs:** Suspiciously detailed output from sparse source content.

### Pitfall 3: Anthropic API Model Name Changes
**What goes wrong:** Hardcoded model names break when Anthropic updates model versions.
**Why it happens:** Model names include version dates (e.g., `claude-sonnet-4-20250514`).
**How to avoid:** Use the latest stable Sonnet model name. The scoring module already hardcodes `claude-haiku-4-5-20251001` -- follow the same pattern but consider making it configurable.
**Warning signs:** API errors about unknown model names.

### Pitfall 4: Database Migration Ordering
**What goes wrong:** Phase 3 adds columns (enrichment_state, enrichment_data) but migration isn't idempotent.
**Why it happens:** Running init_db multiple times causes duplicate column errors.
**How to avoid:** Follow the Phase 2 pattern: use try/except per ALTER TABLE statement. Already proven in `migrate_phase2()`.
**Warning signs:** Errors on second run of the application.

## Code Examples

### Web Scraping with Trafilatura
```python
import trafilatura
import httpx

async def fetch_and_extract(url: str) -> str | None:
    """Fetch a URL and extract main content text."""
    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "Watchman/0.1 (+https://icebreakerai.com)"}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    # trafilatura extracts main content, strips boilerplate
    extracted = trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=True,
    )
    return extracted
```

### Claude Sonnet Structured Extraction
```python
import anthropic
from watchman.models.icebreaker import IcebreakerToolEntry

def _build_enrichment_prompt(card_title: str, card_url: str, page_content: str | None) -> str:
    content_section = f"## Page Content\n\n{page_content}" if page_content else (
        "## Note\nPage content could not be scraped. Extract what you can from the title and URL only."
    )

    return f"""Extract structured tool information for the IcebreakerAI tool registry.

## Signal
**Title:** {card_title}
**URL:** {card_url}

{content_section}

## Instructions
1. Extract factual information ONLY from the provided content.
2. For fields you cannot determine from the content, use null or empty list.
3. Do NOT infer or fabricate pricing, capabilities, or API details not mentioned in the content.
4. capabilities: list specific features/capabilities mentioned.
5. pricing: extract pricing model if mentioned (free, freemium, paid, enterprise, etc.), null if not stated.
6. api_surface: describe API/SDK availability if mentioned, null if not stated.
7. integration_hooks: list specific integrations mentioned (e.g., "Slack", "GitHub", "REST API").

Respond with a JSON object matching the required schema."""
```

### Pydantic Validation
```python
from watchman.models.icebreaker import IcebreakerToolEntry

# Validate LLM output
try:
    entry = IcebreakerToolEntry.model_validate_json(response_text)
except ValidationError as e:
    logger.error("Enrichment validation failed: %s", e)
    # Store validation failure, don't proceed to Gate 2
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text LLM output + regex parsing | `json_schema` structured output | Anthropic 2024 | Eliminates parsing failures entirely |
| BeautifulSoup manual scraping | trafilatura automatic extraction | Stable since 2023 | Handles boilerplate removal, encoding, and diverse page structures |
| Manual HTTP with requests | httpx async client | Project standard | Async-compatible, already used in collectors |

## Open Questions

1. **Claude Sonnet model version**
   - What we know: Latest Sonnet is `claude-sonnet-4-20250514`
   - What's unclear: Whether to hardcode or make configurable
   - Recommendation: Hardcode like scoring does with Haiku, update when needed. Configuring model name adds complexity for rare changes.

2. **Enrichment timing**
   - What we know: User left this to Claude's discretion
   - What's unclear: Immediate (in approve handler) vs deferred (background job)
   - Recommendation: Immediate in the approve handler. Enrichment involves one HTTP request + one LLM call (~5-15s). Slack Bolt handlers run in a thread pool, so this won't block other actions. Simpler than adding a background queue for a single-user system.

3. **Notification after enrichment**
   - What we know: User left this to Claude's discretion
   - What's unclear: Whether to notify Lauren when enrichment completes
   - Recommendation: Silently queue for Gate 2 (Phase 4). Enrichment is automatic plumbing -- Lauren will see the result when Gate 2 presents the enriched entry. Notifying on every enrichment adds noise.

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/watchman/scoring/scorer.py` -- proven Claude API pattern with structured output
- Project codebase: `src/watchman/models/icebreaker.py` -- existing target schema
- Project codebase: `src/watchman/slack/actions.py` -- existing approve handler as trigger point

### Secondary (MEDIUM confidence)
- Anthropic API documentation -- json_schema structured output format
- trafilatura documentation -- content extraction capabilities

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, proven patterns exist
- Architecture: HIGH - mirrors existing scoring module, clear integration points
- Pitfalls: MEDIUM - scraping reliability is inherently uncertain, LLM output quality varies

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain, no fast-moving dependencies)
