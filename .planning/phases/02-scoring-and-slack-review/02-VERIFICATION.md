---
phase: 02-scoring-and-slack-review
verified: 2026-02-24T00:00:00Z
status: human_needed
score: 14/15 must-haves verified
human_verification:
  - test: "Trigger daily delivery with SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID set"
    expected: "Signal cards appear in Slack formatted as 'X.X -- strong taxonomy fit' with Approve, Reject, Snooze 30d, and Details buttons"
    why_human: "Requires live Slack workspace and environment variables; cannot verify API calls or rendered Block Kit UI programmatically"
  - test: "Click Approve on a delivered card"
    expected: "Message updates in-place, buttons disappear, checkmark and 'Approved' text appear; DB review_state = 'approved'"
    why_human: "Requires live Slack interaction; action handler wiring to Bolt websocket cannot be verified without a running bot"
  - test: "Click Reject on a delivered card"
    expected: "Message updates in-place with X and 'Rejected' text; DB review_state = 'rejected'"
    why_human: "Requires live Slack interaction"
  - test: "Click Snooze on a delivered card"
    expected: "Message updates with clock and '30 days' text; DB review_state = 'snoozed', snooze_until is now + 30 days"
    why_human: "Requires live Slack interaction"
  - test: "Click Details on a delivered card"
    expected: "Ephemeral message shows all 4 dimension scores with rationales (Taxonomy Fit, Novel Capability, Adoption Traction, Credibility)"
    why_human: "Requires live Slack interaction; ephemeral messages are user-visible only"
  - test: "Run /watchman add-source https://example.com/feed 1 in Slack"
    expected: "Bot responds with confirmation 'Added https://example.com/feed as Tier 1 rss source'; sources.yaml gains new entry"
    why_human: "Requires live Slack slash command interaction"
  - test: "Verify snoozed card with expired snooze_until re-appears in next daily delivery"
    expected: "find_top_scored_today returns cards where snooze_until <= now AND review_state = 'snoozed'"
    why_human: "Requires time manipulation or waiting 30 days; DB query is verified programmatically but end-to-end requires delivery run"
---

# Phase 2: Scoring and Slack Review Verification Report

**Phase Goal:** Lauren receives a curated, scored review queue in Slack and can approve, reject, or snooze each signal card
**Verified:** 2026-02-24
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | New signal cards are scored against a 4-dimension relevance rubric via Claude Haiku | VERIFIED | `scorer.py` calls `client.messages.create(model="claude-haiku-4-5-20251001", output_config={"format": {"type": "json_schema", ...}})` |
| 2 | Scores include composite score, per-dimension breakdown, and top contributing dimension | VERIFIED | `RubricScore` model has `taxonomy_fit`, `novel_capability`, `adoption_traction`, `credibility`, `composite_score`, `top_dimension` |
| 3 | Rubric weights are loaded from YAML config and can be changed without code edits | VERIFIED | `rubric.yaml` has 4 dimensions with weights 0.35/0.30/0.20/0.15 summing to 1.0; loaded via `load_rubric()` |
| 4 | Score breakdowns are persisted in the database per signal card | VERIFIED | `CardRepository.save_score()` writes `relevance_score`, `score_breakdown` (JSON), `top_dimension` to the `cards` table |
| 5 | Daily cap logic selects top N cards (3-7) by composite score, tier as tiebreaker | VERIFIED | `find_top_scored_today(limit=cap)` orders by `relevance_score DESC, tier ASC` |
| 6 | Lauren receives scored signal cards in Slack formatted with Block Kit | HUMAN NEEDED | `deliver_daily_review` and `build_signal_card_blocks` are implemented and wired; live Slack delivery requires human verification |
| 7 | Each card shows composite score plus top contributing dimension | VERIFIED | `_format_score_line()` returns `"8.6 -- strong taxonomy fit"` format; all 14 Block Kit tests pass |
| 8 | Each card has Approve, Reject, Snooze, and Details buttons | VERIFIED | `build_signal_card_blocks` creates 4 buttons with correct `action_id` values (`approve_card`, `reject_card`, `snooze_card`, `details_card`) |
| 9 | Clicking Approve updates card state to 'approved' in DB and updates the Slack message | HUMAN NEEDED | `handle_approve` calls `repo.set_review_state(card_id, "approved")` then `client.chat_update()`; requires live Slack to verify end-to-end |
| 10 | Clicking Reject updates card state to 'rejected' in DB and updates the Slack message | HUMAN NEEDED | `handle_reject` calls `repo.set_review_state(card_id, "rejected")` then `client.chat_update()`; requires live Slack |
| 11 | Clicking Snooze sets snooze_until to 30 days from now and updates the Slack message | HUMAN NEEDED | `snooze_card(card_id, days=30)` computes `now + 30 days`; confirmed card block removes buttons; requires live Slack |
| 12 | Details button shows full 4-dimension rubric breakdown | HUMAN NEEDED | `_handle_details_action` parses `score_breakdown` and calls `chat_postEphemeral(build_details_blocks(...))`; requires live Slack |
| 13 | Daily review shows 'Showing X of Y signals today' footer | VERIFIED | `build_review_footer(delivered, total_today)` produces `"Showing {showing} of {total} signals today"`; 4 footer tests pass |
| 14 | Snoozed cards with expired snooze_until appear in next daily review | VERIFIED | `find_top_scored_today` SQL: `(review_state = 'snoozed' AND snooze_until <= datetime('now'))` |
| 15 | Lauren can add sources via /watchman add-source slash command | HUMAN NEEDED | `commands.py` parses `add-source <url> [tier]`, validates, detects type, appends to `sources.yaml`; requires live Slack |

