# Phase 2: Scoring and Slack Review - Research

**Researched:** 2026-02-24
**Domain:** LLM scoring with Claude Haiku, Slack interactive messages (Block Kit), button action handling, slash commands
**Confidence:** HIGH

## Summary

Phase 2 adds two major capabilities: (1) automated relevance scoring of signal cards using Claude Haiku 4.5 against a YAML-configured rubric, and (2) a Slack-based review interface where Lauren receives scored cards as Block Kit messages and can approve, reject, or snooze each card via buttons. It also includes a `/watchman add-source` slash command.

The standard approach for scoring is the Anthropic Python SDK (anthropic>=0.80) with structured outputs (`output_config.format`) to guarantee schema-conformant JSON score breakdowns from Haiku 4.5. For Slack interactivity, Bolt for Python (slack-bolt>=1.27) with Socket Mode is the correct pattern — it eliminates the need for an HTTP server, using a persistent WebSocket connection instead. This aligns with the existing architecture (single-process agent on Paul's machine).

The key integration challenge is threading Bolt's Socket Mode listener alongside APScheduler's async run loop. Both can coexist by running Bolt in a background thread (sync `SocketModeHandler`) while the main process continues running APScheduler. The database schema for Phase 2 requires new columns on the `cards` table for score data and review state, plus a `snooze_until` timestamp for re-queue logic.

**Primary recommendation:** Use `anthropic>=0.80` with `output_config.format` structured outputs for scoring, and `slack-bolt>=1.27` with sync `SocketModeHandler` in a background thread for Slack interactivity. Keep scoring as a processing step that runs after normalization; keep Slack delivery as a scheduled daily job.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Each Slack card shows the overall relevance score plus the top contributing rubric dimension (e.g., "8.2 — strong taxonomy fit")
- A "Details" button on each card expands to reveal the full 4-dimension rubric breakdown (taxonomy fit, novel capability, adoption/traction, credibility)
- Full rubric score breakdowns are persisted in the database per signal for future calibration
- Daily review includes a summary count footer (e.g., "Showing 5 of 23 signals today")
- Signals that don't make the daily cap are silently excluded from individual cards — only the aggregate count is shown
- Rubric weights are defined in YAML config (not hardcoded) so they can be adjusted without code changes
- Default weights ship with the starter config (taxonomy fit, novel capability, adoption/traction, credibility)

### Claude's Discretion
- Slack card layout and visual hierarchy (Block Kit structure, spacing, emoji usage)
- Review delivery timing and cadence (single cards vs. batch, time of day)
- Button placement and interaction flow for approve/reject/snooze
- Snooze visual behavior (confirmation message, re-queue indicator)
- `/watchman add-source` slash command UX and validation flow
- Score scale (0-10, 0-100, etc.) and threshold logic for the daily cap
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-04 | Score signals against IcebreakerAI relevance rubric (taxonomy fit, novel capability, adoption/traction, credibility) using Claude Haiku | Anthropic SDK structured outputs with `output_config.format`; Haiku 4.5 supports structured outputs GA |
| PROC-05 | Enforce daily volume cap (3-7 cards) to prevent signal fatigue | Score all cards, rank by composite score, select top N; cap logic in scorer or delivery job |
| PROC-06 | Persist score breakdown per signal for future calibration | New columns on `cards` table: `relevance_score`, `score_breakdown` (JSON), `top_dimension` |
| SLCK-01 | Deliver scored signal cards to Lauren's Slack channel using Block Kit | Bolt for Python + `client.chat_postMessage` with Block Kit blocks; Socket Mode for receiving interactions |
| SLCK-02 | Lauren can approve a signal card via Slack button | `@app.action("approve_card")` handler updates card state to `approved` in DB, updates message |
| SLCK-03 | Lauren can reject a signal card via Slack button | `@app.action("reject_card")` handler updates card state to `rejected` in DB, updates message |
| SLCK-04 | Lauren can snooze a signal card via Slack button (30-day expiry, re-queues after expiry) | `@app.action("snooze_card")` sets `snooze_until = now + 30 days` in DB; daily job re-queues expired snoozes |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.80 | Claude Haiku API calls with structured outputs | Official Anthropic Python SDK; structured outputs GA for Haiku 4.5 as of Dec 2025 |
| slack-bolt | >=1.27 | Bolt framework for Slack apps: actions, commands, Socket Mode | Official Slack Python framework; replaces raw SDK for interactive apps |
| slack-sdk | >=3.0 | Already installed; used for `WebClient.chat_postMessage` | Bolt wraps slack-sdk; both are used together |
| pydantic | >=2.0 | Already installed; Score models as typed dataclasses | Consistent with existing codebase pattern |
| pyyaml | >=6.0 | Already installed; rubric weights config file | Consistent with existing sources.yaml pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiohttp | >=3.9 | Required by AsyncApp if async Bolt used | Only needed if choosing async Bolt variant |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slack-bolt | raw slack-sdk WebClient only | Raw SDK cannot handle interactive payloads (buttons, slash commands); Bolt is necessary |
| structured outputs (`output_config.format`) | Prompt-only JSON parsing | Structured outputs guarantee valid JSON; prompt-only risks parse failures and requires retry logic |
| sync SocketModeHandler in thread | AsyncSocketModeHandler + asyncio | Async variant requires aiohttp and async refactor of existing sync codebase; sync in thread is simpler |

**Installation:**
```bash
pip install "anthropic>=0.80" "slack-bolt>=1.27"
```

## Architecture Patterns

### Recommended Project Structure
```
src/watchman/
├── scoring/
│   ├── __init__.py
│   ├── scorer.py          # Claude Haiku scoring logic
│   └── rubric.py          # Rubric config loader (YAML weights → RubricConfig)
├── slack/
│   ├── __init__.py
│   ├── app.py             # Bolt App init + SocketModeHandler setup
│   ├── blocks.py          # Block Kit builder functions for signal cards
│   ├── actions.py         # @app.action handlers (approve, reject, snooze)
│   ├── commands.py        # @app.command handler (/watchman add-source)
│   └── delivery.py        # Daily review queue delivery job
├── config/
│   ├── loader.py          # (existing) source config loader
│   └── rubric.yaml        # NEW: rubric weights configuration
└── storage/
    ├── database.py        # (existing) + new columns migration
    └── repositories.py    # (existing) + CardRepository scoring/review methods
```

### Pattern 1: Structured Output Scoring with Claude Haiku
**What:** Call Haiku with `output_config.format` to get guaranteed JSON score breakdown matching a Pydantic schema
**When to use:** Every time a new non-duplicate signal card is created by the normalizer

```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
import anthropic
import json
from pydantic import BaseModel

class DimensionScore(BaseModel):
    score: float  # 0.0 - 10.0
    rationale: str

class RubricScore(BaseModel):
    taxonomy_fit: DimensionScore
    novel_capability: DimensionScore
    adoption_traction: DimensionScore
    credibility: DimensionScore
    composite_score: float
    top_dimension: str  # e.g. "taxonomy_fit"

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=512,
    messages=[{"role": "user", "content": scoring_prompt}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": RubricScore.model_json_schema(),
        }
    },
)
score = RubricScore.model_validate_json(response.content[0].text)
```

### Pattern 2: Bolt Socket Mode — Sync in Background Thread
**What:** Run `SocketModeHandler` in a daemon thread so it doesn't block APScheduler's main loop
**When to use:** Always — this is the correct pattern for a single-process agent without an HTTP server

```python
# Source: https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/
import threading
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ["SLACK_BOT_TOKEN"])

def start_slack_listener():
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()

# In main.py, before scheduler.start():
slack_thread = threading.Thread(target=start_slack_listener, daemon=True)
slack_thread.start()
```

### Pattern 3: Button Action Handler — Approve/Reject/Snooze
**What:** Register action handlers that ack immediately, update DB, then update the original Slack message
**When to use:** Every button click from Lauren

```python
# Source: https://docs.slack.dev/tools/bolt-python/concepts/actions/
@app.action("approve_card")
def handle_approve(ack, body, client):
    ack()  # Must ack within 3 seconds
    card_id = int(body["actions"][0]["value"])
    # Update DB state
    asyncio.run(card_repo.set_review_state(card_id, "approved"))
    # Update the message in place (remove buttons, show confirmed state)
    client.chat_update(
        channel=body["container"]["channel_id"],
        ts=body["container"]["message_ts"],
        blocks=build_confirmed_card_blocks(card_id, "approved"),
        text="Signal approved",
    )

@app.action("snooze_card")
def handle_snooze(ack, body, client):
    ack()
    card_id = int(body["actions"][0]["value"])
    asyncio.run(card_repo.snooze_card(card_id, days=30))
    client.chat_update(
        channel=body["container"]["channel_id"],
        ts=body["container"]["message_ts"],
        blocks=build_confirmed_card_blocks(card_id, "snoozed"),
        text="Signal snoozed for 30 days",
    )
```

### Pattern 4: Block Kit Signal Card Structure
**What:** Block Kit message structure for a scored signal card
**When to use:** Delivering each card to Lauren's Slack channel

```python
# Source: https://api.slack.com/block-kit/building
def build_signal_card_blocks(card: SignalCard, score: RubricScore) -> list[dict]:
    top_label = score.top_dimension.replace("_", " ").title()
    score_line = f"{score.composite_score:.1f} — strong {top_label.lower()}"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{card.url}|{card.title}>*\n{score_line}\n_{card.source_name} · Tier {card.tier}_",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": "approve_card",
                    "value": str(card.id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": "reject_card",
                    "value": str(card.id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Snooze 30d"},
                    "action_id": "snooze_card",
                    "value": str(card.id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Details"},
                    "action_id": "details_card",
                    "value": str(card.id),
                },
            ],
        },
        {"type": "divider"},
    ]
```

### Pattern 5: Slash Command — `/watchman add-source`
**What:** Register a slash command handler that validates input and adds a source to sources.yaml
**When to use:** Lauren invokes `/watchman add-source <url> [tier]` from Slack

```python
# Source: https://docs.slack.dev/tools/bolt-python/reference/
@app.command("/watchman")
def handle_watchman_command(ack, say, command):
    ack()
    text = command.get("text", "").strip()
    if text.startswith("add-source"):
        parts = text.split()
        if len(parts) < 2:
            say("Usage: `/watchman add-source <url> [tier]`")
            return
        url = parts[1]
        tier = int(parts[2]) if len(parts) > 2 else 2
        # Validate URL, append to sources.yaml, reload registry
        ...
```

### Pattern 6: Rubric Config YAML
**What:** YAML configuration file for rubric dimension weights
**When to use:** Load at startup, pass to scorer

```yaml
# src/watchman/config/rubric.yaml
rubric:
  dimensions:
    taxonomy_fit:
      weight: 0.35
      description: "Does the signal fit IcebreakerAI taxonomy (AI tools, APIs, capabilities)?"
    novel_capability:
      weight: 0.30
      description: "Does it represent a meaningfully new capability or update?"
    adoption_traction:
      weight: 0.20
      description: "Evidence of real adoption, launches, or user growth?"
    credibility:
      weight: 0.15
      description: "Is the source credible and the signal verifiable?"
  score_scale: 10   # 0-10
  daily_cap_min: 3
  daily_cap_max: 7
  daily_cap_target: 5  # Select top N by composite score
```

### Anti-Patterns to Avoid
- **Calling Haiku synchronously in the Bolt action handler:** Action handlers must ack within 3 seconds. If scoring is triggered by button click, do the work async after ack. However, scoring should run as a pipeline step, not in the action handler at all.
- **Blocking main thread with `handler.start()`:** `SocketModeHandler.start()` blocks forever; always run in a daemon thread or the scheduler will never start.
- **Storing score breakdown as multiple columns:** Use a single `score_breakdown` JSON TEXT column; Haiku's output is a nested object and flat columns would require schema changes per rubric revision.
- **Using raw `slack-sdk` WebClient for interactive features:** `slack-sdk` alone cannot receive button click payloads. Bolt is required to register action listeners.
- **Registering one `@app.action` per card ID:** Action IDs should be generic (`approve_card`, `reject_card`) with the card ID embedded in the button's `value` field.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema enforcement from LLM | Custom retry/parse loop | `output_config.format` with `json_schema` type | Guaranteed valid JSON via constrained decoding; no retries needed |
| Interactive button payload routing | Custom HTTP endpoint + payload parser | `slack-bolt` `@app.action()` | Bolt handles request verification, acking, routing, and error recovery |
| Slack request verification (signing secret) | Custom HMAC verification | Bolt verifies automatically using `SLACK_SIGNING_SECRET` | Cryptographic verification of every inbound payload is required |
| Socket connection management | Custom WebSocket client | Bolt's `SocketModeHandler` | Handles reconnection, heartbeats, and connection lifecycle |

**Key insight:** Bolt for Python is the standard for Slack apps with interactivity. The raw `slack-sdk` WebClient is for outbound-only integrations (like the existing health alerter); anything with button clicks or slash commands requires Bolt.

## Common Pitfalls

### Pitfall 1: Action Handler Timeout (3-Second Rule)
**What goes wrong:** Bolt action handlers must call `ack()` within 3 seconds or Slack will show "That didn't work" error. If DB updates or LLM calls happen before `ack()`, timeouts occur.
**Why it happens:** Sync DB operations or accidental blocking calls delay ack.
**How to avoid:** Call `ack()` as the first line. Do all DB updates and message updates after.
**Warning signs:** Lauren sees "That didn't work" in Slack after clicking a button.

### Pitfall 2: `asyncio.run()` in Bolt Action Handlers
**What goes wrong:** Bolt sync handlers run in threads. Calling `asyncio.run()` from within a Bolt action handler that's already in a thread creates a new event loop — this works but can cause issues if there's already a running loop in that thread.
**Why it happens:** The existing codebase is async (aiosqlite), but Bolt sync handlers are not async.
**How to avoid:** Either (a) use `asyncio.run()` in each action handler (creates a new loop per call — safe in Bolt's thread pool), or (b) create a dedicated sync wrapper for DB operations. Option (a) is simpler given the low call frequency.
**Warning signs:** `RuntimeError: This event loop is already running` in Bolt action handlers.

### Pitfall 3: Socket Mode Requires App-Level Token
**What goes wrong:** Socket Mode requires an App-level token (`xapp-...`), distinct from the Bot token (`xoxb-...`). Using a bot token for the socket handler raises `slack_sdk.errors.SlackApiError`.
**Why it happens:** Two different credentials are needed: bot token for API calls, app token for socket connection.
**How to avoid:** Set both `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` environment variables. Document this in setup notes.
**Warning signs:** `invalid_auth` error on `SocketModeHandler` initialization.

### Pitfall 4: Daily Cap Selection Strategy
**What goes wrong:** If all signals score similarly, the cap selects arbitrarily. If scoring is too lenient, Lauren sees only marginal signals.
**Why it happens:** Haiku needs a rubric prompt specific enough to discriminate quality.
**How to avoid:** Use tier as a tiebreaker (Tier 1 signals rank above Tier 2 at equal scores). Cap selects top N by `composite_score DESC, tier ASC`. Test the rubric prompt with real sample signals before finalizing.
**Warning signs:** Lauren repeatedly rejects all 5 cards — signals are low quality despite high scores.

### Pitfall 5: Snooze Re-queue on Restart
**What goes wrong:** Snooze re-queue relies on a scheduled job checking `snooze_until <= now`. If the process restarts, previously snoozed cards that expired while offline are re-queued on next run — but only if the scheduler job runs. If the daily delivery job only runs once, expired snoozes silently stay snoozed.
**Why it happens:** The scheduler job is the only trigger for snooze expiry.
**How to avoid:** The daily delivery job should include snoozed cards with `snooze_until <= today` in its candidate pool. This ensures re-queued cards appear on the next daily run after expiry.
**Warning signs:** Lauren reports she snoozed a card 31+ days ago but never saw it re-appear.

### Pitfall 6: Block Kit `chat_update` Removes Blocks If Not Provided
**What goes wrong:** Calling `client.chat_update()` with only `text=` removes all blocks, showing a plain text message instead of a formatted confirmation.
**Why it happens:** `chat_update` treats `blocks` as authoritative; omitting `blocks` clears them.
**How to avoid:** Always pass `blocks=` to `chat_update`, even for confirmed state (show a stripped-down confirmation card without buttons).

## Code Examples

Verified patterns from official sources:

### Claude Haiku Structured Output (Python SDK)
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-haiku-4-5-20251001",  # exact model ID
    max_tokens=512,
    messages=[{"role": "user", "content": prompt}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "taxonomy_fit": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "number"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["score", "rationale"],
                        "additionalProperties": False,
                    },
                    # ... other dimensions
                    "composite_score": {"type": "number"},
                    "top_dimension": {"type": "string"},
                },
                "required": [
                    "taxonomy_fit",
                    "novel_capability",
                    "adoption_traction",
                    "credibility",
                    "composite_score",
                    "top_dimension",
                ],
                "additionalProperties": False,
            },
        }
    },
)
result = json.loads(response.content[0].text)
```

### Bolt App + Socket Mode Thread
```python
# Source: https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/
import threading
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

