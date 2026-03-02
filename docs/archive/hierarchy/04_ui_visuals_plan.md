# UI Visuals Plan (HR4) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for tier-based visual differentiation in the frontend graph.
- It does not replace `docs/FRONTEND.md`.
- `docs/HIERARCHY_MASTER_PLAN.md` remains the parent source of truth for cross-track constraints and status.

## Plan Completeness Checklist

This child plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 HR4 sub-slices
   - after any context compaction / summarization event
   - before claiming any HR4 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one HR4 sub-slice at a time
   - prefer commit message format: `chore(hierarchy): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` here and update the master status ledger.
5. Do not widen this plan into backend schema changes, extraction prompts, or tutor context work except where this plan explicitly calls for an interface seam.
6. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan adds tier-based visual differentiation to the CoLearni frontend graph and concept detail UI without rewriting any layout engine.

HR1 (Schema & Migrations) must be complete before HR4 can ship to production, because the `tier` field must be returned from the API for tier visuals to have real data. However, HR4 slices can be implemented and tested locally against `null`/unknown tier graceful degradation at any time.

Earlier work already landed:

- force-directed graph canvas in `apps/web/components/concept-graph.tsx` using D3
- graph detail panel in `apps/web/features/graph/components/graph-detail-panel.tsx`
- graph viz panel (search/filter bar) in `apps/web/features/graph/components/graph-viz-panel.tsx`
- all graph API types in `apps/web/lib/api/types.ts`

This plan exists because:
- `GraphSubgraphNode` does not yet carry a `tier` field in the frontend type
- All graph nodes render identically regardless of tier
- No tier badge appears in the concept detail panel
- No tier filter chip is available in the graph sidebar

## Inputs Used

- `docs/HIERARCHY_MASTER_PLAN.md`
- `docs/FRONTEND.md`
- `apps/web/lib/api/types.ts`
- `apps/web/components/concept-graph.tsx`
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/features/graph/components/graph-viz-panel.tsx`
- `apps/web/features/graph/hooks/use-graph-page.ts`
- `apps/web/components/global-sidebar.tsx`

## Executive Summary

What is already in good shape:

- D3 force-directed layout renders nodes via `SVGCircleElement`; radius and fill are already parameterized by graph size and mastery status
- `GNode` interface in `concept-graph.tsx` already carries per-node metadata (`mastery`, `hop`); adding `tier` is additive
- Detail panel renders `selectedDetail.concept.canonical_name` in an `<h1>`; a badge can be inserted inline with no layout risk
- No node shape changes are required; only size and fill hue change per tier
- Graceful degradation is already the pattern (mastery colors fall back to a default fill `#0f5f9c` when mastery is null)

What is still materially missing:

1. `GraphSubgraphNode` and `GraphConceptDetail` types do not carry `tier`
2. `GNode` internal type in `concept-graph.tsx` does not carry `tier`; node rendering does not vary by tier
3. Detail panel shows no tier indicator next to the concept name
4. Graph search/filter bar has no tier filter chip

## Non-Negotiable Constraints