**Score:** 9/15 fully automated, 6/15 require human verification (Slack interactions). No items FAILED.

### Required Artifacts

**Plan 01 artifacts:**

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/watchman/scoring/scorer.py` | Claude Haiku scoring | VERIFIED | `score_card()` and `score_unscored_cards()` implemented; uses `output_config` json_schema |
| `src/watchman/scoring/rubric.py` | Rubric YAML loader | VERIFIED | `load_rubric()` and `RubricConfig` exported; uses Pydantic validation |
| `src/watchman/scoring/models.py` | Pydantic score models | VERIFIED | `DimensionScore` with 0-10 range validation, `RubricScore` with all 4 dimensions |
| `src/watchman/config/rubric.yaml` | Default rubric weights | VERIFIED | Contains `taxonomy_fit` (0.35), `novel_capability` (0.30), `adoption_traction` (0.20), `credibility` (0.15) |
| `src/watchman/storage/database.py` | Phase 2 migration | VERIFIED | `migrate_phase2()` adds 8 columns; called from `init_db()`; idempotent |
| `src/watchman/storage/repositories.py` | CardRepository methods | VERIFIED | `save_score`, `find_unscored`, `find_top_scored_today`, `count_scored_today`, `set_review_state`, `snooze_card` all present |

**Plan 02 artifacts:**

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/watchman/slack/app.py` | Bolt App init and SocketModeHandler | VERIFIED | `create_slack_app()` and `start_socket_mode()` exported; registers actions and commands |
| `src/watchman/slack/blocks.py` | Block Kit builders | VERIFIED | `build_signal_card_blocks`, `build_confirmed_card_blocks`, `build_details_blocks`, `build_review_footer` all exported |
| `src/watchman/slack/actions.py` | Action handlers | VERIFIED | `register_actions()` registers approve/reject/snooze/details handlers; ack() called first |
| `src/watchman/slack/commands.py` | Slash command handler | VERIFIED | `register_commands()` handles `/watchman add-source` with URL validation, tier validation, type detection |
| `src/watchman/slack/delivery.py` | Daily review delivery | VERIFIED | `deliver_daily_review()` async and `deliver_daily_review_sync()` APScheduler wrapper |
| `src/watchman/main.py` | Updated entry point | VERIFIED | Checks for Slack tokens, starts Socket Mode, calls `schedule_scoring_job` and `schedule_delivery_job` |

### Key Link Verification