def create_slack_app() -> App:
    return App(token=os.environ["SLACK_BOT_TOKEN"])

def start_socket_mode(app: App) -> threading.Thread:
    def run():
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        handler.start()
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
```

### `chat_update` After Button Action
```python
# Source: https://docs.slack.dev/tools/bolt-python/reference/
@app.action("approve_card")
def handle_approve(ack, body, client):
    ack()
    card_id = int(body["actions"][0]["value"])
    channel_id = body["container"]["channel_id"]
    message_ts = body["container"]["message_ts"]
    # Update DB
    asyncio.run(update_card_state(card_id, "approved"))
    # Replace blocks with confirmed state (no buttons)
    client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=[{
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Approved"},
        }],
        text="Signal approved",
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `output_format` beta parameter | `output_config.format` (GA) | Dec 2025 | No beta header required; `output_format` still works in transition |
| Claude Haiku 3 (`claude-3-haiku-20240307`) | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) | 2025 | Haiku 3 deprecated; will retire April 2026 |
| slack-sdk-only for interactive apps | Bolt for Python | Standard since 2021 | Bolt handles interaction payload routing, signing, ack |

**Deprecated/outdated:**
- `output_format` parameter: Still works but replaced by `output_config.format`; do not use in new code
- `claude-3-haiku-20240307`: Deprecated; retires April 2026; use `claude-haiku-4-5-20251001`
- Old beta header `structured-outputs-2025-11-13`: No longer required; do not include it

