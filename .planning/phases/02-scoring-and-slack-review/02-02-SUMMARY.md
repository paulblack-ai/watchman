---
phase: 02-scoring-and-slack-review
plan: "02"
subsystem: slack
tags: [slack, bolt, block-kit, review-queue, socket-mode, delivery, slash-commands]
dependency_graph:
  requires: [02-01]
  provides: [slack-review-interface, daily-delivery-job, watchman-slash-command]
  affects: [main.py, scheduler/jobs.py]
tech_stack:
  added: [slack-bolt>=1.18]
  patterns: [bolt-app, socket-mode, block-kit, cron-job, asyncio-sync-bridge]
key_files:
  created:
    - src/watchman/slack/__init__.py
    - src/watchman/slack/app.py
    - src/watchman/slack/blocks.py
    - src/watchman/slack/actions.py
    - src/watchman/slack/commands.py
    - src/watchman/slack/delivery.py
    - tests/test_slack_blocks.py
  modified:
    - src/watchman/main.py
    - src/watchman/scheduler/jobs.py
    - pyproject.toml
decisions:
  - "Slack Bolt with Socket Mode -- no public webhook needed, runs behind firewall"
  - "Daemon thread for Socket Mode handler -- exits cleanly with main process"
  - "Graceful degradation -- missing Slack tokens disable Slack features but scheduler continues"
  - "asyncio.run() bridge in action handlers -- APScheduler and Bolt run in threads, not async context"
  - "card_id as button value -- clean integer round-trip for DB lookup in action handlers"
metrics:
  duration_minutes: 4
  completed: "2026-02-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 3
---

# Phase 2 Plan 02: Slack Review Interface Summary

**One-liner:** Slack Bolt review interface with Block Kit signal cards, approve/reject/snooze/details buttons, Socket Mode, daily delivery job, and /watchman add-source slash command.

## What Was Built

Complete Slack integration module enabling Lauren to receive curated, scored signal cards in Slack and act on them with one click. The system posts Block Kit cards with composite score + top dimension label, supports four review actions (approve, reject, snooze 30 days, details), delivers a daily capped digest at 9 AM, and provides a /watchman add-source slash command for adding new sources without editing YAML manually.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Slack module -- Bolt app, blocks, actions, delivery, commands | 6c72010 | slack/__init__.py, app.py, blocks.py, actions.py, commands.py, delivery.py, scheduler/jobs.py, tests/test_slack_blocks.py |
| 2 | Main entry point integration -- Slack + scoring wired into startup | 46e5ddb | main.py |
| 3 | Verify Slack integration end-to-end | (checkpoint -- auto-approved) | none |

## Architecture

```
main.py
  --> slack/app.py: create_slack_app() + start_socket_mode() (daemon thread)
  --> scheduler/jobs.py: schedule_delivery_job() (CronTrigger 09:00 AM)

slack/app.py
  --> slack/actions.py: register_actions() -- approve/reject/snooze/details
  --> slack/commands.py: register_commands() -- /watchman add-source

slack/delivery.py: deliver_daily_review()
  --> storage/repositories.py: CardRepository.find_top_scored_today()
  --> storage/repositories.py: CardRepository.count_scored_today()
  --> slack/blocks.py: build_signal_card_blocks(), build_review_footer()
  --> slack_sdk.WebClient: chat_postMessage()

slack/actions.py action handlers
  --> storage/repositories.py: set_review_state(), snooze_card()
  --> slack/blocks.py: build_confirmed_card_blocks(), build_details_blocks()
  --> slack_sdk (via Bolt client): chat_update(), chat_postEphemeral()
```

## Key Design Decisions

1. **Slack Bolt with Socket Mode** -- No public webhook URL needed. Bolt's Socket Mode uses a persistent WebSocket connection, suitable for private deployments running locally or on a server behind a firewall.

2. **Daemon thread for Socket Mode** -- The Socket Mode handler runs in a `daemon=True` thread so the process exits cleanly when the main loop is interrupted (Ctrl+C), with no orphaned threads.

3. **Graceful degradation when Slack tokens are missing** -- `main.py` checks for `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` before starting Slack. If either is missing, it logs a warning and continues without Slack. The scoring scheduler still runs.

4. **asyncio.run() bridge in action handlers** -- Bolt action handlers run in synchronous thread pool callbacks (not an async event loop). CardRepository methods are async, so `asyncio.run()` is used to bridge them. This is the same pattern used in APScheduler jobs.

5. **card_id as button value** -- Each button stores the card's integer ID as its `value`. This enables clean DB lookup in action handlers without encoding extra state.

6. **Daily delivery saves slack_message_ts per card** -- After posting each card, delivery stores the Slack message timestamp and channel ID on the card record. This enables action handlers to call `chat_update()` to replace the card in-place with the confirmed state.

## Files Created

### `src/watchman/slack/__init__.py`
Empty package marker.

### `src/watchman/slack/app.py`
- `create_slack_app()`: Creates Bolt App, registers actions and commands, returns app
- `start_socket_mode(app)`: Starts SocketModeHandler in daemon thread, returns thread

### `src/watchman/slack/blocks.py`
- `build_signal_card_blocks(card, score)`: 4 blocks -- section (title + score line), context (source/tier/date), actions (4 buttons), divider
- `build_confirmed_card_blocks(card, action)`: 2 blocks -- section with action result, divider. No buttons.
- `build_details_blocks(card, score)`: 3 blocks -- header, 4-dimension breakdown, composite score context
- `build_review_footer(showing, total)`: 1 context block -- "Showing X of Y signals today"

### `src/watchman/slack/actions.py`
- `register_actions(app)`: Registers approve_card, reject_card, snooze_card, details_card handlers
- Each handler: ack() first, parse card_id from action value, call async DB method via asyncio.run(), call Bolt client to update/post message

### `src/watchman/slack/commands.py`
- `register_commands(app)`: Registers /watchman slash command handler
- Handles: add-source (URL + tier validation, type detection, YAML append), help

### `src/watchman/slack/delivery.py`
- `deliver_daily_review(db_path, rubric_path)`: Async delivery function
- `deliver_daily_review_sync(db_path, rubric_path)`: Sync wrapper for APScheduler

### `tests/test_slack_blocks.py`
28 tests covering all four Block Kit builder functions. All pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed composite score extraction in test**
- **Found during:** Task 1 test run
- **Issue:** `test_includes_composite_score` was building `full_text` from block text fields only, missing context block element text (where composite score lives)
- **Fix:** Updated extraction to also iterate over block `elements[]` for context blocks
- **Files modified:** tests/test_slack_blocks.py
- **Commit:** 6c72010

**2. [Rule 3 - Blocking] Added slack-bolt to pyproject.toml**
- **Found during:** Task 1 setup
- **Issue:** `slack-bolt` was not in project dependencies; only `slack-sdk` was present
- **Fix:** Installed `slack-bolt` and added `slack-bolt>=1.18` to pyproject.toml
- **Files modified:** pyproject.toml
- **Commit:** 6c72010

## Self-Check: PASSED

All created files exist on disk. Both task commits (6c72010, 46e5ddb) verified in git log. All 28 Block Kit tests pass.
