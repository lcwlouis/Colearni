# Colearni Refinement — Frontend Graph Fixes Plan

Last updated: 2026-03-04

Parent plan: `docs/CREF_MASTER_PLAN.md`

Archive snapshots:
- `docs/archive/cref/06_frontend_graph_plan_v0.md`

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template (inherited from master)
5. removal entry template (inherited from master)
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (template in master plan).
5. If implementation uncovers a behavior change risk, STOP and update this plan and the master plan before widening scope.
6. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

This track fixes a camera behavior issue on the graph page: when selecting certain nodes, the camera animates to a position that's too far away, forcing the user to reset the view. This only happens on some nodes, suggesting it's related to node position coordinates or the camera animation ratio.

This is an independent frontend-only fix that can run in parallel with other tracks.

## Inputs Used

- `docs/CREF_MASTER_PLAN.md` (parent plan)
- `docs/FRONTEND.md` — Sigma.js component inventory
- `apps/web/components/sigma-graph/graph-events.tsx` — camera animation on node focus
- `apps/web/components/sigma-graph/camera-controls.tsx` — camera utilities

## Executive Summary

What works today:
- Node click triggers `onSelect` callback
- `focusNodeId` effect animates camera to the selected node
- Camera animation uses `ratio: 0.3` and `duration: 500ms`
- Most nodes animate correctly

What this track fixes:
1. Camera animation for outlier nodes that send the view too far away

## Non-Negotiable Constraints

1. Follow FRONTEND.md patterns
2. Do not change the graph data model or layout algorithm
3. Camera fix must work for all node positions, not just specific ones

## Completed Work (Do Not Reopen Unless Blocked)

- Sigma.js graph rendering
- ForceAtlas2 layout
- Camera controls (zoom, fit, reset)
- Node click/hover events

## Remaining Slice IDs

- `CREF6.1` Fix Node Selection Camera Behavior

## Decision Log

1. The camera animation should clamp the zoom ratio to prevent extreme zoom-out on outlier nodes.
2. Use Sigma's `camera.animate()` with a bounded ratio that accounts for node position relative to the graph center.

## Current Verification Status

- `cd apps/web && npm run lint`: baseline to be recorded
- `cd apps/web && npm run typecheck`: baseline to be recorded

Hotspots:

| File | Why it matters |
|---|---|
| `apps/web/components/sigma-graph/graph-events.tsx` | Camera animation on `focusNodeId` |
| `apps/web/components/sigma-graph/camera-controls.tsx` | Camera utility functions |

## Implementation Sequencing

### CREF6.1. Slice 1: Fix Node Selection Camera Behavior

Purpose:
- Fix the camera animation when selecting nodes so it doesn't zoom too far out on outlier nodes.

Root problem:
- The `focusNodeId` effect in `graph-events.tsx` animates the camera to the selected node with a fixed `ratio: 0.3`. For nodes that are far from the graph center (outliers from ForceAtlas2 layout), this ratio causes the camera to zoom out excessively, making the view unhelpful.

Files involved:
- `apps/web/components/sigma-graph/graph-events.tsx`
- `apps/web/components/sigma-graph/camera-controls.tsx` (optional helper)

Implementation steps:
1. In the `focusNodeId` effect, get the node's position from the graph
2. Calculate a dynamic ratio based on the node's distance from the current camera center or the graph bounding box
3. Clamp the ratio to a reasonable range (e.g., `Math.max(0.1, Math.min(0.5, calculatedRatio))`)
4. Alternative approach: instead of using `ratio`, use `sigma.getCamera().animate()` with explicit `x`, `y`, `ratio` where the ratio is calculated to show the node and its immediate neighbors
5. Add a fallback: if the camera would zoom out beyond the full graph view, use `fit-to-screen` followed by centering on the node
6. Test with nodes at various positions in the layout

What stays the same:
- Click/hover event handling
- Node selection callback
- Animation duration
- All other camera controls

Verification:
- `cd apps/web && npm run lint && npm run typecheck`
- Manual check: select various nodes including outlier nodes — camera stays at a useful zoom level
- Verify that after selecting a node, the node is visible and centered
- Verify reset view still works

Exit criteria:
- No node selection sends the camera too far away
- Selected node is always visible and centered
- Zoom level is reasonable for all node positions

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the master plan's Self-Audit Convergence Protocol may reopen slices in this child plan. The audit uses a **Fresh-Eyes** approach: the auditor treats each slice as if it has NOT been implemented, independently analyzes what should exist, then compares against actual code.

When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. The auditor's fresh-eyes analysis is recorded in the Audit Workspace below
4. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
5. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
6. The reopened slice is **re-implemented from scratch** — do not just patch the previous attempt. Re-read the slice definition, think about what needs to happen, implement it properly, then verify.
7. Only the specific issue identified in the Audit Report is addressed — do not widen scope

**IMPORTANT**: Tests passing is necessary but NOT sufficient for marking a reopened slice as done. The auditor must confirm the logic is correct through code review, not just test results.

## Audit Workspace

This section is initially empty. During the Self-Audit Convergence Protocol, the auditor writes their fresh-eyes analysis here. For each slice being audited:

1. **Before looking at any code**, write down what SHOULD exist based on the slice definition
2. **Then** open the code and compare against the independent analysis
3. Document gaps, verdict, and reasoning

```text
(Audit entries will be appended here during the audit convergence loop)
```

## Execution Order (Update After Each Run)

1. `CREF6.1` Fix Node Selection Camera Behavior

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
cd apps/web && npm run lint
cd apps/web && npm run typecheck
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read docs/CREF_MASTER_PLAN.md, then read docs/cref/06_frontend_graph_plan.md.
Begin with the next incomplete CREF6 slice exactly as described.

Execution loop for this child plan:

1. Work on one CREF6 slice at a time.
2. Follow FRONTEND.md patterns. Do not change graph data model or layout algorithm.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed CREF6 slices OR if context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and docs/cref/06_frontend_graph_plan.md and restate which CREF6 slices remain.
6. Continue to the next incomplete CREF6 slice once the previous slice is verified.
7. When all CREF6 slices are complete, immediately re-open docs/CREF_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because CREF6 is complete. CREF6 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

If this child plan is being revisited during an audit cycle:
- Treat every reopened slice as if it has NOT been implemented.
- In the Audit Workspace, write what SHOULD exist BEFORE looking at code.
- Then compare against actual implementation.
- Re-implement from scratch if gaps are found — do not just patch.
- Tests passing is NOT sufficient — confirm logic correctness through code review.
- Only work on slices marked as "reopened". Do not re-examine slices that passed the audit.

START:

Read docs/CREF_MASTER_PLAN.md.
Read docs/cref/06_frontend_graph_plan.md.
Begin with the current CREF6 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When CREF6 is complete, immediately return to docs/CREF_MASTER_PLAN.md and continue with the next incomplete child plan.
```
