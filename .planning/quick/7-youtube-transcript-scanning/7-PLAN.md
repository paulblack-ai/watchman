---
phase: quick-7
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - src/watchman/processing/normalizer.py
  - src/watchman/processing/transcript.py
autonomous: true
requirements: [YT-TRANSCRIPT-01]

must_haves:
  truths:
    - "YouTube videos with tool-announcement titles get transcript pulled and split into individual tool cards"
    - "YouTube videos with non-tool titles (tutorials, vlogs) are skipped and normalized as regular single cards"
    - "Each extracted tool from a transcript becomes its own SignalCard with unique url_hash"
  artifacts:
    - path: "src/watchman/processing/transcript.py"
      provides: "Pre-filter gate and transcript-based tool extraction"
      exports: ["is_tool_announcement", "extract_tools_from_transcript"]
    - path: "src/watchman/processing/normalizer.py"
      provides: "YouTube transcript scanning branch in process_unprocessed"
      contains: "is_tool_announcement"
    - path: "pyproject.toml"
      provides: "youtube-transcript-api dependency"
      contains: "youtube-transcript-api"
  key_links:
    - from: "src/watchman/processing/normalizer.py"
      to: "src/watchman/processing/transcript.py"
      via: "import and call in youtube branch"
      pattern: "from watchman\\.processing\\.transcript import"
    - from: "src/watchman/processing/transcript.py"
      to: "youtube_transcript_api"
      via: "transcript fetch"
      pattern: "YouTubeTranscriptApi"
---

<objective>
Add YouTube transcript scanning to the normalizer pipeline. When a YouTube RawItem arrives, a cheap pre-filter checks the title/description for tool-announcement signals. If it passes, the transcript is fetched and an LLM pass extracts individual tool mentions as separate signal cards — mirroring the existing changelog splitting pattern.

Purpose: Turn YouTube roundup videos ("5 NEW AI Tools This Week") into individual tool cards that flow through scoring/review, while skipping irrelevant content videos.
Output: New transcript.py module, updated normalizer with youtube branch, youtube-transcript-api dependency added.
</objective>

<execution_context>
@/Users/salfaqih/.claude/get-shit-done/workflows/execute-plan.md
@/Users/salfaqih/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/watchman/processing/normalizer.py
@src/watchman/collectors/youtube.py
@src/watchman/llm_client.py
@src/watchman/models/raw_item.py
@pyproject.toml

<interfaces>
<!-- From normalizer.py — key patterns to follow -->
From src/watchman/processing/normalizer.py:
```python
# Existing detection pattern (follow this style):
def _is_changelog_candidate(item: RawItem, source_cfg: SourceConfig | None) -> bool

# Existing LLM splitting pattern (follow this style):
async def split_changelog_item(item: RawItem) -> list[dict]

# Card creation with unique url_hash for split cards:
card = normalize_raw_item(item, tier, override_title=entry["title"], override_summary=entry["description"])
# normalize_raw_item appends #title to URL for url_hash uniqueness when override_title is set

# JSON parsing helper already exists:
def _parse_llm_json(text: str) -> list[dict] | dict | None
```

From src/watchman/models/raw_item.py:
```python
class RawItem(BaseModel):
    collector_type: Literal["rss", "api", "scrape", "jina", "youtube"]
    title: str | None = None
    summary: str | None = None  # YouTube: description from media:group
    raw_data: str | None = None  # YouTube: JSON with video_id, channel, url
```