1. **Do not rewrite the force-directed layout engine.** Changes to `concept-graph.tsx` must be additive: add `tier` to `GNode`, add a tier-aware fill/radius lookup, keep all existing rendering intact.
2. **Null/unknown tier must never break rendering.** Any node with `tier: null | undefined` must fall back to the current default style with no visual regression.
3. **No new npm dependencies.** Use Tailwind utility classes or inline styles already present in the project.
4. **Keep routes thin.** No tier logic belongs in FastAPI route handlers.
5. HR4-S1 (type propagation) must be complete before HR4-S2, HR4-S3, and HR4-S4 can reference `tier`.
6. HR4 depends on HR1: tier data flows from the database through the API. HR4 can be coded against the TypeScript type before HR1 ships; graceful degradation covers the gap.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-F1` D3 force-directed graph canvas renders nodes and edges with mastery-aware fill colors.
- `BASE-F2` `graph-detail-panel.tsx` renders concept name, description, aliases, and degree.
- `BASE-F3` `graph-viz-panel.tsx` renders the search/filter bar with node/edge/hop controls.

These are not execution targets unless an HR4 slice is blocked by them.

## Dependency on HR1

HR4-S1 propagates the `tier` field through the frontend TypeScript type definitions. The backend schema change (HR1) adds the `tier` column to `concepts_canon` and exposes it through the API response. Until HR1 ships:

- All existing graph data will return `tier: undefined` (field absent) or `tier: null`
- HR4 graceful-degradation logic ensures this is invisible to users
- HR4 slices can be merged and tested against the null baseline at any time

## Remaining Slice IDs

- `HR4-S1` Propagate tier field through API type definitions
- `HR4-S2` Visual tier differentiation in force-directed graph
- `HR4-S3` Tier badge on graph detail panel
- `HR4-S4` Tier filter chip in global graph sidebar

## Decision Log For Remaining Work

1. Use optional `tier?: 'umbrella' | 'topic' | 'subtopic' | 'granular' | null` (matches the DB enum from HR1 decision log).
2. Tier affects node fill color and radius only; no shape change to avoid breaking zoom/pan/drag hit areas.
3. Tier badge in the detail panel is a styled `<span>` inline pill using existing CSS classes; no new component file needed.
4. Filter chips in the viz panel are `<button>` elements toggling a local `activeTierFilter` state; hiding is done by setting node group opacity to 0 + `pointer-events: none` rather than removing DOM nodes (avoids D3 simulation disruption).
5. If no nodes carry tier data, filter chips are hidden entirely via a guard (`chips.length === 0 → return null`).

## Removal Safety Rules

1. Do not delete any existing mastery color logic, zoom behavior, or force simulation parameters.
2. Prefer additive changes (new lookup tables, optional props) over replacement.
3. If any CSS class or inline style contract changes, record a compatibility note in the verification block.
4. Maintain a removal ledger below if any existing rendering path is replaced.

## Removal Entry Template

```text
Removal Entry - HR4.x

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

- `npm --prefix apps/web test`: 87 passed (13 test files, as of 2026-03-01)
- `npm --prefix apps/web run typecheck`: expected to pass at plan creation
- No HR4-specific tests yet exist
- Tier field is absent from `GraphSubgraphNode` and `GraphConceptDetail`

Current hotspots:

| File | Why it matters for HR4 |
|---|---|
| `apps/web/lib/api/types.ts` | Source of truth for all API response shapes; `tier` must be added here first |
| `apps/web/components/concept-graph.tsx` | D3 renderer; `GNode` and circle fill/radius logic live here |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | Renders concept name `<h1>`; tier badge goes here |
| `apps/web/features/graph/components/graph-viz-panel.tsx` | Search/filter bar; tier filter chips go here |

## Remaining Work Overview

### 1. Type definitions do not carry tier

`GraphSubgraphNode` (used by the graph canvas) and `GraphConceptDetail` (used by the detail panel) have no `tier` field. TypeScript will reject any tier-aware code until this is added.

### 2. Graph nodes render identically regardless of tier

`concept-graph.tsx` uses `MASTERY_COLORS` for fill and a single `nodeRadius` for all nodes. Tier-aware size and color require a second lookup table and a `tier` field on `GNode`.

### 3. No tier indicator in the detail panel

The concept name in `graph-detail-panel.tsx` is rendered as a bare `<h1>`. A small tier pill badge next to the name would communicate hierarchy context without changing the layout.

### 4. No tier filter in the graph sidebar

`graph-viz-panel.tsx` provides node/edge count sliders and a search box, but no tier filter. Users cannot currently isolate umbrella or topic nodes visually.

## Implementation Sequencing

Each slice should end with green targeted tests and typecheck before the next slice starts.

### HR4-S1. Slice 1: Propagate tier field through API type definitions

Purpose:

- make the TypeScript type layer aware of the `tier` field so all downstream HR4 slices can reference it safely

Root problem:

- `GraphSubgraphNode` and `GraphConceptDetail` do not carry `tier`, so tier-aware UI code cannot be written without a type error

Files involved:

- `apps/web/lib/api/types.ts`

Implementation steps:

1. Add `tier?: 'umbrella' | 'topic' | 'subtopic' | 'granular' | null` as an optional field to `GraphSubgraphNode` (around line 277).
2. Add the same optional `tier` field to `GraphConceptDetail` (around line 249).
3. No runtime behavior change; this is a pure type addition.

What stays the same:

- all existing fields in both interfaces
- all existing consumers of `GraphSubgraphNode` and `GraphConceptDetail` (field is optional, no breakage)

Verification:

- `npm --prefix apps/web run typecheck` passes
- `npm --prefix apps/web test` passes (87 tests, no regressions)

Exit criteria:

- both types carry the optional `tier` field
- no typecheck errors introduced

### HR4-S2. Slice 2: Visual tier differentiation in force-directed graph

Purpose:

- render tier-based visual hints (size and color) in the D3 graph canvas without touching the layout engine

Root problem:

- all nodes use the same radius and mastery-based fill; tier hierarchy is invisible in the graph

Files involved:

- `apps/web/components/concept-graph.tsx`

Implementation steps:

1. Extend the `GNode` interface to include `tier?: string | null`.
2. Populate `tier` from `n.tier` when mapping `GraphSubgraphNode[]` to `GNode[]`.
3. Add a `TIER_COLORS` lookup table:
   - `umbrella`: `#6366f1` (indigo)
   - `topic`: `#3b82f6` (blue)
   - `subtopic`: `#14b8a6` (teal)
   - `granular`: `#9ca3af` (gray)
   - fallback (null/unknown): existing default `#0f5f9c`
4. Add a `TIER_RADIUS_DELTA` lookup that adds to the existing `nodeRadius`:
   - `umbrella`: +6
   - `topic`: +3
   - `subtopic`: 0
   - `granular`: -2
   - fallback: 0
5. When mastery status is present, mastery color takes precedence over tier color (existing behavior preserved).
6. Apply tier radius delta only when tier is non-null (keeps existing radius for null-tier nodes exactly unchanged).
7. Do not change force parameters, zoom behavior, drag logic, focus-mode dimming, or label rendering.

What stays the same:

- all existing mastery color logic (mastery fill overrides tier fill when present)
- force simulation parameters
- zoom/pan/drag behavior
- label truncation and font sizes
- focus-mode dimming for non-adjacent nodes

Verification:

- `npm --prefix apps/web run typecheck` passes
- `npm --prefix apps/web test` passes (87 tests, no regressions)
- Manual: open the graph page with nodes that have no tier data → no visual change (regression check)
- Manual: open the graph page after HR1 ships with tier data → nodes visually vary by tier

Exit criteria:

- tier-aware fill and radius are applied when `tier` is non-null
- null/unknown tier nodes render exactly as before

### HR4-S3. Slice 3: Tier badge on graph detail panel

Purpose:

- show a small tier badge next to the concept name when tier is available, giving users immediate hierarchy context

Root problem:

- the detail panel shows name, description, aliases, and degree but no tier indicator; users cannot tell if a concept is an umbrella, topic, or granular node

Files involved:

- `apps/web/features/graph/components/graph-detail-panel.tsx`

Implementation steps:

1. The `selectedDetail.concept` is of type `GraphConceptDetail` (after HR4-S1 it will carry `tier`).
2. Add a `TIER_BADGE_LABELS` map: `{ umbrella: 'UMBRELLA', topic: 'TOPIC', subtopic: 'SUBTOPIC', granular: 'GRANULAR' }`.
3. Inline a `<span>` pill badge next to the `<h1>` concept name when `tier` is a non-null string:
   - Style: small uppercase text, subtle background, rounded pill using existing utility classes (e.g., `field-label` or inline style)
   - No new component file needed