## Database Schema Changes Required

Phase 2 needs new columns on the `cards` table and a new migration. The existing `init_db` creates the table without these columns; Phase 2 must add them via `ALTER TABLE` or by dropping and recreating (SQLite limitation: ALTER TABLE can only ADD columns).

**New columns for `cards` table:**
```sql
ALTER TABLE cards ADD COLUMN relevance_score REAL;
ALTER TABLE cards ADD COLUMN score_breakdown TEXT;   -- JSON: {taxonomy_fit, novel_capability, ...}
ALTER TABLE cards ADD COLUMN top_dimension TEXT;
ALTER TABLE cards ADD COLUMN review_state TEXT DEFAULT 'pending'
    CHECK(review_state IN ('pending', 'approved', 'rejected', 'snoozed'));
ALTER TABLE cards ADD COLUMN reviewed_at TEXT;
ALTER TABLE cards ADD COLUMN snooze_until TEXT;      -- ISO datetime
ALTER TABLE cards ADD COLUMN slack_message_ts TEXT;  -- for chat_update
ALTER TABLE cards ADD COLUMN slack_channel_id TEXT;
```

**New index:**
```sql
CREATE INDEX idx_cards_review_state ON cards(review_state);
CREATE INDEX idx_cards_snooze_until ON cards(snooze_until);
```

