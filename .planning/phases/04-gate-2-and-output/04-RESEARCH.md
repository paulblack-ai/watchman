# Phase 4: Gate 2 and Output - Research

**Researched:** 2026-02-24
**Domain:** Slack Block Kit (Gate 2 review) + JSON file output
**Confidence:** HIGH

## Summary

Phase 4 completes the Watchman pipeline by adding a second Slack approval gate for enriched tool entries and a JSON output emitter for approved entries. The implementation closely mirrors existing Gate 1 patterns from Phase 2 (Slack Block Kit cards with action buttons, action handlers updating DB state, in-place message updates) while adding new elements: re-enrich flow with retry cap, Gate 2-specific card design showing enrichment data, and a JSON file writer producing IcebreakerAI-compatible output.

The codebase already has all foundation components: Slack Bolt app with Socket Mode, Block Kit card builders, action handler registration, DB state management, enrichment pipeline with Pydantic validation. Phase 4 extends these patterns without introducing new libraries.

**Primary recommendation:** Follow existing Gate 1 patterns exactly. Add Gate 2 action handlers in the existing `actions.py`, Gate 2 block builders in `blocks.py`, a new `output/writer.py` module for JSON emission, and DB migration for Gate 2 state columns.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Approve/reject only -- no inline editing of enrichment fields in Slack
- Reject offers two paths: permanent reject (dead end) or re-enrich (send back through enrichment pipeline)
- Re-enrichment capped at 2 retries (3 total enrichment attempts per signal)
- After max retries exhausted, only approve or permanent reject are available
- Re-enriched entries show latest enrichment only (no diff/comparison with previous attempt)

### Claude's Discretion
- Gate 2 Slack card design: what enrichment details to display, card layout, how to differentiate from Gate 1 cards
- Output file format: file naming, directory structure, one-file-per-tool vs batch, overwrite behavior
- Delivery timing: whether Gate 2 cards send immediately after enrichment or are batched, throttling relative to Gate 1

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OUT-01 | System presents enriched tool entry to Lauren in Slack for second approval | Gate 2 Block Kit card builder with enrichment details display; action handler registration for Gate 2 actions |
| OUT-02 | Lauren can approve or reject the enriched entry via Slack buttons | Gate 2 action handlers (approve_gate2, reject_gate2, re_enrich) with DB state tracking and retry cap logic |
| OUT-03 | Approved entries are written as JSON files to an output directory in IcebreakerAI-compatible schema | JSON writer using IcebreakerToolEntry.model_dump_json() with file-per-tool output to configurable directory |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack-bolt | >=1.18 | Slack app framework (already installed) | Action handlers, Block Kit rendering |
| slack-sdk | (bundled) | WebClient for Slack API calls | chat_postMessage, chat_update |
| pydantic | >=2.0 | IcebreakerToolEntry serialization | model_dump_json() for output files |
| aiosqlite | (installed) | Async SQLite access | DB state management |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | Output directory and file path management | JSON file writing |
| json | stdlib | JSON formatting with indentation | Pretty-printed output files |

### Alternatives Considered
None -- Phase 4 uses only existing project dependencies.

## Architecture Patterns

### Recommended Project Structure
```
src/watchman/
├── slack/
│   ├── actions.py       # ADD Gate 2 action handlers alongside Gate 1
│   ├── blocks.py        # ADD Gate 2 card builder functions
│   └── delivery.py      # ADD Gate 2 delivery (immediate post-enrichment)
├── output/
│   ├── __init__.py      # NEW module
│   └── writer.py        # NEW JSON file emitter
└── storage/
    ├── database.py      # ADD migrate_phase4()
    └── repositories.py  # ADD Gate 2 state queries
```

### Pattern 1: Gate 2 Action Handlers (Mirror Gate 1)
**What:** Register Gate 2 action handlers following the exact same pattern as Gate 1 (approve_card, reject_card)
**When to use:** For all Gate 2 Slack button interactions

Gate 1 pattern from actions.py:
```python
@app.action("approve_card")
def handle_approve(ack, body, client, logger):
    ack()
    _handle_review_action(body, client, "approved")
```

Gate 2 mirrors this with different action IDs and a shared handler:
```python
@app.action("approve_gate2")
def handle_approve_gate2(ack, body, client, logger):
    ack()
    _handle_gate2_action(body, client, "gate2_approved")

@app.action("reject_gate2")
def handle_reject_gate2(ack, body, client, logger):
    ack()
    _handle_gate2_action(body, client, "gate2_rejected")

@app.action("re_enrich")
def handle_re_enrich(ack, body, client, logger):
    ack()
    _handle_re_enrich_action(body, client)
```

### Pattern 2: Immediate Gate 2 Delivery (Post-Enrichment)
**What:** Send Gate 2 Slack card immediately after enrichment completes, rather than batching
**When to use:** Triggered from enrichment pipeline on success

Recommendation: Deliver Gate 2 cards immediately when enrichment completes. This keeps the pipeline responsive -- Lauren approved in Gate 1 and expects the enriched version promptly. This matches the existing pattern where enrichment triggers immediately on Gate 1 approval.

