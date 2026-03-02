# CoLearni UX Overhaul — Graph Visualization Replacement Plan

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
5. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

Replace the D3 force-simulation-based graph (`concept-graph.tsx`) with a Sigma.js + graphology-based component following the architecture documented in `docs/lightrag-graph-porting-guide.md`. This is the single highest-impact UX improvement — the user rated the current graph 3/10.

The LightRAG porting guide provides complete reference implementation details for all aspects of the graph: rendering pipeline, layout algorithms, interaction model, visual styling, search, and state management.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- `docs/lightrag-graph-porting-guide.md` (primary reference — 39KB porting guide)
- `apps/web/components/concept-graph.tsx` (existing D3 component to replace)
- `apps/web/features/graph/hooks/use-graph-page.ts` (existing data fetching)
- `apps/web/features/graph/components/graph-viz-panel.tsx` (existing panel wrapper)

## Executive Summary

What works today:
- D3 force simulation renders nodes and edges
- Focus mode with dimming
- Tier filtering and search highlighting
- Drag, zoom, pan interactions
- Node click → select → detail panel

What this track replaces:
1. D3 force simulation → Sigma.js WebGL renderer (much faster for large graphs)
2. Fixed force layout → Multiple switchable layouts (ForceAtlas2, Circular, etc.)
3. SVG DOM manipulation → WebGL rendering (no DOM nodes per graph node)
4. Manual zoom/pan code → Sigma.js built-in camera controls
5. Manual search highlighting → MiniSearch with fuzzy matching
6. Subtle blue stroke selection → Prominent node highlight with visual reducers

## Non-Negotiable Constraints

1. Must preserve the existing data model: `GraphConceptNode[]` + `GraphEdge[]` as the API contract
2. Must keep `onSelect(conceptId)` callback interface for the detail panel
3. Must keep `focusNodeId` for zoom-to-node behavior
4. Must keep tier filtering (umbrella, topic, subtopic, granular)
5. Do NOT introduce Tailwind CSS — adapt LightRAG patterns to our existing CSS custom properties
6. Do NOT add entity editing (LightRAG properties panel) — we use our own detail panel
7. Must work with the existing graph page layout (left: graph, right: detail panel)

## Completed Work

- Existing D3 graph component (to be archived, not deleted until replacement is verified)
- Graph data fetching hooks (`use-graph-page.ts`)
- Graph page layout

## Remaining Slice IDs

- `UXG.1` Install dependencies and scaffold Sigma.js component
- `UXG.2` Data pipeline — transform API data to graphology format
- `UXG.3` Core rendering — Sigma.js with node/edge programs and tier-based styling
- `UXG.4` Layout algorithms — ForceAtlas2 default + layout switcher
- `UXG.5` Interactions — node click, hover, drag, camera controls, zoom-to-node
- `UXG.6` Search — MiniSearch integration with fuzzy matching and highlighting
- `UXG.7` Integration — wire into graph page, replace old component, archive D3 code

## Decision Log

1. Use graphology + Sigma.js v3 as documented in the porting guide
2. ForceAtlas2 as the default layout (most natural for knowledge graphs)
3. Use CSS custom properties (not Tailwind) for theming — map LightRAG's color constants to our `--accent`, `--bg`, `--text`, etc.
4. Keep zustand for graph-specific state (layout settings, visibility) separate from our existing React state
5. Do NOT port the LightRAG properties panel — we have our own detail panel
6. Archive `concept-graph.tsx` as `concept-graph.d3-archive.tsx` during transition
7. The graph viz panel wrapper (`graph-viz-panel.tsx`) stays — only the inner graph component is replaced
8. Node size should reflect degree (number of connections) as in LightRAG
9. Edge should be curved (using `@sigma/edge-curve`) for visual clarity
10. Selected node should have a prominent highlight ring (border program) + label always visible

## Current Verification Status

- `npx vitest run`: 106 passed
- Existing graph renders correctly with D3

Hotspots:

| File | Role |
|---|---|
| `apps/web/components/concept-graph.tsx` | D3 component to be REPLACED (539 LOC) |
| `apps/web/features/graph/components/graph-viz-panel.tsx` | Panel wrapper — MODIFIED to use new component |
| `apps/web/features/graph/hooks/use-graph-page.ts` | Data hooks — MODIFIED for graphology transformation |
| `docs/lightrag-graph-porting-guide.md` | Reference implementation (39KB) |

## Implementation Sequencing

### UXG.1. Install dependencies and scaffold component

Purpose:
- Set up the Sigma.js ecosystem and create the component shell

Files involved:
- `apps/web/package.json`
- `apps/web/components/sigma-graph.tsx` (new)
- `apps/web/components/sigma-graph/` (new directory for sub-components)

Implementation steps:
1. Install core dependencies:
   ```bash
   cd apps/web && npm install graphology sigma @react-sigma/core \
     @react-sigma/layout-forceatlas2 @react-sigma/layout-force \
     @react-sigma/layout-circular @react-sigma/layout-noverlap \
     @sigma/edge-curve @sigma/node-border minisearch
   ```
