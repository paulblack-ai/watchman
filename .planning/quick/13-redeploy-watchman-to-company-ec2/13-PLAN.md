---
phase: quick-13
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: false
requirements: [DEPLOY-01]
must_haves:
  truths:
    - "EC2 has all code changes from tasks 10, 11, and 12 (Notion integration, poller fix, Gemini Flash)"
    - "EC2 .env includes NOTION_TOKEN and NOTION_DATABASE_ID without losing existing vars"
    - "notion-client package is installed in EC2 venv"
    - "systemd watchman.service is running with Notion jobs scheduled"
    - "Watchman can reach Notion API from EC2"
  artifacts:
    - path: "~/watchman/src/watchman/notion/"
      provides: "Notion client, delivery, poller, setup modules on EC2"
    - path: "~/watchman/.env"
      provides: "All env vars including new Notion ones"
  key_links:
    - from: "watchman.main"
      to: "Notion API"
      via: "NOTION_TOKEN env var + notion-client SDK"
      pattern: "notion_enabled.*NOTION_TOKEN"
---

<objective>
Deploy code changes from quick tasks 10-12 to company EC2 instance (13.59.61.76).

Purpose: The EC2 instance is running stale code from task 9 (Slack-only). It needs the Notion integration (task 10), poller select-property fix (task 11), and Gemini Flash scoring swap (task 12).

Output: EC2 running latest Watchman with Notion as primary review surface and Gemini Flash scoring.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/9-migrate-watchman-to-company-ec2-instance/9-SUMMARY.md
@.planning/quick/10-watchman-notion-migration-replace-slack-/10-SUMMARY.md
@.planning/quick/12-swap-watchman-scoring-model-from-haiku-t/12-SUMMARY.md

## EC2 Current State (verified via SSH)

- **SSH alias:** `ssh watchman` connects to 13.59.61.76
- **Python:** 3.11.14
- **Venv path:** ~/watchman/venv/ (NOT .venv — systemd ExecStart uses venv/bin/python)
- **Code path:** ~/watchman/ (installed with pip install -e '.[dev]')
- **No git repo** on EC2 — code was transferred via scp in task 9
- **systemd service file:** /etc/systemd/system/watchman.service
  - ExecStart=/home/ec2-user/watchman/venv/bin/python -m watchman.main
  - Environment=PYTHONPATH=/home/ec2-user/watchman/src
- **Existing .env vars:** SLACK_APP_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SLACK_PAUL_USER_ID, OPENROUTER_API_KEY, WATCHMAN_DB_PATH
- **Missing on EC2:** entire src/watchman/notion/ directory, notion-client package, NOTION_TOKEN, NOTION_DATABASE_ID, updated scorer.py

## Files Changed Since Task 9 (code only)

13 files changed, 1173 insertions(+), 28 deletions(-):
- pyproject.toml (notion-client dep added)
- src/watchman/enrichment/pipeline.py (Notion Gate 2 delivery)
- src/watchman/main.py (Notion-first wiring, ~74 lines changed)
- src/watchman/models/signal_card.py (notion_page_id field)
- src/watchman/notion/__init__.py (new)
- src/watchman/notion/client.py (new, 170 lines)
- src/watchman/notion/delivery.py (new, 345 lines)
- src/watchman/notion/poller.py (new, 305 lines)
- src/watchman/notion/setup.py (new, 109 lines)
- src/watchman/scheduler/jobs.py (Notion delivery + poll jobs)
- src/watchman/scoring/scorer.py (Gemini Flash swap)
- src/watchman/storage/database.py (notion migration)
- src/watchman/storage/repositories.py (3 new CardRepository methods)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Transfer updated code and install dependencies</name>
  <files>EC2: ~/watchman/src/, ~/watchman/pyproject.toml</files>
  <action>
Stop the systemd service before modifying code:
```
ssh watchman "sudo systemctl stop watchman"
```

Transfer all changed source files from local to EC2 using scp. The local project root is /Users/paul/paul/Projects/watchman. Transfer these paths:

1. The entire src/watchman/notion/ directory (new — 5 files):
   ```
   scp -r src/watchman/notion/ watchman:~/watchman/src/watchman/notion/
   ```

2. Modified source files (6 files):
   ```
   scp src/watchman/main.py watchman:~/watchman/src/watchman/main.py
   scp src/watchman/enrichment/pipeline.py watchman:~/watchman/src/watchman/enrichment/pipeline.py
   scp src/watchman/models/signal_card.py watchman:~/watchman/src/watchman/models/signal_card.py
   scp src/watchman/scheduler/jobs.py watchman:~/watchman/src/watchman/scheduler/jobs.py
   scp src/watchman/scoring/scorer.py watchman:~/watchman/src/watchman/scoring/scorer.py
   scp src/watchman/storage/database.py watchman:~/watchman/src/watchman/storage/database.py
   scp src/watchman/storage/repositories.py watchman:~/watchman/src/watchman/storage/repositories.py
   ```

3. Updated pyproject.toml (has notion-client dependency):
   ```
   scp pyproject.toml watchman:~/watchman/pyproject.toml
   ```

After transfer, reinstall the package in the EC2 venv to pick up the new notion-client dependency:
```
ssh watchman "cd ~/watchman && venv/bin/pip install -e '.[dev]'"
```

