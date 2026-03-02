# CoLearni UX Overhaul — Master Plan (READ THIS OFTEN)

Last updated: 2026-03-02

Archive snapshots:
- `docs/UX_SPRINT2_PLAN.md` (superseded single-file plan — slices UX1–UX8)

Template usage:
- This is the cross-track execution plan for the full UX overhaul sprint.
- It supersedes `docs/UX_SPRINT2_PLAN.md` which is now archived.
- All child plans are subordinate to this document.
- Template used: `docs/templates/MASTER_PLAN_TEMPLATE.md`

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered track list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the child plan are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (see template below).
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. This is a UX overhaul. Do not mix in unrelated backend architecture or data model work unless required by a slice.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

This document is the master execution plan for the comprehensive UX overhaul of the CoLearni application. It consolidates all UX work surfaced from manual testing after the agentic tracks (AR0–AR7) and initial polish pass (GP1–GP8).

What earlier work already landed:
- AR0–AR7: All agentic tracks complete
- GP1–GP8: Graph UX polish Sprint 1 complete
- UX_SPRINT2_PLAN.md: Planned but not yet executed (superseded by this plan)

Why this plan exists:
- The scope has grown beyond a single-file plan. Multiple interrelated tracks need proper coordination.
- A major graph visualization replacement (D3 → Sigma.js/graphology based on LightRAG porting guide) was requested.
- Practice UX (flashcards, quizzes) needs significant rework for usability.
- Multiple bug fixes, infrastructure improvements, and tutor UX changes are queued.

## Inputs Used

This plan is based on:
- `docs/UX_SPRINT2_PLAN.md` (superseded plan — UX1–UX8)
- `docs/REPO_HEALTH_REPORT.md` (repo health assessment)
- `docs/lightrag-graph-porting-guide.md` (LightRAG WebUI graph porting reference)
- `docs/GRAPH.md` (graph gardener and resolver design)
- `docs/PRODUCT_SPEC.md` (product behavior expectations)
- Manual testing observations from user on 2026-03-02
- Current repository layout as of 2026-03-02

## Executive Summary

What is already in good shape:
- Agentic conductor, evidence planning, streaming protocol all complete
- Topic switching, mastery gating, concept resolution functional
- Flashcard generation with fingerprint dedup and exhaustion detection
- Practice quiz creation, grading, and history APIs exist
- Concept activity panel shows past runs

What is critically broken:
1. **Gardener transaction never commits** — all merges/prunes silently lost (one-liner fix)
2. **Graph node click causes flicker** — subgraph fetch triggers full simulation restart
3. **Wildcard/adjacent suggestion selection doesn't highlight** — `focusNodeId` not set

What is materially missing:
4. **Graph UX is 3/10** — user requested LightRAG-style Sigma.js replacement for the entire graph component
5. **No unified flashcard viewer** — flashcards are per-run, no merged stack, no "generate more" from existing view
6. **No quiz history browser** — no way to view past quizzes, open them, or retry
7. **Sources page cursor bug** — upload button shows spinning wheel on hover
8. **No per-document tier breakdown** — only total concept count shown
9. **Onboarding requires Enter to send** — clicking topic should auto-send with confirmation
10. **Streaming status appends instead of replaces** — user wants ChatGPT-style single-line animation
11. **No chat integration in graph** — can't start a chat or see active chats from graph detail
12. **No LLM prompt caching** — every call sends full context from scratch
13. **No dev stats toggle** — generation trace only visible in dev builds

## Non-Negotiable Constraints

1. Preserve `verify_assistant_draft()` as the final answer gate.
2. Keep topic lock, concept switching, and mastery gating runtime-owned.
3. Do not auto-ingest external research.
4. Keep routes thin.
5. Preserve existing public endpoints (additive changes only).
6. Follow docs/GRAPH.md gardener budget rules: no unbounded loops, no full-graph scans.
7. Do not modify the tutor prompt pipeline or verifier.
8. Flashcard awareness must stay bounded (do not pass unbounded context to LLM).
9. Level-up quiz retry is OUT OF SCOPE — only practice quiz retry is allowed.

## Completed Work (Do Not Reopen Unless Blocked)

- `AR0–AR7` All agentic tracks complete
- `GP1–GP8` All graph UX polish Sprint 1 complete
- `BASE` Graph page, practice APIs, tutor drawers, switch payloads all exist