2. Create `apps/web/components/sigma-graph.tsx` with:
   - Props matching existing `ConceptGraph` interface: `nodes`, `edges`, `focusNodeId`, `onSelect`, `onBackgroundClick`, `width`, `height`, `filteredTiers`
   - Basic `SigmaContainer` with empty graphology graph
   - Placeholder for layout and interactions
3. Verify it renders an empty graph without errors.

Verification:
- `npx vitest run`
- Manual: import new component in a test page → renders empty container

Exit criteria:
- Dependencies installed
- Scaffold component renders without errors
- Existing graph unchanged

### UXG.2. Data pipeline — API to graphology

Purpose:
- Transform `GraphConceptNode[]` + `GraphEdge[]` into a graphology `Graph` instance

Implementation steps:
1. Create `apps/web/lib/graph/transform.ts`:
   - `buildGraphologyGraph(nodes: GraphConceptNode[], edges: GraphEdge[]): Graph`
   - Map node attributes: `id`, `label` (canonical_name), `tier`, `size` (based on degree), `color` (based on tier), `x`/`y` (random initial positions via seedrandom)
   - Map edge attributes: `source`, `target`, `label` (description), `weight`, `type: "curvedArrow"`
2. Create `apps/web/lib/graph/constants.ts`:
   - Tier color mapping (reuse existing tier colors from concept-graph.tsx)
   - Node size range (min/max based on degree)
   - Default Sigma settings
3. Add tier filtering: set `hidden: true` attribute on nodes whose tier is filtered out.

Verification:
- Unit test: `transform.test.ts` — given mock nodes+edges, produces valid graphology graph
- `npx vitest run`

Exit criteria:
- API data cleanly transforms to graphology format
- Tier filtering works via node attributes
- Edge and node counts match

### UXG.3. Core rendering — Sigma.js with visual programs

Purpose:
- Render the graph with proper node/edge visual styling

Implementation steps:
1. In `sigma-graph.tsx`, use `SigmaContainer` with:
   - `@sigma/node-border` program for node rendering (tier-colored fill + selection border)
   - `@sigma/edge-curve` program for curved edges
   - Label rendering settings (font, size threshold, density)
2. Implement node visual reducers (from porting guide Section 7):
   - Default state: tier-colored node, size based on degree
   - Hover state: highlight node + label always visible
   - Selected state: bright border ring, label bold, slightly larger
   - Dimmed state: when another node is hovered/selected, dim non-neighbors
3. Implement edge visual reducers:
   - Default: thin, muted color
   - Highlighted: thicker, brighter (when connected to hovered/selected node)
   - Hidden: when both endpoints are filtered
4. Use CSS custom properties for colors, not hardcoded values.

Verification:
- `npx vitest run`
- Manual: graph renders with tier-colored nodes, curved edges, readable labels

Exit criteria:
- Nodes render with tier-appropriate colors and sizes
- Edges render as curved arrows
- Labels are readable and density-controlled
- Selected node is unmistakably highlighted

### UXG.4. Layout algorithms

Purpose:
- Provide a good default layout with option to switch

Implementation steps:
1. Use `@react-sigma/layout-forceatlas2` as the default:
   - Run for a fixed number of iterations (e.g., 500) then stop
   - Gravity, scaling, and edge weight settings from porting guide
2. Add a layout dropdown in `graph-viz-panel.tsx`:
   - ForceAtlas2 (default)
   - Circular
   - No-overlap (post-processing pass)
3. Layout changes should re-position nodes without recreating the graph.

Verification:
- Manual: graph auto-layouts on load, nodes don't overlap excessively
- Manual: switching layout smoothly re-arranges nodes

Exit criteria:
- Default layout produces a readable, well-spaced graph
- Layout switching works without data loss

### UXG.5. Interactions — click, hover, drag, camera

Purpose:
- Implement all user interaction patterns

Implementation steps:
1. **Node click**: Call `onSelect(conceptId)` and set internal selected state
2. **Background click**: Call `onBackgroundClick()` and clear selection
3. **Node hover**: Show highlight + label, dim non-neighbors
4. **Node drag**: Move node position (ForceAtlas2 supports this natively)
5. **Camera controls**: Zoom wheel, pan drag on background
6. **Zoom-to-node**: When `focusNodeId` changes, animate camera to center on that node (from porting guide Section 8)
7. **Zoom-to-fit**: Reset camera to show all nodes

Verification:
- Manual: click node → selects, shows in detail panel, highlights
- Manual: hover → label visible, neighbors highlighted
- Manual: drag node → moves smoothly
- Manual: zoom/pan → smooth camera control
- Manual: focusNodeId change → smooth camera animation

Exit criteria:
- All interaction patterns work smoothly
- No flicker on any interaction
- Selected node is always visually obvious

### UXG.6. Search — MiniSearch integration

Purpose:
- In-graph search with fuzzy matching and node highlighting