Verify notion-client is installed:
```
ssh watchman "~/watchman/venv/bin/pip list | grep -i notion"
```
Expected: `notion-client` appears in the list with version >= 2.0.

Also verify all transferred files exist:
```
ssh watchman "ls ~/watchman/src/watchman/notion/client.py ~/watchman/src/watchman/notion/delivery.py ~/watchman/src/watchman/notion/poller.py ~/watchman/src/watchman/notion/setup.py"
```
  </action>
  <verify>
    <automated>ssh watchman "~/watchman/venv/bin/pip list | grep -i notion && ls ~/watchman/src/watchman/notion/client.py ~/watchman/src/watchman/notion/poller.py"</automated>
  </verify>
  <done>All 13 changed files are on EC2, notion-client package installed in venv, service is stopped and ready for env var config.</done>
</task>

<task type="checkpoint:human-action">
  <name>Task 2: Add Notion environment variables to EC2</name>
  <files>EC2: ~/watchman/.env</files>
  <action>
Prompt the user to provide their Notion credentials. The executor needs two values:
1. NOTION_TOKEN — the Notion integration token (starts with `secret_` or `ntn_`)
2. NOTION_DATABASE_ID — the 32-character hex ID of the Watchman Notion database

Once the user provides the values, append them to the EC2 .env file (do NOT overwrite — use >>):
```
ssh watchman "echo 'NOTION_TOKEN=<value>' >> ~/watchman/.env && echo 'NOTION_DATABASE_ID=<value>' >> ~/watchman/.env"
```

Optionally also add WATCHMAN_SCORING_MODEL if user wants to override the default (google/gemini-2.0-flash-001).

Verify the .env has all required vars:
```
ssh watchman "grep -E '^(NOTION_TOKEN|NOTION_DATABASE_ID|OPENROUTER_API_KEY)' ~/watchman/.env | sed 's/=.*/=***/'"
```
Expected: NOTION_TOKEN=***, NOTION_DATABASE_ID=***, OPENROUTER_API_KEY=*** all present.
  </action>
  <verify>
    <automated>ssh watchman "grep -c NOTION_TOKEN ~/watchman/.env && grep -c NOTION_DATABASE_ID ~/watchman/.env"</automated>
  </verify>
  <done>EC2 .env contains NOTION_TOKEN and NOTION_DATABASE_ID alongside all existing env vars (SLACK_*, OPENROUTER_API_KEY, WATCHMAN_DB_PATH).</done>
</task>

<task type="auto">
  <name>Task 3: Restart service and verify Notion connectivity</name>
  <files>EC2: systemd watchman.service</files>
  <action>
Test Notion API connectivity from EC2 before restarting the service:
```
ssh watchman "cd ~/watchman && PYTHONPATH=src venv/bin/python -c \"
from watchman.notion.client import NotionClient
import os
from dotenv import load_dotenv
load_dotenv()
nc = NotionClient()
print('Notion client initialized, token present:', bool(os.environ.get('NOTION_TOKEN')))
print('Database ID:', os.environ.get('NOTION_DATABASE_ID', 'MISSING')[:8] + '...')
\""
```

If connectivity check passes, restart the systemd service:
```
ssh watchman "sudo systemctl start watchman"
```

Wait a few seconds, then verify the service is running and Notion jobs are scheduled:
```
ssh watchman "sudo systemctl status watchman"
```

Check the journal logs for startup confirmation — look for:
- "Review surface: Notion" (confirms Notion mode activated)
- Scheduled jobs include notion-related jobs (deliver-daily-review-notion, poll-notion-status)
- No import errors or missing module errors

```
ssh watchman "journalctl -u watchman --since '1 min ago' --no-pager | head -60"
```

If the service crashes on start, check logs for the specific error:
```
ssh watchman "journalctl -u watchman --since '2 min ago' --no-pager | tail -30"
```

Final verification — confirm the poller is running by watching for a poll cycle in the logs (the poller runs every 45 seconds):
```
ssh watchman "journalctl -u watchman -f --no-pager"
```
Watch for about 60 seconds for a "poll_notion_status" log entry, then Ctrl-C.
  </action>
  <verify>
    <automated>ssh watchman "systemctl is-active watchman && journalctl -u watchman --since '2 min ago' --no-pager | grep -i 'notion\|Review surface'"</automated>
  </verify>
  <done>systemd watchman.service is active (running), logs show "Review surface: Notion", Notion delivery and poll jobs are scheduled, no errors in startup logs.</done>
</task>

</tasks>

<verification>
All deployment checks pass:
- `ssh watchman "systemctl is-active watchman"` returns "active"
- `ssh watchman "journalctl -u watchman --since '5 min ago' --no-pager | grep -i notion"` shows Notion-related log entries
- `ssh watchman "grep NOTION_TOKEN ~/watchman/.env"` confirms env var present
- `ssh watchman "~/watchman/venv/bin/pip list | grep notion"` shows notion-client installed
</verification>

<success_criteria>
1. EC2 running latest code with Notion integration, poller fix, and Gemini Flash scoring
2. .env has NOTION_TOKEN and NOTION_DATABASE_ID alongside existing vars
3. systemd service is active and stable (no crash loops)
4. Logs confirm "Review surface: Notion" and Notion jobs are scheduled
5. Notion poller is executing on its 45-second schedule
</success_criteria>

<output>
After completion, create `.planning/quick/13-redeploy-watchman-to-company-ec2/13-SUMMARY.md`
</output>