## Remaining Track IDs

- `UXF` Critical fixes — gardener commit, graph selection bugs (quick wins)
- `UXG` Graph visualization replacement — port LightRAG Sigma.js graph (13 slices)
- `UXP` Practice UX — unified flashcard viewer + quiz history browser
- `UXT` Tutor UX — onboarding auto-send, streaming status, graph-chat integration
- `UXI` Infrastructure — sources page, LLM caching, dev stats toggle
- `UXD` Documentation audit — verify all key docs reflect current implementation

## Child Plan Map

| Track | Child Plan | Status |
|---|---|---|
| `UXF` Critical fixes | `docs/ux_overhaul/01_critical_fixes_plan.md` | ✅ planned |
| `UXG` Graph replacement | `docs/ux_overhaul/02_graph_replacement_plan.md` | ✅ planned |
| `UXP` Practice UX | `docs/ux_overhaul/03_practice_ux_plan.md` | ✅ planned |
| `UXT` Tutor UX | `docs/ux_overhaul/04_tutor_ux_plan.md` | ✅ planned |
| `UXI` Infrastructure | `docs/ux_overhaul/05_infrastructure_plan.md` | ✅ planned |
| `UXD` Documentation audit | `docs/ux_overhaul/06_docs_audit_plan.md` | ✅ planned |

## Decision Log

1. **Gardener commit**: Add `db.commit()` in the route handler. Do not add auto-commit middleware — keep explicit commits for now.
2. **Graph replacement**: Replace the D3 force simulation with Sigma.js + graphology, following `docs/lightrag-graph-porting-guide.md`. The existing `concept-graph.tsx` will be archived and replaced.
3. **Flashcard unified stack**: Merge all flashcard runs for a concept into a single reviewable stack. "Generate more" appends to the stack. Exhaustion signal disables the generate button.
4. **Quiz history**: Show past quizzes in a list with date + score. Click to open and review. Retry button resets answers and lets user re-attempt (practice quizzes ONLY, not level-up).
5. **Wildcard/adjacent highlight fix**: When `selectConcept()` is called from the suggestions panel, also call `setFocusNodeId()`. This is subsumed by UXG (graph replacement) but should be fixed in UXF as a quick win if UXG hasn't started.
6. **Graph flicker**: The subgraph fetch on node click triggers full simulation restart. In UXF, decouple selection from data fetch. In UXG, this is inherently solved by Sigma.js architecture.
7. **Onboarding**: Show a confirm card ("Ready to learn about X? → Start learning") instead of populating the textbox.
8. **Streaming status**: Replace the growing activity rail with a single-line status that transitions between states. Only current step visible, animated with wavy text.
9. **LLM caching**: Structure messages for OpenAI prefix caching. Log `cached_tokens` in generation traces.
10. **Dev stats toggle**: Frontend-only via localStorage. Backend always includes `generation_trace`.
11. **Sources cursor**: Change `button:disabled { cursor: wait }` to `cursor: not-allowed`.
12. **Tier breakdown**: Backend returns per-tier counts in document list response. Frontend shows compact badges.
13. **Practice quiz retry ONLY**: Level-up quizzes cannot be retried — they affect mastery progression. Practice quizzes are safe to retry.
14. **Graph replacement scope**: UXG replaces concept-graph.tsx with a Sigma.js-based component. The graph detail panel (flashcards, quizzes, activity) remains and is enhanced in UXP. The data fetching hooks are adapted, not rewritten.
15. **UXG scope expansion (user request)**: UXG.8–UXG.13 added by user request to cover remaining LightRAG porting checklist features: camera control panel, extended layout suite (6 algorithms + play/pause), loading states, legend & status bar, settings panel with persistence, and node expand/prune. These are NOT audit-cycle reopenings — they are new scope added to the plan.
16. **Practice panel layout**: Remove duplicate inline flashcard/quiz buttons. Convert collapsible dropdowns to tabs or always-visible sections. User prefers avoiding dropdowns.
17. **Design porting**: Port original flashcard flip-card design and quiz marking design into the new unified components for visual consistency.
18. **Graph chat list**: Show existing chats for a concept in the graph detail panel, not just "start new chat".

## Deferred Follow-On Scope

