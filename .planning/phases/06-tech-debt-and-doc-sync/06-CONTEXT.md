# Phase 6: Tech Debt and Doc Sync - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix deprecated Python APIs, sync documentation references with actual implementation state, update requirement checkboxes to reflect completed work, and add missing verification artifacts for phases 1 and 3. Pure maintenance — no new features or behavioral changes.

</domain>

<decisions>
## Implementation Decisions

### Deprecated API Replacement
- Replace all `datetime.utcnow()` calls with `datetime.now(UTC)` across the codebase
- Mechanical find-and-replace — no behavioral change expected

### Documentation Sync
- SUMMARY docs must reference OPENROUTER_API_KEY (not ANTHROPIC_API_KEY) to match actual LLM provider configuration
- REQUIREMENTS.md checkboxes for SLCK-01 through SLCK-04 and OUT-01 through OUT-03 must be checked to reflect completed phases

### Verification Artifacts
- Create VERIFICATION.md files for Phase 1 and Phase 3
- Follow the same format used by existing verification files in the project

### Claude's Discretion
- Verification file content and evidence format
- Order of operations for the fixes
- Whether to batch datetime replacements by file or module
- Any additional doc inconsistencies discovered during the sync

</decisions>

<specifics>
## Specific Ideas

No specific requirements — all tasks are explicitly defined in the success criteria. Standard mechanical cleanup.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-tech-debt-and-doc-sync*
*Context gathered: 2026-02-25*
