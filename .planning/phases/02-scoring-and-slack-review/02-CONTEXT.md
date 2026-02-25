# Phase 2: Scoring and Slack Review - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Signal cards are scored against the IcebreakerAI relevance rubric using Claude Haiku, capped to 3-7 per day, and delivered to Lauren in Slack with Block Kit formatting. Lauren can approve, reject, or snooze each card. Includes a `/watchman add-source` slash command for adding sources directly from Slack. Enrichment and second-gate review are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Scoring transparency
- Each Slack card shows the overall relevance score plus the top contributing rubric dimension (e.g., "8.2 — strong taxonomy fit")
- A "Details" button on each card expands to reveal the full 4-dimension rubric breakdown (taxonomy fit, novel capability, adoption/traction, credibility)
- Full rubric score breakdowns are persisted in the database per signal for future calibration

### Filtered signal visibility
- Daily review includes a summary count footer (e.g., "Showing 5 of 23 signals today") so Lauren knows the volume being filtered
- Signals that don't make the daily cap are silently excluded from individual cards — only the aggregate count is shown

### Rubric configuration
- Rubric weights are defined in YAML config (not hardcoded) so they can be adjusted without code changes
- Default weights ship with the starter config (taxonomy fit, novel capability, adoption/traction, credibility)

### Claude's Discretion
- Slack card layout and visual hierarchy (Block Kit structure, spacing, emoji usage)
- Review delivery timing and cadence (single cards vs. batch, time of day)
- Button placement and interaction flow for approve/reject/snooze
- Snooze visual behavior (confirmation message, re-queue indicator)
- `/watchman add-source` slash command UX and validation flow
- Score scale (0-10, 0-100, etc.) and threshold logic for the daily cap

</decisions>

<specifics>
## Specific Ideas

- Score display pattern: "8.2 — strong taxonomy fit" as the compact format (score + plain-language top factor)
- Lauren wants to know filtering is happening without seeing every filtered card — the "Showing X of Y" footer balances awareness with noise reduction

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-scoring-and-slack-review*
*Context gathered: 2026-02-24*
