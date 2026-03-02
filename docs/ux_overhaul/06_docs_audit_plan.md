# CoLearni UX Overhaul — Documentation Audit Plan

Last updated: 2026-03-02

Parent plan: `docs/UX_OVERHAUL_MASTER_PLAN.md`

Archive snapshots:
- `none` (new plan)

## Plan Completeness Checklist

1. archive snapshot path(s) ✓
2. current verification status ✓
3. ordered slice list with stable IDs ✓
4. verification block template (inherited from master) ✓
5. removal entry template (inherited from master) ✓
6. final section `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✓

## Non-Negotiable Run Rules

1. Re-read this file at start, after every 2 slices, after context compaction, before completion claims.
2. A slice is ONLY complete with docs updated + accuracy verified + verification block produced.
3. Work PR-sized: `chore(docs): <slice-id> <short description>`.
4. If a behavior change risk is discovered, STOP and update this plan.
5. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

Audit and update all key documentation files to ensure they reflect the current state of the codebase after the UX overhaul. The UX overhaul introduced changes across multiple tracks (UXF critical fixes, UXG graph replacement, UXP practice UX, UXT tutor UX, UXI infrastructure) and documentation must be brought in sync.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- All completed UXF, UXG, UXP, UXT, UXI child plans
- Current codebase state after UX overhaul implementation
- The 9 documentation files listed below

## Executive Summary

Nine documentation files need auditing:

| File | Lines | Risk Area |
|---|---|---|
| `docs/API.md` | 1,426 | Missing new endpoints from gardener commit fix, practice quiz retry, flashcard stack, graph-to-chat |
| `docs/ARCHITECTURE.md` | 215 | Graph rendering change (D3 → Sigma.js), new state management (Zustand), new dependencies |
| `docs/FRONTEND.md` | 121 | New components (sigma-graph, flashcard-stack, quiz-history, onboarding-confirm, concept-chat-links), new deps (graphology, sigma, minisearch) |
| `docs/GRAPH.md` | 274 | Gardener now commits transactions, orphan pruner integrated, graph rendering moved to Sigma.js |
| `docs/OBSERVABILITY.md` | 538 | Spans/events may not match code. LLM cache hit rate logging may need documenting |
| `docs/PLAN.md` | 553 | Likely stale — needs archival or update to reflect current sprint |
| `docs/PRODUCT_SPEC.md` | 173 | Feature descriptions need updating for unified flashcard stack, quiz history+retry, onboarding confirm, streaming status, graph-chat nav |
| `docs/PROGRESS.md` | 577 | Implementation progress tracker needs UX overhaul completion status |
| `docs/PROMPTS.md` | 279 | Prompt catalog may not match current templates. Uses "P9" sprint naming |

## Non-Negotiable Constraints

1. Do not remove or significantly rewrite documentation sections that are still accurate.
2. Only update what has changed.
3. Add timestamps to files that lack them.
4. Keep documentation factual and concise — do not pad with aspirational content.

## Completed Work

- All 9 documentation files exist and are maintained
- UX overhaul implementation complete across UXF, UXG, UXP, UXT, UXI tracks

## Remaining Slice IDs

- `UXD.1` Audit and flag stale sections
- `UXD.2` Update API.md and ARCHITECTURE.md
- `UXD.3` Update FRONTEND.md and GRAPH.md
- `UXD.4` Update PRODUCT_SPEC.md, PLAN.md, PROGRESS.md
- `UXD.5` Update OBSERVABILITY.md and PROMPTS.md

## Decision Log

1. UXD.1 produces a staleness report only — no changes to docs in that slice.
2. Subsequent slices (UXD.2–UXD.5) pair related docs together for efficient updates.
3. Stale sections in PLAN.md should be archived (moved to a "Historical" section) rather than deleted.
4. PROGRESS.md updates should mark UX overhaul items as complete with dates.
5. API.md updates should follow the existing endpoint documentation format exactly.

## Current Verification Status

- `PYTHONPATH=. pytest -q`: 922 passed
- `npx vitest run`: 106 passed

## Implementation Sequencing

### UXD.1. Audit and flag stale sections

Purpose:
- Read all 9 documentation files and cross-reference with code changes from UXF, UXG, UXP, UXT, UXI tracks
- Produce a staleness report listing what needs updating in each file
- Do NOT make changes yet — audit only

Files involved:
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/FRONTEND.md`
- `docs/GRAPH.md`
- `docs/OBSERVABILITY.md`
- `docs/PLAN.md`
- `docs/PRODUCT_SPEC.md`
- `docs/PROGRESS.md`
- `docs/PROMPTS.md`

