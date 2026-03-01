---
phase: quick-7
plan: 01
subsystem: processing
tags: [youtube, transcript, llm, pre-filter, normalizer]

requires:
  - phase: 01-collection-pipeline
    provides: YouTube collector, RawItem model, normalizer pipeline
provides:
  - YouTube transcript scanning with pre-filter and LLM tool extraction
  - Individual tool cards from YouTube roundup videos
affects: [normalizer, scoring, slack-review]

tech-stack:
  added: [youtube-transcript-api]
  patterns: [keyword pre-filter before LLM, transcript-based card splitting]

key-files:
  created:
    - src/watchman/processing/transcript.py
  modified:
    - src/watchman/processing/normalizer.py
    - pyproject.toml

key-decisions:
  - "Keyword pre-filter gates transcript API calls to avoid unnecessary cost"
  - "Non-tool YouTube videos fall through to standard single-card normalization"
  - "Transcript truncated to 4000 chars to control LLM costs"
  - "Lazy import for transcript module to avoid hard dependency at module load"

patterns-established:
  - "Pre-filter pattern: cheap keyword check before expensive API/LLM call"

requirements-completed: [YT-TRANSCRIPT-01]

duration: 2min
completed: 2026-03-01
---

# Quick Task 7: YouTube Transcript Scanning Summary

**Keyword pre-filter and LLM transcript extraction for YouTube tool-announcement videos, splitting roundups into individual tool cards**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T12:56:13Z
- **Completed:** 2026-03-01T12:58:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created transcript.py with keyword-based pre-filter (is_tool_announcement) that detects tool-announcement videos without LLM cost
- Added extract_tools_from_transcript that fetches captions via youtube-transcript-api and uses Claude Haiku to extract individual tools
- Wired YouTube branch into normalizer pipeline before changelog/generic-title branches
- Non-tool YouTube videos (tutorials, vlogs) fall through to standard single-card normalization

## Task Commits

Each task was committed atomically:

1. **Task 1: Create transcript.py with pre-filter and extraction logic** - `e713ec7` (feat)
2. **Task 2: Wire transcript scanning into normalizer pipeline** - `3ec9706` (feat)

## Files Created/Modified
- `src/watchman/processing/transcript.py` - Pre-filter (is_tool_announcement) and LLM transcript extraction (extract_tools_from_transcript)
- `src/watchman/processing/normalizer.py` - YouTube branch in process_unprocessed before changelog detection
- `pyproject.toml` - Added youtube-transcript-api>=0.6 dependency

## Decisions Made
- Keyword pre-filter gates transcript API calls: only videos with tool-announcement signals (e.g., "5 NEW AI Tools", "just launched") trigger transcript fetch
- Non-tool signals ("how I use", "tutorial for beginners") skip transcript scanning unless tool keywords are also present
- Transcript truncated to 4000 chars for LLM cost control
- Lazy import pattern for transcript module (consistent with existing llm_client import pattern)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- YouTube transcript scanning is live and will process YouTube items on next normalizer run
- Pre-filter ensures only relevant videos incur transcript API and LLM costs

---
*Quick Task: 7-youtube-transcript-scanning*
*Completed: 2026-03-01*