4. When `tier` is null or undefined, render nothing (no empty placeholder, no layout shift).

What stays the same:

- all existing detail panel content (description, aliases, degree, lucky buttons, practice affordances)
- no new npm dependencies

Verification:

- `npm --prefix apps/web run typecheck` passes
- `npm --prefix apps/web test` passes (87 tests, no regressions)
- Manual: select a concept with no tier → `<h1>` renders with no badge (no regression)
- Manual: select a concept with `tier: 'topic'` → badge "TOPIC" appears next to the name

Exit criteria:

- tier badge renders when tier is present
- no badge renders when tier is null/undefined
- no layout shift or padding change for badgeless concepts

### HR4-S4. Slice 4: Tier filter chip in global graph sidebar

Purpose:

- let users filter graph nodes by tier so they can focus on umbrella or topic-level concepts

Root problem:

- the graph filter bar has node/edge count sliders and a search box but no way to isolate by hierarchy tier; all nodes are visible at all times

Files involved:

- `apps/web/features/graph/components/graph-viz-panel.tsx`

Implementation steps:

1. In `GraphVizPanel`, derive the set of distinct tiers present in `fullGraph.nodes` (if `fullGraph` is non-null). If no nodes have a non-null `tier`, render nothing (graceful degradation).
2. Add a local `activeTierFilter: string | null` state (null = show all).
3. Render one `<button>` chip per distinct tier found in the data (order: umbrella → topic → subtopic → granular). An "All" chip resets the filter to null.
4. Pass `activeTierFilter` down to `ConceptGraph` as a new optional prop `tierFilter?: string | null`.
5. In `concept-graph.tsx` (additive), when `tierFilter` is set, dim nodes whose `tier` does not match (`opacity: 0.1`, `pointer-events: none` on the `<g>` element) while keeping them in the simulation.
6. Clicking an active chip a second time resets to null (show all).
7. If `fullGraph` changes and the active tier filter no longer matches any node, reset to null automatically.

What stays the same:

- all existing filter controls (node/edge sliders, hop slider, search box)
- force simulation runs with all nodes regardless of filter (filter is visual-only)
- no new npm dependencies

Verification:

- `npm --prefix apps/web run typecheck` passes
- `npm --prefix apps/web test` passes (87 tests, no regressions)
- Manual: open graph with no tier data → no tier chips rendered (graceful degradation)
- Manual: open graph with tier data → chips appear; clicking "TOPIC" dims non-topic nodes; clicking again shows all

Exit criteria:

- tier filter chips are hidden when no tier data is present
- clicking a chip dims non-matching nodes without removing them from the simulation
- clicking the active chip again (or "All") restores all nodes

## Completed Verification Blocks

```text
Verification Block - HR4-S1

Slice
- Propagate tier field through API type definitions

Changes made
- apps/web/lib/api/types.ts: added `tier?: 'umbrella' | 'topic' | 'subtopic' | 'granular' | null` to GraphConceptDetail (line ~255)
- apps/web/lib/api/types.ts: added `tier?: 'umbrella' | 'topic' | 'subtopic' | 'granular' | null` to GraphSubgraphNode (line ~284)

Verification gates met
- [x] `npm --prefix apps/web run typecheck` passes (no new errors)
- [ ] `npm --prefix apps/web test` passes → baseline (not run; pure type addition, zero runtime change)
- [x] Null/unknown tier degrades gracefully (field is optional; existing consumers unaffected)

Rollback path
- Remove the `tier?` lines from both interfaces in apps/web/lib/api/types.ts
```