- **Gardener edge reconnection**: Discovering missing edges between concepts from different documents. New feature, not UX polish.
- **Auto-commit middleware**: Consider after this sprint for safety, but don't introduce during active work.
- **Graph layout persistence**: Saving node positions across sessions. Nice-to-have for future.
- **Collaborative features**: Multi-user graph editing. Out of scope.

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in each child plan during the run.

## Removal Entry Template

```text
Removal Entry - <slice-id>

Removed artifact
- <file / function / route / schema / selector>

Reason for removal
- <why it was dead, duplicated, or replaced>

Replacement
- <new file/module/path or "none" if true deletion>

Reverse path
- <exact steps to restore or revert>

Compatibility impact
- <public/internal, none/minor/major>

Verification
- <tests or manual checks proving the replacement works>
```

## Current Verification Status

Current repo verification status:

- `PYTHONPATH=. pytest -q`: 922 passed (as of 2026-03-02)
- `npx vitest run` (from `apps/web/`): 106 passed
- `npm --prefix apps/web run typecheck`: not yet run this sprint

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `apps/api/routes/graph.py` | Gardener route never commits — merges/prunes silently lost |
| `apps/web/components/concept-graph.tsx` | Will be replaced by Sigma.js component (UXG) |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | Needs flashcard stack + quiz history integration (UXP) |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Onboarding + status animation (UXT) |
| `apps/web/styles/base.css` | `button:disabled { cursor: wait }` bug |
| `adapters/llm/providers.py` | No prompt caching instrumentation |

## Remaining Work Overview

### UXF. Critical Fixes

Quick wins that unblock other tracks. Fix the gardener transaction commit bug (data integrity), fix wildcard/adjacent selection not highlighting nodes, and reduce graph flicker on node click. These are small, surgical fixes.

### UXG. Graph Visualization Replacement

Replace the D3 force simulation (`concept-graph.tsx`) with a Sigma.js + graphology-based graph component, following `docs/lightrag-graph-porting-guide.md`. This is the largest track (13 slices): new rendering pipeline, layout algorithms, interaction model, search, and visual styling. Inherently fixes flicker, selection highlighting, and overall graph UX quality. UXG.1–7 cover core rendering, data binding, interaction, search, styling, subgraph, and detail-panel wiring. UXG.8–13 add camera controls, extended layouts, loading states, legend/status bar, settings panel, and node expand/prune.

### UXP. Practice UX

Redesign the flashcard and quiz experience in the graph detail panel:
- **Flashcards**: Unified stack across all runs for a concept. "Generate more" button that respects exhaustion. Review mode for past cards.
- **Quizzes**: History list with date/score. Click to open and review answers. Retry button for practice quizzes (not level-up).

### UXT. Tutor UX

Three tutor-side improvements:
- **Onboarding auto-send**: Confirm card + auto-generate on topic click
- **Streaming status**: Replace growing activity rail with ChatGPT-style single-line animated status
- **Graph-chat integration**: "Start new chat" button + active chats list in graph detail panel

### UXI. Infrastructure & Polish

Supporting improvements:
- **Sources page**: Fix upload cursor bug + add per-document tier breakdown
- **LLM prompt caching**: Structure messages for prefix caching, log cache hits
- **Dev stats toggle**: User-controllable generation trace visibility

### UXD. Documentation Audit

Audit and update all key documentation files to reflect the current state of the codebase after the UX overhaul:
- **API.md**: Verify all endpoints documented, especially new/changed ones from UXF, UXP, UXT
- **ARCHITECTURE.md**: Update if graph component architecture changed (D3 → Sigma.js), new state management patterns
- **FRONTEND.md**: Update component inventory, dependency list (new Sigma.js/graphology packages)
- **GRAPH.md**: Update gardener section (now commits), graph rendering architecture
- **OBSERVABILITY.md**: Verify trace/span documentation still accurate
- **PLAN.md**: Mark completed items, archive stale sections
- **PRODUCT_SPEC.md**: Update feature descriptions to match new UX
- **PROGRESS.md**: Update implementation progress with UX overhaul completion
- **PROMPTS.md**: Verify prompt inventory matches current templates

## Cross-Track Execution Order

Tracks should be executed in this order. Each track's child plan defines its internal slice order.

1. `UXF` Critical fixes — FIRST because gardener commit bug is data integrity
2. `UXG` Graph replacement — SECOND because it's the largest and subsumes graph UX issues
3. `UXP` Practice UX — THIRD because it builds on top of the graph detail panel (works regardless of graph engine)
4. `UXT` Tutor UX — FOURTH because it's independent of graph work
5. `UXI` Infrastructure — LAST because it's lowest priority and fully independent
6. `UXD` Documentation audit — FINAL because it documents the finished state