### Pattern 3: JSON File Output (One File Per Tool)
**What:** Write one JSON file per approved tool entry to the output directory
**When to use:** Triggered by Gate 2 approval

Recommendation:
- One file per tool: `output/{sanitized_name}_{card_id}.json`
- Pretty-printed JSON with 2-space indent
- Configurable output directory via `WATCHMAN_OUTPUT_DIR` env var (default: `./output`)
- Skip write if file already exists (no overwrite)
- Use `IcebreakerToolEntry.model_dump_json(indent=2)` for serialization

### Anti-Patterns to Avoid
- **Shared action IDs between Gate 1 and Gate 2:** Use distinct action_id values (approve_gate2, not approve_card) to avoid handler conflicts
- **Inline DB queries in action handlers:** Use CardRepository methods, same as Gate 1
- **Synchronous file I/O in action handlers:** JSON writes are fast enough to be sync in the ack() handler; no async needed for small JSON files

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON serialization | Custom dict building | `IcebreakerToolEntry.model_dump_json()` | Pydantic handles datetime, None, nested types |
| File name sanitization | Regex-based cleaner | `re.sub(r'[^\w\-]', '_', name).lower()[:50]` | Simple, but use a standard pattern |
| Slack message updates | Direct API calls | `client.chat_update()` (already used in Gate 1) | Handles threading, error codes |

## Common Pitfalls

### Pitfall 1: Re-enrich Retry Counter Not Persisted
**What goes wrong:** Re-enrichment retry count stored in memory (lost on restart)
**Why it happens:** Treating retry count as transient state
**How to avoid:** Store enrichment_attempt_count in the DB as a column (Phase 4 migration)
**Warning signs:** Re-enrich button appears after restart when it shouldn't

### Pitfall 2: Gate 2 Card Sent Before Enrichment Complete
**What goes wrong:** Gate 2 Slack card posted with incomplete/missing enrichment data
**Why it happens:** Race condition between enrichment state update and Gate 2 delivery
**How to avoid:** Trigger Gate 2 delivery from within the enrichment pipeline completion path (after save_enrichment succeeds)
**Warning signs:** Gate 2 cards with "None" or empty fields

### Pitfall 3: Output Directory Not Created
**What goes wrong:** JSON write fails because output directory doesn't exist
**Why it happens:** Assuming directory exists
**How to avoid:** Use `output_dir.mkdir(parents=True, exist_ok=True)` before writing
**Warning signs:** FileNotFoundError in logs

### Pitfall 4: asyncio.run() in Action Handlers
**What goes wrong:** Nested event loop errors
**Why it happens:** Bolt action handlers are sync, but DB operations are async
**How to avoid:** Use the established pattern: `asyncio.run(_update())` -- already working in Gate 1 handlers
**Warning signs:** "Cannot run the event loop while another loop is running"

## Code Examples

### Gate 2 Block Kit Card (Recommended Design)
```python
def build_gate2_card_blocks(card: SignalCard, entry: IcebreakerToolEntry, can_re_enrich: bool) -> list[dict]:
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f":mag: {entry.name}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{card.url}|{card.title}>*\n{entry.description}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Capabilities:*\n{chr(10).join('- ' + c for c in entry.capabilities[:5])}"},
                {"type": "mrkdwn", "text": f"*Pricing:* {entry.pricing or 'Unknown'}\n*API:* {entry.api_surface or 'Unknown'}"}
            ]
        },
        # Actions with conditional re-enrich
    ]
    return blocks
```

### JSON Output Writer
```python
import json
import re
from pathlib import Path

def write_tool_entry(entry: IcebreakerToolEntry, card_id: int, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w\-]', '_', entry.name).lower()[:50]
    filename = f"{safe_name}_{card_id}.json"
    filepath = output_dir / filename
    if filepath.exists():
        return filepath  # No overwrite
    filepath.write_text(entry.model_dump_json(indent=2))
    return filepath
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate Bolt apps per gate | Single Bolt app with namespaced action IDs | Current best practice | Simpler architecture, one Socket Mode connection |

## Open Questions

1. **IcebreakerAI schema field completeness**
   - What we know: Current IcebreakerToolEntry has 8 fields (name, description, capabilities, pricing, api_surface, integration_hooks, source_url, discovered_at)
   - What's unclear: Whether the actual registry needs additional metadata fields
   - Recommendation: Use current schema as-is; add fields later if registry requires them

## Sources

### Primary (HIGH confidence)
- Existing codebase: slack/actions.py, slack/blocks.py, slack/delivery.py -- patterns verified from working Gate 1 implementation
- Existing codebase: enrichment/pipeline.py, models/icebreaker.py -- enrichment data flow verified
- Existing codebase: storage/database.py, storage/repositories.py -- migration and repository patterns verified

### Secondary (MEDIUM confidence)
- Slack Block Kit documentation -- Block types, action_id registration, chat_update API

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries needed, all patterns verified in codebase
- Architecture: HIGH -- mirrors Gate 1 patterns exactly, well-understood code
- Pitfalls: HIGH -- derived from analysis of existing action handler code and enrichment pipeline

**Research date:** 2026-02-24
**Valid until:** Indefinite (no external dependency changes expected)
