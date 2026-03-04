# CoLearni UX Overhaul — Critical Fixes Plan

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
2. A slice is ONLY complete with code changed + behavior verified + verification block produced.
3. Work PR-sized: `chore(refactor): <slice-id> <short description>`.
4. If a behavior change risk is discovered, STOP and update this plan.

## Purpose

Quick surgical fixes that unblock other tracks and resolve data integrity issues. These are 1–5 line changes with high impact.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- Code investigation of `apps/api/dependencies.py`, `apps/api/routes/graph.py`
- Code investigation of `apps/web/features/graph/components/graph-detail-panel.tsx`
- Code investigation of `apps/web/components/concept-graph.tsx`

## Executive Summary

What works: Gardener logic, orphan pruner logic, graph rendering, concept selection — all correctly implemented.

What's broken:
1. Gardener route never commits its DB transaction — all work silently rolled back
2. Wildcard/adjacent suggestion click doesn't set `focusNodeId` — node not highlighted
3. Node click triggers subgraph fetch which restarts simulation — visible flicker

## Non-Negotiable Constraints

1. Do not change `get_db_session` dependency — add explicit commits where needed.
2. Do not restructure the graph component — UXG track will handle the full replacement.
3. Keep fixes surgical and minimal.

## Completed Work

- Gardener merge logic, orphan pruner, tier backfill — all correct
- Graph focus zoom-to-node effect exists and works when focusNodeId is set

## Remaining Slice IDs

- `UXF.1` Fix gardener transaction commit
- `UXF.2` Fix wildcard/adjacent selection highlighting
- `UXF.3` Reduce graph flicker on node click

## Decision Log

1. Add `db.commit()` in the gardener route handler after `run_graph_gardener()` returns.
2. Audit other graph mutation routes for the same missing commit.
3. When `selectConcept()` is called from suggestion results, also call `setFocusNodeId()`.
4. Decouple concept detail fetching from graph re-rendering — fetch detail data but don't replace the graph's node/edge arrays on selection.

## Current Verification Status

- `PYTHONPATH=. pytest -q`: 922 passed
- `npx vitest run`: 106 passed

Hotspots:

| File | Why it matters |
|---|---|
| `apps/api/routes/graph.py` | Missing `db.commit()` after gardener run |
| `apps/api/dependencies.py` | `get_db_session` does not auto-commit |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | `selectConcept()` called without `setFocusNodeId()` for suggestions |
| `apps/web/features/graph/hooks/use-graph-page.ts` | `selectConcept()` triggers subgraph fetch causing graph redraw |

## Implementation Sequencing

### UXF.1. Fix gardener transaction commit

Purpose:
- Make gardener endpoint persist its changes to the database

Root problem:
- `get_db_session()` in `apps/api/dependencies.py` creates a session with `autocommit=False`. On cleanup, it only calls `session.close()` — never `session.commit()`. The gardener route handler never commits explicitly either. All gardener work (merges, prunes, tier backfills) is calculated, success counts are returned to the UI, but the transaction is silently rolled back on session close.

Files involved:
- `apps/api/routes/graph.py`

Implementation steps:
1. In the `run_gardener()` route handler, add `db.commit()` after `run_graph_gardener()` returns and before building the response.
2. Audit all other routes in `apps/api/routes/graph.py` for mutations that need commits. Add commits where missing.
3. Do a quick grep across `apps/api/routes/` for any other POST/PUT/PATCH/DELETE handlers that call domain functions with mutations but never commit. Document findings in this verification block.

What stays the same:
- Gardener logic, orphan pruner, tier backfill — unchanged
- `get_db_session` dependency — unchanged
- All other route handlers — unchanged unless same bug found

Verification:
- `PYTHONPATH=. pytest -q`
- Manual check: run gardener → refresh page → merges/prunes actually visible
- Manual check: delete document → run gardener → orphan nodes gone after refresh

Exit criteria:
- Gardener changes persist in the database
- No other mutation routes have missing commits

### UXF.2. Fix wildcard/adjacent selection highlighting

