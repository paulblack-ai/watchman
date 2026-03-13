---
phase: quick
plan: 9
title: "Migrate Watchman to Company EC2 Instance"
subsystem: infrastructure
tags: [migration, ec2, systemd, deployment]
key-files:
  modified:
    - pyproject.toml
    - ~/.ssh/config
decisions:
  - "python-dotenv added to pyproject.toml (was missing from dependency list)"
metrics:
  duration: "~9 min"
  completed: "2026-03-13"
  tasks_completed: 3
  tasks_total: 3
---

# Quick Task 9: Migrate Watchman to Company EC2 Instance Summary

Migrated watchman signal collection service from personal EC2 (us-east-1, 54.234.12.180) to company EC2 (us-east-2, 13.59.61.76) with Python 3.11 and fresh venv.

## What Was Done

### Task 1: Provision + Transfer + Setup
- Installed Python 3.11 on new Amazon Linux 2023 instance via `dnf`
- Transferred code, .env, watchman.db (18MB), and watchman.service from old instance via local /tmp relay
- Excluded old venv (Python version mismatch); created fresh venv with Python 3.11
- Installed all dependencies via `pip install -e '.[dev]'`
- Installed systemd service, enabled on boot, started service
- **Commit:** `81110d8`

### Task 2: Verify
- Confirmed service `active (running)` and stable (no crashes)
- All 30 scheduled jobs registered: 24 collect_source, scoring, enrichment, normalizer, daily review, daily digest
- Scheduler started cleanly, no errors in logs
- Collection cycles not yet fired (DB has recent timestamps from old instance, intervals are 4-12h)

### Task 3: Cutover
- Stopped and disabled watchman.service on old instance
- Verified PM2 gathering-agent still running on old instance (13 days uptime, untouched)
- Updated ~/.ssh/config: `watchman` -> `watchman-old`, `watchman-new` -> `watchman`
- Verified `ssh watchman` connects to new instance (us-east-2)
- Verified `ssh watchman-old` connects to old instance (us-east-1)
- Cleaned up /tmp/watchman-migration/

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing python-dotenv dependency**
- **Found during:** Task 1 (service startup)
- **Issue:** `ModuleNotFoundError: No module named 'dotenv'` -- python-dotenv was installed manually on old instance but not declared in pyproject.toml
- **Fix:** Installed python-dotenv in new venv, added `python-dotenv>=1.0` to pyproject.toml dependencies
- **Files modified:** pyproject.toml (local), venv on new instance
- **Commit:** 81110d8

**2. [Rule 3 - Blocking] Incomplete SCP transfer**
- **Found during:** Task 1 (file transfer)
- **Issue:** `scp -r` from old instance missed watchman.db and watchman.service files
- **Fix:** Copied missing files individually via targeted scp commands
- **No commit needed** (ops-only fix)

## Verification

| Check | Result |
|-------|--------|
| Service status on new instance | active (running), 30 jobs |
| No errors in journalctl | PASS |
| Old service stopped + disabled | PASS |
| PM2 gathering-agent untouched | PASS (13D uptime) |
| SSH alias `watchman` -> new instance | PASS (us-east-2) |
| SSH alias `watchman-old` -> old instance | PASS (us-east-1) |
| /tmp cleanup | PASS |

## Instance Details

| Property | Old Instance | New Instance |
|----------|-------------|-------------|
| SSH alias | `watchman-old` | `watchman` |
| IP | 54.234.12.180 | 13.59.61.76 |
| Region | us-east-1 | us-east-2 |
| OS | Amazon Linux 2023 | Amazon Linux 2023 |
| Python | 3.9 | 3.11.14 |
| Watchman service | STOPPED + DISABLED | RUNNING + ENABLED |
| gathering-agent (PM2) | RUNNING (untouched) | N/A |
| SSH key | gathering-agent-key.pem | macmini.pem |

## Self-Check: PASSED

- 9-SUMMARY.md: FOUND
- Commit 81110d8: FOUND