Implementation steps:
1. Create search index from node labels + descriptions using MiniSearch
2. Wire to existing search input in `graph-viz-panel.tsx`
3. On search: highlight matching nodes (bright), dim non-matching
4. Prefix + fuzzy matching (from porting guide Section 10)
5. Clear search → restore normal view

Verification:
- Manual: type in search → matching nodes highlighted
- Manual: fuzzy matching works (typos still find nodes)
- Manual: clear search → normal view restored

Exit criteria:
- Search finds nodes by name with fuzzy matching
- Visual highlighting for search results
- Search clears cleanly

### UXG.7. Integration — replace old component, archive D3

Purpose:
- Wire the new Sigma.js graph into the existing page and archive the old component

Implementation steps:
1. In `graph-viz-panel.tsx`, replace `<ConceptGraph>` with `<SigmaGraph>` using the same props.
2. Rename `concept-graph.tsx` → `concept-graph.d3-archive.tsx` (staged removal).
3. Update any imports that referenced the old component.
4. Verify all existing features work:
   - Tier filtering, search, gardener button, focus mode
   - Detail panel still populates on selection
   - Graph controls (max nodes/edges/depth) still function
5. Add a Removal Entry for the D3 component archival.

Verification:
- `npx vitest run`
- Full manual smoke test of all graph features
- Gardener button still works (run → feedback → graph updates)

Exit criteria:
- New Sigma.js graph is the active component
- Old D3 component archived (not deleted)
- All existing features preserved
- Graph UX significantly improved (target: 7+/10)

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

1. `UXG.1` Install deps + scaffold ✅
2. `UXG.2` Data pipeline ✅
3. `UXG.3` Core rendering ✅
4. `UXG.4` Layout algorithms ✅
5. `UXG.5` Interactions ✅
6. `UXG.6` Search ✅
7. `UXG.7` Integration + archive ✅

## Verification Matrix

```bash
npx vitest run  # from apps/web/
npm --prefix apps/web run typecheck
```

## Removal Ledger

Removal Entry - UXG.7

Removed artifact
- `apps/web/components/concept-graph.tsx` (renamed to `concept-graph.d3-archive.tsx`)

Reason for removal
- Replaced by Sigma.js-based `sigma-graph.tsx` which provides WebGL rendering, 
  ForceAtlas2 layout, fuzzy search, and improved interaction model.

Replacement
- `apps/web/components/sigma-graph.tsx` + `apps/web/components/sigma-graph/` sub-components

Reverse path
- `git mv apps/web/components/concept-graph.d3-archive.tsx apps/web/components/concept-graph.tsx`
- Revert import in `graph-viz-panel.tsx` from `SigmaGraph` back to `ConceptGraph`
- Revert import in `tutor-graph-drawer.tsx` from `SigmaGraph` back to `ConceptGraph`

Compatibility impact
- Internal only. No public API changes. The component prop interface is identical.

Verification
- `npx vitest run` passes
- `npm run typecheck` passes
- All graph interactions preserved: click, hover, drag, zoom, search, tier filter

Verification Block - UXG.7

Root cause
- D3 force simulation graph rated 3/10 — needed replacement with modern WebGL renderer

Files changed
- apps/web/components/concept-graph.tsx → concept-graph.d3-archive.tsx (archived)
- apps/web/features/graph/components/graph-viz-panel.tsx (import swap)
- apps/web/features/tutor/components/tutor-graph-drawer.tsx (import swap)

What changed
- Archived D3 graph component, wired Sigma.js replacement into graph page and tutor drawer

Commands run
- npx vitest run
- npm run typecheck

Manual verification steps
- Load graph page → Sigma.js graph renders with tier-colored nodes
- Click node → detail panel populates
- Hover → neighbor highlighting
- Search → fuzzy matching highlights nodes
- Tier filter toggles → nodes show/hide
- Zoom/pan → smooth camera control
- Tutor drawer graph → renders with SigmaGraph

Observed outcome
- All tests pass (117/117), graph renders correctly with new Sigma.js component

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/02_graph_replacement_plan.md.
Also read docs/lightrag-graph-porting-guide.md as the primary reference.
Begin with the next incomplete UXG slice exactly as described.

Execution loop for this child plan:

1. Work on one UXG slice at a time.
2. Preserve existing GraphConceptNode[]/GraphEdge[] API contract, onSelect(conceptId) callback, focusNodeId zoom-to-node, and tier filtering. Do NOT introduce Tailwind CSS. Use docs/lightrag-graph-porting-guide.md as the primary reference.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed UXG slices OR if context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/02_graph_replacement_plan.md and restate which UXG slices remain.
6. Continue to the next incomplete UXG slice once the previous slice is verified.
7. When all UXG slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXG is complete. UXG completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle, only work on slices marked as "reopened". Produce audit-prefixed Verification Blocks. Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/02_graph_replacement_plan.md.
Read docs/lightrag-graph-porting-guide.md.
Begin with the current UXG slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXG is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue with the next incomplete child plan.
```