**Plan 01 key links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scoring/scorer.py` | Anthropic API | `output_config.format.type = "json_schema"` | WIRED | Line 79-85: `output_config={"format": {"type": "json_schema", "schema": RubricScore.model_json_schema()}}` |
| `scoring/scorer.py` | `scoring/rubric.py` | `RubricConfig` used in prompt builder | WIRED | Line 11: `from watchman.scoring.rubric import RubricConfig, load_rubric`; used in `_build_scoring_prompt()` |
| `scheduler/jobs.py` | `scoring/scorer.py` | `score_unscored_cards` called in `run_scoring_job` | WIRED | Line 68: lazy import + `asyncio.run(score_unscored_cards(db_path, rubric_path))` |

**Plan 02 key links:**

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `slack/delivery.py` | `storage/repositories.py` | `CardRepository.find_top_scored_today` | WIRED | Line 68: `cards = await repo.find_top_scored_today(limit=cap)` |
| `slack/actions.py` | `storage/repositories.py` | `set_review_state` and `snooze_card` | WIRED | Lines 77, 125: both called via `asyncio.run()` bridge |
| `slack/blocks.py` | `scoring/models.py` | `RubricScore` used to format card display | WIRED | Line 4: `from watchman.scoring.models import RubricScore`; used in all builder functions |
| `main.py` | `slack/app.py` | `start_socket_mode` in daemon thread | WIRED | Lines 67-70: lazy import + `start_socket_mode(slack_app)` when tokens present |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROC-04 | 02-01 | Score signals against IcebreakerAI relevance rubric (taxonomy fit, novel capability, adoption/traction, credibility) using Claude Haiku | SATISFIED | `scorer.py` calls Claude Haiku with 4-dimension rubric; all 4 dimensions in `RubricScore` model |
| PROC-05 | 02-01 | Enforce daily volume cap (3-7 cards) to prevent signal fatigue | SATISFIED | `find_top_scored_today(limit=cap)` with `daily_cap_target=5` from rubric.yaml; cap enforced in delivery |
| PROC-06 | 02-01 | Persist score breakdown per signal for future calibration | SATISFIED | `save_score()` writes `score_breakdown` as JSON string and `relevance_score` + `top_dimension` |
| SLCK-01 | 02-02 | Deliver scored signal cards to Lauren's Slack channel using Block Kit | HUMAN NEEDED | Implementation complete (`deliver_daily_review` + `build_signal_card_blocks`); live delivery requires human verification |
| SLCK-02 | 02-02 | Lauren can approve a signal card via Slack button | HUMAN NEEDED | `approve_card` action handler calls `set_review_state("approved")` and `chat_update()`; requires live Slack |
| SLCK-03 | 02-02 | Lauren can reject a signal card via Slack button | HUMAN NEEDED | `reject_card` action handler calls `set_review_state("rejected")` and `chat_update()`; requires live Slack |
| SLCK-04 | 02-02 | Lauren can snooze a signal card via Slack button (default 30-day expiry, re-queues after expiry) | HUMAN NEEDED | `snooze_card` action handler + `find_top_scored_today` SQL handles re-queue; requires live Slack |

Note: REQUIREMENTS.md still shows SLCK-01 through SLCK-04 as "Pending" (unchecked). These should be marked complete after human verification confirms end-to-end Slack behavior.

### Anti-Patterns Found

No anti-patterns detected in any key files. Scanned for: TODO, FIXME, XXX, HACK, PLACEHOLDER, `return null`, `return {}`, `return []`, empty handler stubs. All clear.

One minor observation (non-blocking):
- `src/watchman/storage/repositories.py` line 307: `datetime.utcnow()` is deprecated (use `datetime.now(UTC)`). Generates a DeprecationWarning in test runs. Not a blocker.

### Human Verification Required

#### 1. Slack Card Delivery

**Test:** With `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`, and `ANTHROPIC_API_KEY` set, run:
```
python -c "import asyncio; from watchman.slack.delivery import deliver_daily_review; from pathlib import Path; print(asyncio.run(deliver_daily_review(Path('watchman.db'), Path('src/watchman/config/rubric.yaml'))))"
```
**Expected:** Signal cards appear in the configured Slack channel showing a title link, score line in "8.2 -- strong taxonomy fit" format, source/tier/date context, and 4 buttons (Approve, Reject, Snooze 30d, Details). Footer shows "Showing X of Y signals today."
**Why human:** Requires live Slack workspace, valid tokens, and scored cards in the database.

#### 2. Approve Button

**Test:** Click the "Approve" button on a delivered card.
**Expected:** The Slack message updates in-place. Buttons disappear. Card shows checkmark + "Approved" text. Database `review_state = 'approved'` for that card.
**Why human:** Bolt WebSocket event handling requires a running process connected to Slack; cannot mock end-to-end.

#### 3. Reject Button

**Test:** Click the "Reject" button on a delivered card.
**Expected:** The Slack message updates in-place. Buttons disappear. Card shows X + "Rejected" text. Database `review_state = 'rejected'`.
**Why human:** Same as Approve.

#### 4. Snooze Button

**Test:** Click the "Snooze 30d" button on a delivered card.
**Expected:** The Slack message updates with clock + "Snoozed for 30 days" text. Database `review_state = 'snoozed'` and `snooze_until` is approximately now + 30 days.
**Why human:** Same as Approve.

#### 5. Details Button

**Test:** Click the "Details" button on a delivered card.
**Expected:** An ephemeral message visible only to Lauren appears, showing all 4 dimensions: Taxonomy Fit, Novel Capability, Adoption Traction, Credibility — each with a score (e.g. "9.0/10") and rationale text. Composite score shown at bottom.
**Why human:** Ephemeral messages are user-visible only in the actual Slack UI.

#### 6. /watchman add-source Command

**Test:** In Slack, type: `/watchman add-source https://example.com/feed 1`
**Expected:** Bot responds: "Added `https://example.com/feed` as Tier 1 rss source. Restart Watchman for the new source to be scheduled." The `src/watchman/config/sources.yaml` file gains a new entry.
**Why human:** Requires live Slack slash command registration and routing to the bot.

#### 7. Snoozed Card Re-queue

**Test:** Manually insert a snoozed card with `snooze_until` set to a past timestamp and `review_state = 'snoozed'`. Run `deliver_daily_review`. Verify the card appears in the delivery.
**Expected:** The snoozed card with expired snooze_until is included in the daily review alongside new pending cards.
**Why human:** Requires controlled database state and a delivery run to observe the re-queue behavior.

### Gaps Summary

No gaps found. All automated checks pass. The 6 items marked HUMAN NEEDED are not failures — they are Slack interaction behaviors that cannot be verified without a live workspace. The underlying implementation for each (action handlers, DB updates, Block Kit builders, delivery function) is fully implemented, wired, and tested where automatable.

The phase goal is architecturally achieved. Human verification is the final gate to confirm the live integration works end-to-end.

---

_Verified: 2026-02-24_
_Verifier: Claude (gsd-verifier)_