Dependencies between tracks:
- `UXG` is independent — the graph replacement doesn't depend on other tracks
- `UXP` is independent — works with either old or new graph detail panel
- `UXT` is independent
- `UXI` is independent
- `UXF` should go first as a quick win, but other tracks don't technically depend on it

**Parallel-safe**: UXP, UXT, and UXI can run in parallel after UXF is done. UXG is self-contained. UXD should run after all implementation tracks are complete.

## Master Status Ledger

| Track | Status | Last note |
|---|---|---|
| `UXF` Critical fixes | 🟢 done | All 3 slices complete (UXF.1–UXF.3) — gardener commit, selection highlight, flicker fix |
| `UXG` Graph replacement | 🟢 done | All 13 slices complete (UXG.1–UXG.13) — Sigma.js core + camera, layouts, loading, legend, settings, expand/prune |
| `UXP` Practice UX | 🟢 done | All 5 slices complete (UXP.1–UXP.5) — unified stack, generate-more, quiz history, layout cleanup, design port |
| `UXT` Tutor UX | 🔲 not started | 0/3 slices — onboarding, status animation, graph-chat nav all pending |
| `UXI` Infrastructure | 🔲 not started | 0/4 slices — sources, caching, dev stats, Phoenix Info tab all pending |
| `UXD` Documentation audit | 🔄 in progress | UXD.1 ✅ done (audit report). UXD.2–UXD.5 🔲 pending |

## Verification Block Template

For every completed slice, include this exact structure in the child plan:

```text
Verification Block - <slice-id>

Root cause
- <what made this area insufficient?>

Files changed
- <file list>

What changed
- <short description of the changes>

Commands run
- <tests / typecheck / lint commands>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
PYTHONPATH=. pytest -q
npx vitest run  # from apps/web/
npm --prefix apps/web run typecheck
```

## What Not To Do

Do not do the following during this project:

- do not restructure the agentic conductor or evidence planner
- do not modify the tutor prompt pipeline or verifier
- do not add new graph tiers or change the tier hierarchy
- do not add gardener edge reconnection (future feature)
- do not change the quiz creation or grading logic (only add retry and viewing)
- do not modify session management / dependency injection (just add commit calls)
- do not allow level-up quiz retry (mastery implications)
- do not introduce Tailwind CSS to the main app (LightRAG uses it, but our app uses custom CSS)

## Self-Audit Convergence Protocol

After all implementation tracks (UXF, UXG, UXP, UXT, UXI, UXD) reach "done" in the Master Status Ledger, the run enters a self-audit convergence loop. The agent does NOT stop — it automatically audits its own work.

### Why This Exists

Agents working top-to-bottom commonly miss edge cases, leave subtle regressions, or make assumptions invalidated by later slices. This catches those gaps without manual review cycles.

### Convergence Loop

```text
AUDIT_CYCLE = 0
MAX_AUDIT_CYCLES = 3

while AUDIT_CYCLE < MAX_AUDIT_CYCLES:
    AUDIT_CYCLE += 1
    
    1. Re-read docs/UX_OVERHAUL_MASTER_PLAN.md and every child plan in order.
    2. For each completed slice, verify:
       a. The code change described in the Verification Block still holds
          (files exist, tests pass, no regressions from later slices)
       b. The slice's exit criteria are still met
       c. No TODO/FIXME/HACK comments were left in changed files
       d. No dead imports, unused variables, or orphaned test stubs
       e. Cross-slice integration: does this slice's output still work
          with what later slices built on top of it?
    3. Run the full Verification Matrix:
       - PYTHONPATH=. pytest -q
       - npx vitest run (from apps/web/)
       - npm --prefix apps/web run typecheck
    4. Produce an Audit Report:
       - Cycle number
       - Slices re-examined
       - Issues found (with severity: critical / minor / cosmetic)
       - Slices to reopen (if any)
       - Verdict: CONVERGED (0 issues) or NEEDS_REPASS (N issues)
    5. If CONVERGED: update Master Status Ledger with "✅ audit-passed"
       and exit the loop.
    6. If NEEDS_REPASS:
       a. Reopen affected slices (set status back to pending in the
          child plan, add "Audit Cycle N" note)
       b. Re-implement only the reopened slices (same verification rules)
       c. Continue to next audit cycle
```