## Slack App Setup Requirements (Not Code)

Two credentials are required before any code runs:
1. **`SLACK_BOT_TOKEN`** (`xoxb-...`): Bot OAuth token with scopes `chat:write`, `channels:read`, `commands`
2. **`SLACK_APP_TOKEN`** (`xapp-...`): App-level token with scope `connections:write` (required for Socket Mode)

Slack App configuration steps:
- Enable Socket Mode in App Settings
- Create slash command `/watchman`
- Enable Interactivity (for button payloads)
- Install app to workspace
- Set `SLACK_CHANNEL_ID` (Lauren's review channel) in environment

These steps are prerequisites that must be completed before the Phase 2 code runs.

## Open Questions

1. **Scoring trigger timing**
   - What we know: Scoring should happen before delivery; normalizer creates cards; APScheduler runs collection periodically
   - What's unclear: Should scoring run immediately after normalization (as part of the same APScheduler job), or as a separate scheduled step?
   - Recommendation: Run scoring as a post-normalization step in the same processing job. This avoids a second job and ensures cards are scored before the daily delivery job runs.

2. **Score threshold for daily cap**
   - What we know: Daily cap is 3-7 cards; rubric weights are in YAML; score is 0-10
   - What's unclear: Exact threshold logic — hard minimum score cutoff? Or always top N regardless of absolute score?
   - Recommendation: Always select top N (no hard cutoff). Include `seen_count > 1` as a boost signal. Lauren's rejections over time will inform calibration of weights.

3. **Handling days with fewer than 3 scored signals**
   - What we know: Cap is 3-7; some days may have fewer new signals
   - What's unclear: Should the delivery job skip delivery if < 3 signals, or deliver whatever is available?
   - Recommendation: Deliver whatever is available (even 1-2 cards), include the "Showing X of Y" footer. Don't skip delivery silently.

## Sources

### Primary (HIGH confidence)
- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) — Claude Haiku 4.5 model ID, pricing, capabilities
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — `output_config.format` API, Python SDK examples, GA status
- [Bolt for Python Reference](https://docs.slack.dev/tools/bolt-python/reference/) — `app.action()`, `app.command()`, ack/say/client patterns
- [Bolt Python Socket Mode](https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/) — SocketModeHandler setup, env var requirements
- [Bolt Python Actions](https://docs.slack.dev/tools/bolt-python/concepts/actions/) — action listener patterns, body structure

### Secondary (MEDIUM confidence)
- [PyPI: anthropic 0.80.0](https://pypi.org/project/anthropic/) — version confirmed as 0.80 (Feb 2026)
- [PyPI: slack-bolt 1.27.0](https://pypi.org/project/slack-bolt/) — version confirmed (Nov 2025)
- [Slack Block Kit](https://docs.slack.dev/block-kit/) — block structure for signal cards
- [Creating Interactive Messages](https://docs.slack.dev/messaging/creating-interactive-messages/) — response_url, interaction payload structure

### Tertiary (LOW confidence)
- None — all critical claims verified with official sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from PyPI, APIs confirmed from official docs
- Architecture: HIGH — patterns from official Bolt and Anthropic docs
- Pitfalls: HIGH — timeout rule from official Slack docs; other pitfalls from known SDK behavior
- Database schema: HIGH — based on direct reading of existing schema + SQLite constraints

**Research date:** 2026-02-24
**Valid until:** 2026-08-24 (stable libraries; check Haiku model ID before use if >6 months)