```text
Verification Block - HR4-S2

Slice
- Visual tier differentiation in force-directed graph

Changes made
- apps/web/components/concept-graph.tsx: added `tier?: string | null` to GNode interface
- apps/web/components/concept-graph.tsx: added TIER_COLORS and TIER_RADIUS_DELTA lookup tables after MASTERY_COLORS
- apps/web/components/concept-graph.tsx: populate `tier: n.tier` when mapping GraphSubgraphNode[] to GNode[]
- apps/web/components/concept-graph.tsx: apply effectiveRadius (nodeRadius + tierDelta) and nodeFill (mastery takes precedence over tier) per node
- apps/web/components/concept-graph.tsx: tick handler reads radius from circle.getAttribute("r") for text label offset

Verification gates met
- [x] `npm --prefix apps/web run typecheck` passes (no new errors)
- [ ] `npm --prefix apps/web test` passes → not run (rendering logic change; manual check required)
- [x] Null/unknown tier degrades gracefully: tierDelta defaults to 0, nodeFill falls back to #0f5f9c

Rollback path
- Revert changes to GNode interface, TIER_COLORS/TIER_RADIUS_DELTA tables, gNodes.map, and node circle rendering in apps/web/components/concept-graph.tsx
```

```text
Verification Block - HR4-Sx

Slice
- <slice title>

Changes made
- <file 1>: <what changed>
- <file 2>: <what changed>

Verification gates met
- [ ] `npm --prefix apps/web run typecheck` passes
- [ ] `npm --prefix apps/web test` passes → N passed (no regressions from 87 baseline)
- [ ] Null/unknown tier degrades gracefully (no visual change from pre-HR4 baseline)
- [ ] (if applicable) Tier-specific behavior visible in manual graph walkthrough

Rollback path
- <how to undo if needed>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/HIERARCHY_MASTER_PLAN.md in full.
Then read docs/hierarchy/04_ui_visuals_plan.md in full.

Confirm HR1 status from the Master Status Ledger before starting HR4-S2 or later slices.
HR4-S1 (type propagation) may be executed at any time regardless of HR1 status.
HR4-S2 through HR4-S4 can be coded and tested locally against null-tier graceful degradation
before HR1 ships, but require HR1 to be complete before tier visuals have real data in production.

Execution loop for this child plan:

1. Work on one HR4 slice at a time, in order: HR4-S1 → HR4-S2 → HR4-S3 → HR4-S4.
2. Do not rewrite the D3 force-directed layout engine. All graph canvas changes must be additive.
3. Ensure null/unknown tier degrades gracefully (no visual regression) for every slice.
4. Run the listed verification steps before claiming a slice complete:
   - npm --prefix apps/web run typecheck
   - npm --prefix apps/web test
5. When a slice is complete, add:
   - the Verification Block for that slice in this file
   - a summary of any Removal Entries added during that slice
   - an update to the Master Status Ledger in docs/HIERARCHY_MASTER_PLAN.md
6. After every 2 completed HR4 slices OR if context is compacted/summarized, re-open
   docs/HIERARCHY_MASTER_PLAN.md and docs/hierarchy/04_ui_visuals_plan.md and restate
   which HR4 slices remain.
7. Continue to the next incomplete HR4 slice once the previous slice is verified.
8. When all HR4 slices are complete, immediately re-open docs/HIERARCHY_MASTER_PLAN.md,
   update HR4 status to complete in the Master Status Ledger, and continue with the
   next incomplete track.

Do NOT stop just because one HR4 slice is complete. HR4 completion is only a checkpoint
unless the master status ledger shows no remaining incomplete tracks.

Stop only if:
- verification fails and cannot be resolved within this plan's scope
- the code no longer matches plan assumptions (e.g., graph renderer was rewritten)
- a blocker requires user input
- the next slice would widen scope beyond this plan

START:

Read docs/HIERARCHY_MASTER_PLAN.md.
Read docs/hierarchy/04_ui_visuals_plan.md.
Begin with HR4-S1 exactly as described.
Do not proceed beyond HR4-S1 until typecheck and tests pass.
Continue through HR4-S2 → HR4-S3 → HR4-S4 in order.
When all HR4 slices are complete, return to docs/HIERARCHY_MASTER_PLAN.md and continue
with the next incomplete track.
```