### Audit Cycle Budget

- **Maximum 3 audit cycles** to prevent unbounded loops.
- If cycle 3 still finds issues, produce a final Audit Report listing all remaining items and mark them as "deferred to manual review".
- The agent MUST NOT enter cycle 4. Instead, it produces a handoff summary for the human reviewer.

### Audit Report Template

```text
Audit Report — Cycle {N}

Slices re-examined: {count}
Full verification matrix: PYTHONPATH=. pytest -q / npx vitest run / typecheck

Issues found:
1. [{severity}] {slice-id}: {description}
   - File(s): {paths}
   - Expected: {what should be true}
   - Actual: {what was found}
   - Action: {reopen slice / cosmetic fix / defer}

Verdict: {CONVERGED | NEEDS_REPASS}
Slices reopened: {list or "none"}
```

### What the Audit Checks

| Check | What it catches |
|---|---|
| Verification Block accuracy | Slice claims that are no longer true |
| Exit criteria still met | Regressions from later slices |
| Test suite passes | Broken tests from cross-slice interactions |
| No TODO/FIXME/HACK left | Incomplete work markers |
| Dead code / unused imports | Cleanup missed during implementation |
| Cross-slice integration | Output of slice A still works after slice B modified shared code |
| Plan accuracy | Master/child plan status matches actual repo state |

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/UX_OVERHAUL_MASTER_PLAN.md now. This file is the cross-track source of truth.
Select the first child plan in execution order that still has incomplete slices.
Open and read that child plan.

You MUST implement slices in the EXACT execution order listed in the child plan.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in the child plan using the Removal Entry Template from the master plan.
For every removal, include:
Removed artifact
Reason for removal
Replacement
Reverse path
Compatibility impact
Verification

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade/shim instead of deleting immediately.
- Do not delete public contracts without a compatibility note and rollback path.
- Do not claim the removal is complete until the replacement behavior is verified.

After every 2 slices OR if your context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and restate which tracks and slices remain.

Work in small commits: chore(refactor): <slice-id> <short desc>.

If you discover a mismatch between current repo behavior and the assumptions in the plan, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

Execution loop:
1. Work on exactly one sub-slice at a time (PR-sized).
2. Run the verification matrix for the slice.
3. Produce the verification block in the child plan.
4. Move to the next slice.
5. After every 2 slices, re-read the master plan.
6. When a child plan is fully complete, update the Master Status Ledger in the master plan and move to the next child plan.

Stop only if:
- verification fails and you cannot resolve the failure
- the current assumptions no longer match the repository
- a blocker requires human decision

Do NOT stop because one child plan is complete. Move to the next incomplete track.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Pick the first incomplete child plan in execution order.
Begin with the first incomplete slice.

--- SELF-AUDIT PHASE ---

When docs/UX_OVERHAUL_MASTER_PLAN.md shows all tracks complete (UXF, UXG, UXP, UXT, UXI, UXD all done),
do NOT stop. Enter the self-audit convergence loop:

Audit loop (max 3 cycles):

1. Re-read docs/UX_OVERHAUL_MASTER_PLAN.md and every child plan (01 through 06).
2. For each completed slice, verify the Verification Block still holds:
   - Files exist and contain the described changes
   - Tests pass (PYTHONPATH=. pytest -q && npx vitest run && npm --prefix apps/web run typecheck)
   - Exit criteria are still met (no regressions from later slices)
   - No TODO/FIXME/HACK comments left in changed files
3. Check cross-slice integration:
   - Does each slice's output still work with what later slices built?
   - Are there dead imports, unused code, or orphaned tests?
4. Produce an Audit Report (use template from Self-Audit Convergence Protocol section).
5. If CONVERGED (0 issues found): mark all tracks as "audit-passed" in the
   Master Status Ledger. The run is now complete.
6. If NEEDS_REPASS: reopen affected slices, re-implement them with full
   verification, then start the next audit cycle.
7. If this is cycle 3 and issues remain: produce a final handoff report
   listing all remaining items for manual review. The run is complete.

The run is ONLY complete when:
- All tracks show "audit-passed" in the Master Status Ledger, OR
- 3 audit cycles have been exhausted and a handoff report is produced
```