Implementation steps:
1. Read each of the 9 docs files in full.
2. Cross-reference content against the UX overhaul child plans:
   - `docs/ux_overhaul/01_critical_fixes_plan.md` (UXF) — gardener commit fix, selection highlighting, graph flicker
   - `docs/ux_overhaul/02_graph_replacement_plan.md` (UXG) — D3 → Sigma.js, graphology, Zustand state
   - `docs/ux_overhaul/03_practice_ux_plan.md` (UXP) — flashcard stack, quiz history, quiz retry
   - `docs/ux_overhaul/04_tutor_ux_plan.md` (UXT) — onboarding confirm, streaming status, concept-chat links
   - `docs/ux_overhaul/05_infrastructure_plan.md` (UXI) — sources page polish, LLM caching, dev stats toggle
3. For each doc, list:
   - Sections that are accurate (no change needed)
   - Sections that are stale or incomplete (with specific details of what's wrong)
   - Sections that are missing (new content needed)
4. Produce a staleness report as a verification block in this plan file (appended after UXD.1 section).

What stays the same:
- All documentation files — no content changes in this slice

Verification:
- Staleness report produced and appended to this plan
- Every doc file accounted for
- Specific stale items identified with references to which UX track caused the change

Exit criteria:
- Complete staleness report covering all 9 docs
- Each stale item linked to the relevant UX track (UXF/UXG/UXP/UXT/UXI)

### UXD.2. Update API.md and ARCHITECTURE.md

Purpose:
- Bring API reference and architecture overview in sync with post-overhaul codebase

Files involved:
- `docs/API.md`
- `docs/ARCHITECTURE.md`

Implementation steps:
1. **API.md updates** (based on UXD.1 staleness report):
   - Add any new endpoints introduced by UXP (quiz retry, flashcard stack endpoints)
   - Add any new endpoints introduced by UXT (graph-to-chat navigation endpoints)
   - Update any endpoint signatures/responses changed by UXF (gardener commit fix)
   - Follow the existing documentation format for endpoint entries
   - Verify each new/changed endpoint exists in `apps/api/routes/`
2. **ARCHITECTURE.md updates** (based on UXD.1 staleness report):
   - Update graph rendering architecture: D3.js → Sigma.js with graphology
   - Document new state management: Zustand stores for graph state
   - Add new frontend dependencies (graphology, @sigma/*, minisearch)
   - Update any architecture diagrams or component descriptions affected by UXG
   - Add timestamp if missing

What stays the same:
- Backend architecture sections unaffected by UX overhaul
- Database schema documentation
- Authentication/authorization documentation

Verification:
- Every new/changed endpoint in `apps/api/routes/` has a corresponding entry in API.md
- Architecture description matches actual graph rendering stack
- `grep` for Sigma.js / graphology in codebase confirms documented dependencies

Exit criteria:
- API.md covers all current endpoints accurately
- ARCHITECTURE.md reflects Sigma.js graph rendering and Zustand state management

### UXD.3. Update FRONTEND.md and GRAPH.md

Purpose:
- Update frontend source of truth and graph design documentation

Files involved:
- `docs/FRONTEND.md`
- `docs/GRAPH.md`

Implementation steps:
1. **FRONTEND.md updates** (based on UXD.1 staleness report):
   - Add new components: sigma-graph, flashcard-stack, quiz-history, onboarding-confirm, concept-chat-links
   - Add new dependencies: graphology, @sigma/react, minisearch
   - Update component directory structure if changed
   - Document new patterns (Zustand stores, streaming status display)
   - Remove references to replaced components (D3-based graph) if still present
2. **GRAPH.md updates** (based on UXD.1 staleness report):
   - Document that gardener now commits transactions (UXF.1 fix)
   - Document orphan pruner integration
   - Update rendering section: D3.js → Sigma.js with graphology
   - Update graph state management description (Zustand)
   - Ensure gardener budget/resolver documentation still accurate
   - Add timestamp if missing

What stays the same:
- Graph gardener algorithm descriptions (if still accurate)
- Resolver logic documentation
- Any FRONTEND.md sections about non-graph components that haven't changed

Verification:
- New components listed in FRONTEND.md exist in `apps/web/`
- GRAPH.md rendering section matches actual implementation
- Gardener commit behavior documented correctly
- `grep` for old D3 references removed from updated sections

Exit criteria:
- FRONTEND.md lists all current components and dependencies
- GRAPH.md accurately describes gardener behavior and Sigma.js rendering

### UXD.4. Update PRODUCT_SPEC.md, PLAN.md, PROGRESS.md

Purpose:
- Update product vision, release plan, and progress tracker

Files involved:
- `docs/PRODUCT_SPEC.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`

Implementation steps:
1. **PRODUCT_SPEC.md updates** (based on UXD.1 staleness report):
   - Update feature descriptions for new UX: unified flashcard stack, quiz history with retry, onboarding confirmation step, streaming status indicators, graph-chat navigation
   - Ensure feature list matches what's actually implemented
   - Do not add aspirational features — only document what exists
2. **PLAN.md updates** (based on UXD.1 staleness report):
   - Archive stale sprint/release sections by moving them under a "## Historical" heading
   - Update current status to reflect post-UX-overhaul state
   - If the entire plan is historical, add a note at the top pointing to the UX overhaul master plan
   - Add timestamp
3. **PROGRESS.md updates** (based on UXD.1 staleness report):
   - Mark UX overhaul items as complete with completion dates
   - Update any progress percentages or status indicators
   - Add entries for UXF, UXG, UXP, UXT, UXI track completions
   - Add timestamp

What stays the same:
- Product vision/mission statement in PRODUCT_SPEC.md (unless contradicted by implementation)
- Historical entries in PROGRESS.md — do not rewrite history

Verification:
- PRODUCT_SPEC.md feature list matches implemented features
- PLAN.md has no actively misleading "upcoming" items that are already done
- PROGRESS.md reflects current completion state

Exit criteria:
- All three files accurately reflect post-overhaul state
- No aspirational content presented as current

### UXD.5. Update OBSERVABILITY.md and PROMPTS.md

Purpose:
- Ensure observability documentation and prompt catalog match current code

Files involved:
- `docs/OBSERVABILITY.md`
- `docs/PROMPTS.md`

Implementation steps:
1. **OBSERVABILITY.md updates** (based on UXD.1 staleness report):
   - Verify documented spans/events still match code in `core/` and `domain/`
   - Check if LLM cache hit rate logging (from UXI.2) needs documenting
   - Update any trace/span names that changed
   - Verify Phoenix/OpenTelemetry configuration documentation is current
   - Add timestamp if missing
2. **PROMPTS.md updates** (based on UXD.1 staleness report):
   - Cross-reference prompt catalog with actual prompt templates in code
   - Verify prompt IDs/names match
   - Update any prompts that were restructured for caching (UXI.2 prefix caching)
   - Check if "P9" sprint naming is still relevant or needs updating
   - Add timestamp if missing

What stays the same:
- Prompt content descriptions that are still accurate
- Observability setup instructions that haven't changed

Verification:
- `grep` for span/event names in code matches OBSERVABILITY.md entries
- `grep` for prompt template names/IDs in code matches PROMPTS.md entries
- No documented spans/prompts that no longer exist in code

Exit criteria:
- OBSERVABILITY.md spans/events match codebase
- PROMPTS.md catalog matches current prompt templates
- All 9 docs fully audited and updated

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the Self-Audit Convergence Protocol may reopen slices in this child plan. When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
4. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
5. Only the specific issue identified in the Audit Report is addressed — do not widen scope

## Execution Order (Update After Each Run)

1. `UXD.1` Audit and flag stale sections
2. `UXD.2` Update API.md and ARCHITECTURE.md
3. `UXD.3` Update FRONTEND.md and GRAPH.md
4. `UXD.4` Update PRODUCT_SPEC.md, PLAN.md, PROGRESS.md
5. `UXD.5` Update OBSERVABILITY.md and PROMPTS.md

## Verification Matrix

```bash
# Documentation accuracy — no code tests needed, but verify no broken references:
grep -r "D3\|d3-force\|d3-selection" docs/FRONTEND.md docs/GRAPH.md docs/ARCHITECTURE.md  # should not appear in updated sections
grep -r "sigma\|graphology\|Zustand" docs/FRONTEND.md docs/GRAPH.md docs/ARCHITECTURE.md  # should appear
```

## Removal Ledger

{Append entries during implementation}

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/06_docs_audit_plan.md.
Begin with the next incomplete UXD slice exactly as described.

Execution loop for this child plan:

1. Work on one UXD slice at a time.
2. Do not remove or significantly rewrite documentation sections that are still accurate. Only update what has changed. Add timestamps to files that lack them. Keep documentation factual and concise — do not pad with aspirational content.
3. Run the listed verification steps before claiming a slice complete, including cross-referencing docs against actual code where required by the plan.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed UXD slices OR if context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/06_docs_audit_plan.md and restate which UXD slices remain.
6. Continue to the next incomplete UXD slice once the previous slice is verified.
7. When all UXD slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXD is complete. UXD completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle, only work on slices marked as "reopened". Produce audit-prefixed Verification Blocks. Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/06_docs_audit_plan.md.
Begin with the current UXD slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXD is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue with the next incomplete child plan.
```