From src/watchman/llm_client.py:
```python
def get_client() -> anthropic.Anthropic  # OpenRouter-backed, use model="anthropic/claude-haiku-4.5"
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create transcript.py with pre-filter and extraction logic</name>
  <files>src/watchman/processing/transcript.py, pyproject.toml</files>
  <action>
1. Add `youtube-transcript-api>=0.6` to pyproject.toml dependencies and run `pip install -e .`

2. Create `src/watchman/processing/transcript.py` with two public functions:

**`is_tool_announcement(title: str, description: str | None) -> bool`**
- Keyword-based pre-filter (no LLM cost). Returns True if the title or description suggests the video covers new AI tools, product launches, or feature releases.
- Match patterns like: "new ai tool", "just launched", "just released", "new feature", "product launch", "tools you need", "tools this week", "tools that", "ai tools", "top * tools", "best new", "game changer", "alternative to", "just dropped". Use re.compile with re.IGNORECASE for efficiency.
- Also match numeric patterns like "5 NEW AI Tools", "10 Best Tools" (digit followed by tool-related words).
- Return False for tutorial/lifestyle signals: if title contains "how I use", "my workflow", "morning routine", "day in the life", "tutorial for beginners" AND does not contain tool-announcement keywords.
- When in doubt (no strong signal either way), return False — we only want high-confidence matches to avoid wasting transcript API calls.

**`async def extract_tools_from_transcript(item: RawItem) -> list[dict]`**
- Extract video_id from item.raw_data JSON (key: "video_id").
- Fetch transcript using `YouTubeTranscriptApi.get_transcript(video_id)` wrapped in `asyncio.to_thread()`. The library returns a list of dicts with "text" keys. Join all text segments into a single string, truncate to 4000 chars.
- If transcript fetch fails (no captions, video unavailable), log warning and return empty list `[]`.
- Call LLM (same pattern as `split_changelog_item`): prompt asks to extract individual AI tools/products mentioned as new launches or releases. Return JSON array: `[{"title": "Tool Name - What It Does", "description": "1-2 sentence summary of what the tool does and why it matters"}]`. Instruct the LLM to skip tools that are only mentioned in passing (e.g., "like ChatGPT") and focus on tools being announced, demoed, or reviewed as new.
- Include video title in the prompt for context.
- Parse response with `_parse_llm_json` (import from normalizer).
- If LLM returns valid entries, return them. If LLM fails or returns empty, return empty list `[]` (the video will fall through to regular single-card normalization).
- Use `from __future__ import annotations` for Python 3.9 compat.
- Use logging module (logger = logging.getLogger(__name__)).
  </action>
  <verify>python -c "from watchman.processing.transcript import is_tool_announcement, extract_tools_from_transcript; print('imports ok'); assert is_tool_announcement('5 NEW AI Tools That Just Launched', None) == True; assert is_tool_announcement('My Morning Routine with AI', None) == False; print('pre-filter ok')"</verify>
  <done>transcript.py exists with is_tool_announcement (keyword pre-filter) and extract_tools_from_transcript (fetch + LLM extraction). Pre-filter correctly identifies tool-announcement vs non-tool titles.</done>
</task>

<task type="auto">
  <name>Task 2: Wire transcript scanning into normalizer's process_unprocessed</name>
  <files>src/watchman/processing/normalizer.py</files>
  <action>
In `process_unprocessed()`, add a new branch for YouTube items BEFORE the existing changelog and generic-title branches. Insert it right after `tier = source_cfg.tier if source_cfg else 2` (line ~301).

Add this logic:
```python
if item.collector_type == "youtube":
    from watchman.processing.transcript import is_tool_announcement, extract_tools_from_transcript

    if is_tool_announcement(item.title or "", item.summary):
        tools = await extract_tools_from_transcript(item)
        if tools:
            logger.info(
                "YouTube video '%s' yielded %d tool cards",
                item.title,
                len(tools),
            )
            for tool in tools:
                card = normalize_raw_item(
                    item,
                    tier,
                    override_title=tool["title"],
                    override_summary=tool["description"],
                )
                if await _insert_and_dedup(card, card_repo):
                    new_cards += 1
            await raw_repo.mark_processed(item.id)
            continue
    # If not a tool announcement or extraction returned empty,
    # fall through to standard normalization below
```

After the youtube-specific block, the existing `if _is_changelog_candidate(...)` / `elif` / `else` chain handles the fallthrough case (standard single-card normalization for non-tool YouTube videos).

Use lazy import for transcript module (same pattern as `from watchman.llm_client import get_client`) to avoid import errors if youtube-transcript-api is not installed.

Make sure the `continue` only fires when tools were successfully extracted. If `is_tool_announcement` returns False OR `extract_tools_from_transcript` returns empty, the item falls through to the standard `else` branch at the bottom which creates a single card.
  </action>
  <verify>cd /Users/salfaqih/paul/Projects/watchman && PYTHONPATH=src python -c "
from watchman.processing.normalizer import process_unprocessed
print('normalizer imports ok')
# Verify the youtube branch exists in source
import inspect
source = inspect.getsource(process_unprocessed)
assert 'is_tool_announcement' in source, 'missing youtube pre-filter'
assert 'extract_tools_from_transcript' in source, 'missing transcript extraction'
print('youtube branch wired correctly')
"</verify>
  <done>Normalizer's process_unprocessed has a youtube-specific branch that pre-filters by title, pulls transcript, extracts tools as individual cards. Non-tool videos fall through to standard single-card normalization.</done>
</task>

</tasks>

<verification>
1. `PYTHONPATH=src python -c "from watchman.processing.transcript import is_tool_announcement; print(is_tool_announcement('5 NEW AI Tools That Just Launched This Week', None))"` prints True
2. `PYTHONPATH=src python -c "from watchman.processing.transcript import is_tool_announcement; print(is_tool_announcement('How I Use ChatGPT for Meal Planning', None))"` prints False
3. `PYTHONPATH=src python -c "from watchman.processing.normalizer import process_unprocessed; print('normalizer loads ok')"` succeeds
4. `pip show youtube-transcript-api` shows package installed
</verification>

<success_criteria>
- youtube-transcript-api dependency added and installed
- transcript.py module with keyword pre-filter and LLM transcript extraction
- Normalizer wired to detect tool-announcement YouTube videos, pull transcripts, and split into individual tool cards
- Non-tool YouTube videos continue to create single cards as before
- All imports and syntax valid under Python 3.9
</success_criteria>

<output>
After completion, create `.planning/quick/7-youtube-transcript-scanning/7-SUMMARY.md`
</output>
