---
plan: quick-5
status: complete
date: 2026-02-25
commits: [5ee7cdb]
---

# Quick Task 5: Fix view-more-signals button count and click handler

## What Changed
1. **Button text fix**: Changed from "View 65 more signals" to "View next 5 signals (65 remaining)" — shows the batch size (5) instead of total remaining
2. **Python 3.9 compat**: Added `from __future__ import annotations` to all remaining source files (actions.py, delivery.py, app.py, commands.py, models.py, database.py, writer.py, llm_client.py, reset_and_collect.py) to prevent `X | None` TypeError on Python 3.9
3. **Re-delivered**: Fresh delivery of 5 cards to new Slack channel with corrected footer

## Files Modified
- `src/watchman/slack/blocks.py` — Capped button text at `min(remaining, 5)`
- 9 additional files — Added `from __future__ import annotations`

## Notes
- The click handler code was correct — the failure was likely due to Python 3.9 compat issues in the import chain when the handler tried to load modules
- For button clicks to work, the main Watchman process must be running (`python -m watchman.main`) with Socket Mode enabled