Purpose:
- When user clicks a wildcard or adjacent suggestion, the selected node should be highlighted (zoom-to-node + dimming)

Root problem:
- In `graph-detail-panel.tsx`, when a suggestion is selected, `selectConcept(pick.concept_id)` is called but `setFocusNodeId()` is NOT called. The focus highlight effect depends on `focusNodeId` being set.

Files involved:
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/features/graph/hooks/use-graph-page.ts` (if `selectConcept` needs to also set focus)

Implementation steps:
1. Option A (preferred): In `use-graph-page.ts`, make `selectConcept()` always set `focusNodeId` to the selected concept ID. This ensures any selection path (click, suggestion, search) highlights the node.
2. Option B: In `graph-detail-panel.tsx`, when suggestion is selected, explicitly call both `selectConcept()` and `setFocusNodeId()`.
3. Ensure deselecting (clicking background) clears both `selectedConcept` and `focusNodeId`.

What stays the same:
- Focus zoom-to-node effect — unchanged
- Suggestion fetching logic — unchanged

Verification:
- `npx vitest run` from `apps/web/`
- Manual check: click "Adjacent suggestion" → node highlights with zoom
- Manual check: click "Wildcard" → node highlights with zoom
- Manual check: click background → highlight clears

Exit criteria:
- All concept selection paths (click, suggestion, search) highlight the node
- Focus dimming and zoom work for suggestion-selected nodes

### UXF.3. Reduce graph flicker on node click

Purpose:
- Clicking a node should not cause the entire graph to visually reset

Root problem:
- When a node is clicked, `selectConcept()` in `use-graph-page.ts` calls `getConceptSubgraph()` which returns new `nodes` and `edges` arrays. These are passed to `ConceptGraph`, which has `[nodes, edges, ...]` in its `draw()` dependency array, triggering a full simulation restart — causing visible flicker/jitter.

Files involved:
- `apps/web/features/graph/hooks/use-graph-page.ts`
- `apps/web/components/concept-graph.tsx` (minimal change)

Implementation steps:
1. In `use-graph-page.ts`, do NOT replace the graph's node/edge data when a concept is selected for detail viewing. The detail panel should fetch concept info independently without affecting the graph visualization.
2. If the subgraph fetch is needed for expanding the visible graph, do it as an additive merge rather than a full replacement.
3. Alternative: Simply remove the subgraph fetch on selection — the full graph data is already loaded. The detail panel only needs `getConceptDetail()`, not `getConceptSubgraph()`.

What stays the same:
- Graph draws correctly on initial load
- Full graph fetch on page load and controls changes — unchanged
- Concept detail fetching for the side panel — unchanged

Verification:
- `npx vitest run` from `apps/web/`
- Manual check: click a node → no flicker, graph stays stable
- Manual check: click multiple nodes in sequence → smooth transitions
- Manual check: detail panel still shows correct concept info

Exit criteria:
- Node click does not restart the force simulation
- No visible flicker on selection
- Detail panel shows correct data

## Execution Order (Update After Each Run)

1. `UXF.1` Fix gardener transaction commit
2. `UXF.2` Fix wildcard/adjacent selection highlighting
3. `UXF.3` Reduce graph flicker on node click

## Verification Matrix

```bash
PYTHONPATH=. pytest -q
npx vitest run  # from apps/web/
```

## Removal Ledger

No removals expected in this track.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/01_critical_fixes_plan.md.
Begin with the next incomplete UXF slice exactly as described.

Execution loop for this child plan:

1. Work on one UXF slice at a time.
2. Add explicit db.commit() where needed but do not change get_db_session auto-commit middleware. Keep fixes surgical — UXG replaces the graph component entirely.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed UXF slices OR if context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/01_critical_fixes_plan.md and restate which UXF slices remain.
6. Continue to the next incomplete UXF slice once the previous slice is verified.
7. When all UXF slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXF is complete. UXF completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/01_critical_fixes_plan.md.
Begin with the current UXF slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXF is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue with the next incomplete child plan.
```
