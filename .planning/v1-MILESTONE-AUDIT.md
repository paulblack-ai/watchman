---
milestone: v1.0
audited: 2026-02-25
status: gaps_found
scores:
  requirements: 20/27
  phases: 2/4 verified
  integration: 24/27 wired
  flows: 2/4 complete
gaps:
  requirements:
    - id: "PROC-01"
      status: "unsatisfied"
      phase: "Phase 1"
      claimed_by_plans: ["01-03-PLAN.md"]
      completed_by_plans: ["01-03-SUMMARY.md"]
      verification_status: "missing"
      evidence: "process_unprocessed() defined in normalizer.py but never called from scheduler or main.py. Raw items never become signal cards."
    - id: "PROC-02"
      status: "unsatisfied"
      phase: "Phase 1"
      claimed_by_plans: ["01-03-PLAN.md"]
      completed_by_plans: ["01-03-SUMMARY.md"]
      verification_status: "missing"
      evidence: "URL dedup runs inside process_unprocessed() which is never scheduled. Dedup logic exists but is unreachable."
    - id: "PROC-03"
      status: "unsatisfied"
      phase: "Phase 1"
      claimed_by_plans: ["01-03-PLAN.md"]
      completed_by_plans: ["01-03-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Content fingerprint dedup runs inside process_unprocessed() which is never scheduled. Same root cause as PROC-01."
    - id: "SRC-04"
      status: "partial"
      phase: "Phase 1"
      claimed_by_plans: ["01-03-PLAN.md"]
      completed_by_plans: ["01-03-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Individual health alerts fire at 2 consecutive zeros. Daily digest (get_daily_digest + send_daily_digest) defined but never scheduled."
    - id: "SLCK-01"
      status: "partial"
      phase: "Phase 2"
      claimed_by_plans: ["02-02-PLAN.md"]
      completed_by_plans: ["02-02-SUMMARY.md"]
      verification_status: "human_needed"
      evidence: "Code complete and wired. Requires live Slack verification."
    - id: "SLCK-02"
      status: "partial"
      phase: "Phase 2"
      claimed_by_plans: ["02-02-PLAN.md"]
      completed_by_plans: ["02-02-SUMMARY.md"]
      verification_status: "human_needed"
      evidence: "Approve handler implemented. Requires live Slack verification."
    - id: "SLCK-03"
      status: "partial"
      phase: "Phase 2"
      claimed_by_plans: ["02-02-PLAN.md"]
      completed_by_plans: ["02-02-SUMMARY.md"]
      verification_status: "human_needed"
      evidence: "Reject handler implemented. Requires live Slack verification."
    - id: "SLCK-04"
      status: "partial"
      phase: "Phase 2"
      claimed_by_plans: ["02-02-PLAN.md"]
      completed_by_plans: ["02-02-SUMMARY.md"]
      verification_status: "human_needed"
      evidence: "Snooze handler + re-queue logic implemented. Requires live Slack verification."
  integration:
    - from: "scheduler/jobs.py"
      to: "processing/normalizer.py"
      issue: "process_unprocessed() never called — normalizer job missing from scheduler"
      affected_reqs: ["PROC-01", "PROC-02", "PROC-03"]
    - from: "scheduler/jobs.py"
      to: "health/alerter.py"
      issue: "send_daily_digest() defined but never scheduled — daily health digest missing"
      affected_reqs: ["SRC-04"]
  flows:
    - name: "Full pipeline (collection → JSON output)"
      breaks_at: "Normalization — raw_items never converted to cards"
      affected_reqs: ["PROC-01", "PROC-02", "PROC-03"]
    - name: "Health daily digest"
      breaks_at: "Daily digest job never scheduled"
      affected_reqs: ["SRC-04"]
tech_debt:
  - phase: 02-scoring-and-slack-review
    items:
      - "datetime.utcnow() deprecated — should use datetime.now(UTC)"
  - phase: 03-enrichment-pipeline
    items:
      - "datetime.utcnow() in extractor.py — deprecated"
  - phase: documentation
    items:
      - "Phase 02-01 and 03-01 SUMMARYs reference ANTHROPIC_API_KEY instead of OPENROUTER_API_KEY"
      - "REQUIREMENTS.md SLCK-01 through SLCK-04 still unchecked despite code complete"
      - "REQUIREMENTS.md OUT-01 through OUT-03 still unchecked despite Phase 4 verification passed"
      - "Phase 1 missing VERIFICATION.md"
      - "Phase 3 missing VERIFICATION.md"
---

# Milestone v1.0 Audit Report

**Audited:** 2026-02-25
**Status:** gaps_found
**Score:** 20/27 requirements satisfied (3 unsatisfied, 4 need human verification)

## Requirements Cross-Reference

| Req ID | Description | REQUIREMENTS.md | VERIFICATION.md | Integration | Final Status |
|--------|-------------|-----------------|-----------------|-------------|--------------|
| SRC-01 | YAML source config | [x] | No verification | WIRED | satisfied |
| SRC-02 | Zero-code source addition | [x] | No verification | WIRED | satisfied |
| SRC-03 | 15-20 starter sources | [x] | No verification | WIRED | satisfied |
| SRC-04 | Source health alerts | [x] | No verification | PARTIAL | **partial** |
| COLL-01 | APScheduler collectors | [x] | No verification | WIRED | satisfied |
| COLL-02 | RSS collector | [x] | No verification | WIRED | satisfied |
| COLL-03 | HTTP/API collector | [x] | No verification | WIRED | satisfied |
| COLL-04 | Scrape collector | [x] | No verification | WIRED | satisfied |
| PROC-01 | Normalization | [x] | No verification | **UNWIRED** | **unsatisfied** |
| PROC-02 | URL dedup | [x] | No verification | **UNWIRED** | **unsatisfied** |
| PROC-03 | Content fingerprint dedup | [x] | No verification | **UNWIRED** | **unsatisfied** |
| PROC-04 | Claude Haiku scoring | [x] | SATISFIED | WIRED | satisfied |
| PROC-05 | Daily volume cap | [x] | SATISFIED | WIRED | satisfied |
| PROC-06 | Score persistence | [x] | SATISFIED | WIRED | satisfied |
| SLCK-01 | Block Kit delivery | [ ] | HUMAN NEEDED | WIRED | **human needed** |
| SLCK-02 | Approve button | [ ] | HUMAN NEEDED | WIRED | **human needed** |
| SLCK-03 | Reject button | [ ] | HUMAN NEEDED | WIRED | **human needed** |
| SLCK-04 | Snooze button | [ ] | HUMAN NEEDED | WIRED | **human needed** |
| ENRCH-01 | Enrichment on approval only | [x] | No verification | WIRED | satisfied |
| ENRCH-02 | LLM extraction | [x] | No verification | WIRED | satisfied |
| ENRCH-03 | Pydantic schema validation | [x] | No verification | WIRED | satisfied |
| OUT-01 | Gate 2 Slack card | [ ] | PASS | WIRED | satisfied |
| OUT-02 | Approve/reject at Gate 2 | [ ] | PASS | WIRED | satisfied |
| OUT-03 | JSON output files | [ ] | PASS | WIRED | satisfied |
| INFRA-01 | SQLite integration bus | [x] | No verification | WIRED | satisfied |
| INFRA-02 | IcebreakerAI Pydantic models | [x] | No verification | WIRED | satisfied |
| INFRA-03 | Single-process cron agent | [x] | No verification | WIRED | satisfied |

## Critical Gaps

### 1. Normalizer never scheduled (PROC-01, PROC-02, PROC-03)

`process_unprocessed()` in `processing/normalizer.py` is defined and tested but never called from the scheduler or `main.py`. This means:

```
Collectors → raw_items (DB) → [MISSING] → cards (DB) → scorer
```

Raw items accumulate forever. The scoring job finds zero unscored cards. The entire post-collection pipeline is inert.

**Fix:** Add a normalizer job to `scheduler/jobs.py` and schedule it in `main.py`.

### 2. Daily health digest never scheduled (SRC-04 partial)

`get_daily_digest()` and `send_daily_digest()` are defined in health modules but never wired to a scheduler job. Individual alerts fire at 2 consecutive zeros, but persistent failures have no ongoing notification.

**Fix:** Add a daily digest job to the scheduler.

## E2E Flow Status

| Flow | Status | Break Point |
|------|--------|-------------|
| Full pipeline (collection → JSON output) | **BROKEN** | Normalization step never executes |
| Source health → Slack alert | **PARTIAL** | Individual alerts work; daily digest missing |
| Snooze → 30-day re-queue | COMPLETE | — |
| Gate 2 re-enrich retry | COMPLETE | — |

## Phase Verification Status

| Phase | VERIFICATION.md | Status |
|-------|----------------|--------|
| 1. Collection Pipeline | Missing | Unverified |
| 2. Scoring and Slack Review | Present | human_needed (6 Slack items) |
| 3. Enrichment Pipeline | Missing | Unverified |
| 4. Gate 2 and Output | Present | passed (3/3) |

## Tech Debt

- `datetime.utcnow()` deprecated in enrichment/extractor.py and repositories.py
- Phase 02-01 and 03-01 SUMMARYs reference ANTHROPIC_API_KEY (should be OPENROUTER_API_KEY)
- REQUIREMENTS.md checkboxes out of sync with actual status (SLCK-*, OUT-*)
- Phases 1 and 3 missing VERIFICATION.md files

---

*Audited: 2026-02-25*
*Auditor: Claude (audit-milestone)*
