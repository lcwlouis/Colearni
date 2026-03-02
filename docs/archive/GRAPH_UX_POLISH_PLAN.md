# Graph & UX Polish Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new plan; post-agentic follow-up fixes)

Template usage:
- This is a task-specific plan for graph UX, gardener effectiveness, flashcard awareness, and frontend polish fixes.
- It does not replace `docs/REFACTOR_PLAN.md` or `docs/AGENTIC_MASTER_PLAN.md`.
- All agentic tracks (AR0–AR7) are complete; this plan addresses post-review feedback on behavior and polish.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
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
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` with:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps
   - Observed outcome
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. This is a polish / fix pass. Do not mix in unrelated feature or architecture work.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

This document is the active execution plan for post-review fixes surfaced during manual testing of the completed agentic tracks (AR0–AR7).

What earlier work already landed:

- AR0/AR1: Conductor / turn planning
- AR2: Evidence planning with graph-aware retrieval
- AR3: Stream status protocol and frontend sync
- AR4: Learner profile assembly
- AR5: Research planner with bounded discovery
- AR7: Graph learning surface, concept activity panel, topic-lock UX, non-blocking switch banner
- AR6: Background copilots and regression coverage

Why this plan exists:

- Manual testing after AR7 completion revealed UX and behavior gaps that are not regressions but genuine missing polish.
- These fixes are independent of each other and narrowly scoped.

## Inputs Used

This plan is based on:

- `docs/AGENTIC_MASTER_PLAN.md` (completed master plan)
- `docs/agentic/07_graph_learning_surface_plan.md` (completed child plan)
- `docs/GRAPH.md` (graph gardener and resolver design)
- `docs/PRODUCT_SPEC.md` (product behavior expectations)
- manual testing observations from the user on 2026-03-01
- current repository layout as of 2026-03-01

## Executive Summary

What is already in good shape:

- concept activity panel reusable across graph and tutor surfaces
- topic-switch confidence threshold (0.75) and non-blocking banner
- flashcard exhaustion detection and fingerprint-based dedup
- wavy text animation on processing labels, dev stats toggle, workspace deletion, chat title "New Chat"

What is still materially missing:

1. Graph node selection does not zoom/pan to the focused node; the graph force simulation restarts on every click, causing visible jitter
2. The gardener only merges clusters; it does not prune orphan nodes and does not clean up when documents are deleted (default `prune_orphan_graph=False`)
3. NULL-like concept names can enter the graph when the LLM extraction produces artifacts like "(NULL)" in concept names, and more importantly, concepts can exist with no tier assignment at all because the extraction prompt makes tier optional
4. Concept resolution for switching searches all tiers including subtopic/granular, causing unnecessary switch triggers
5. Flashcard generation prompt does not include old flashcard content, so the LLM can regenerate semantically similar cards that pass fingerprint dedup
6. Health indicator checks once on mount and never polls again
7. Onboarding landing only shows gardener-suggested topics; no option to browse the graph or upload documents as a starting point
8. Empty tutor landing ("Start chatting to build context") provides no guidance when no documents or topics exist

## Non-Negotiable Constraints

1. Preserve `verify_assistant_draft()` as the final answer gate.
2. Keep topic lock, concept switching, and mastery gating runtime-owned.
3. Do not auto-ingest external research.
4. Keep routes thin.
5. Preserve existing public endpoints.
6. Follow docs/GRAPH.md gardener budget rules: no unbounded loops, no full-graph scans.
7. Flashcard awareness must stay bounded (do not pass unbounded context to LLM).

## Completed Work (Do Not Reopen Unless Blocked)

- `AR0–AR7` All agentic tracks complete (see `docs/AGENTIC_MASTER_PLAN.md`)
- `BASE-G1–G4` Graph page, practice APIs, tutor drawers, switch payloads all exist

## Remaining Slice IDs

- `GP1` Fix graph focus: zoom-to-node on selection instead of full simulation restart
- `GP2` Eliminate NULL-tier concepts: require tier assignment during extraction and backfill via gardener
- `GP3` Integrate orphan pruner into gardener run and fix document deletion default
- `GP4` Filter concept switching to topic/umbrella tiers only
- `GP5` Pass old flashcard content to generation prompt for true LLM awareness
- `GP6` Add periodic health dot polling
- `GP7` Redesign onboarding landing with graph browsing and document upload options
- `GP8` Topic completion cascading: passing a topic marks its subtopics as passed

## Decision Log For Remaining Work

1. Graph focus should use d3 zoom transform to center the selected node rather than restart the force simulation.
2. focusNodeId updates should NOT be in the draw() dependency array that triggers simulation restart; separate focus visual updates from layout computation.
3. The gardener "Run" button should trigger both merge passes AND orphan pruning, reporting both counts.
4. Document deletion should default `prune_orphan_graph=True` so orphans are always cleaned.
5. Every concept must have a valid tier — the extraction prompt should require it, extraction code should default to "granular" as fallback, and the gardener should backfill existing NULL-tier concepts on each run.
6. Concept switching should only propose switches to topic or umbrella tier concepts; subtopic and granular concepts should be suppressed as switch targets.
7. Flashcard generation should include up to N (e.g. 20) most recent existing flashcard front/back pairs as context so the LLM can avoid repeating content.
8. Health dot should poll every 30 seconds after initial check.
9. Onboarding card should offer three entry paths: pick a suggested topic, browse the graph, or upload a document.
10. When a topic-tier concept is marked as passed (mastery = learned), all subtopics directly under it should also be marked as passed.

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in this file during the run.

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

- `pytest -q`: ~876 passed (with `PYTHONPATH=.`, as of 2026-03-01)
- `npx vitest run` (from `apps/web/`): 106 passed
- `npm --prefix apps/web run typecheck`: not re-run during this planning pass

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `apps/web/components/concept-graph.tsx` | focusNodeId in draw deps causes full sim restart + jitter; no zoom-to-node |
| `domain/graph/extraction.py` | Tier is optional in extraction; NULL tiers allowed; no fallback |
| `core/prompting/graph/extract_chunk_v1.md` | Extraction prompt says tier is optional — should require it |
| `domain/graph/gardener.py` | Gardener does not integrate with orphan pruner |
| `apps/api/routes/knowledge_base.py` | Document deletion defaults `prune_orphan_graph=False` |
| `domain/chat/concept_resolver.py` | Concept switching searches all tiers; no topic/umbrella filter |
| `domain/learning/practice.py` | Flashcard generation prompt lacks old flashcard content |
| `apps/web/components/health-dot.tsx` | Single health check on mount; no periodic polling |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Onboarding/empty state landing is minimal |

## Remaining Work Overview

### 1. Graph focus and jitter

The graph re-runs the full D3 force simulation whenever `focusNodeId` changes because it is in the `draw()` dependency array. This makes every click feel like the entire graph is being reloaded. Additionally, there is no zoom/pan to the focused node—only dimming of non-focused nodes.

### 2. NULL-tier concepts in the graph

LLM extraction allows concepts to be created without a tier assignment. The prompt explicitly says "omit the field entirely" if uncertain. This results in concepts like "Reading or writing a sector" having tier=NULL while their neighbors are properly tiered as Granular. The extraction prompt should require tier, the code should default to "granular" as a fallback, and the gardener should backfill existing NULL-tier concepts.

### 3. Gardener and orphan cleanup

The gardener only merges clusters via LLM disambiguation. It does not prune orphan nodes whose provenance documents have been deleted. Document deletion defaults to not pruning orphans, so they accumulate silently.

### 4. Concept switch tier filtering

The concept resolver searches all tiers for switch candidates. The user wants switching limited to topic and umbrella concepts to reduce unnecessary switch triggers from subtopic/granular mentions.

### 5. Flashcard content awareness

Old flashcard content is never passed to the LLM generation prompt. Deduplication relies solely on post-generation fingerprint matching, which misses semantically similar but textually different cards.

### 6. Health indicator reliability

The health dot checks backend connectivity once on mount and never polls again. If the backend goes down after page load, the green dot remains misleading.

### 7. Onboarding and empty state

The onboarding card only shows gardener-suggested topics. Users have no way to browse the graph, search for a topic, or upload documents from the landing card. The fallback "Start chatting to build context" provides no actionable guidance.

### 8. Topic completion cascading

Passing a topic-tier concept (via level-up quiz) does not cascade mastery to its subtopics. The user expects that clearing a topic should imply its subtopics are considered learned.

## Implementation Sequencing

Each slice should end with green tests before the next slice starts.

### GP1. Slice 1: Fix graph focus — zoom-to-node without simulation restart

Purpose:

- Make node selection smoothly zoom/pan to the focused node without re-running the force simulation

Root problem:

- `focusNodeId` is in the `draw()` dependency array, so every click restarts the force simulation, causing visible jitter
- There is no zoom transform to center the selected node; only non-focused nodes are dimmed

Files involved:

- `apps/web/components/concept-graph.tsx`

Implementation steps:

1. Remove `focusNodeId` from the main draw/simulation dependency array.
2. Add a separate `useEffect` that fires when `focusNodeId` changes:
   - Find the focused node's current x, y coordinates from the simulation data.
   - Use the existing d3 zoom behavior (`zoomRef`) to smoothly transition the viewport to center on that node.
   - Apply focus dimming (opacity 0.2 for non-focused, 1.0 for focused + neighbors) without recreating DOM elements.
3. Keep the simulation restart only for actual data changes (nodes, edges, dimensions).
4. Ensure drag-end does not re-trigger the zoom-to-node effect.

What stays the same:

- Force simulation still runs on initial load and when nodes/edges change
- Focus dimming behavior preserved
- Zoom/pan interaction preserved

Verification:

- Manual check: clicking a node smoothly zooms to center it without graph jitter
- Manual check: clicking a second node transitions smoothly to the new node
- Manual check: clearing focus zooms out to show the full graph
- `npx vitest run` from `apps/web/`

Exit criteria:

- Node selection zooms to the focused node with a smooth transition
- No force simulation restart on focus change
- No visible jitter

### GP2. Slice 2: Eliminate NULL-tier concepts — require tier during extraction and backfill via gardener

Purpose:

- Every concept in the canonical graph must have a valid tier (umbrella, topic, subtopic, or granular)
- Concepts like "Reading or writing a sector" should not exist with tier=NULL while their neighbors are properly tiered

Root problem:

- The extraction prompt says "Only set tier when you are confident. If uncertain, omit the field entirely" — this allows NULL tiers
- The extraction code converts invalid tiers to `None` (extraction.py line 79)
- The resolver and gardener never backfill NULL tiers on existing concepts
- This leads to concepts with no tier, which confuses users and degrades graph quality
- Some NULL-tier concepts (e.g. "Reading or writing a sector") may actually be actions/processes that belong as edge descriptions rather than standalone concept nodes

Files involved:

- `core/prompting/graph/extract_chunk_v1.md` (extraction prompt)
- `domain/graph/extraction.py` (tier fallback)
- `domain/graph/gardener.py` (backfill pass)
- `domain/graph/types.py` (tier utilities)

Implementation steps:

1. Update the extraction prompt (`extract_chunk_v1.md`):
   - Change tier from optional to required: "You MUST assign exactly one tier to every concept."
   - Add guidance: "If a concept describes an action or process rather than a thing or idea, consider whether it belongs as an edge description instead of a concept."
   - Remove "If uncertain, omit the field entirely."
2. In `extraction.py`, add a fallback: if the LLM still returns no tier or an invalid tier, default to `"granular"` instead of `None`.
3. In `gardener.py`, add a tier-backfill pass at the start of the gardener run (before clustering):
   - Query concepts with `tier IS NULL` (bounded by `max_dirty_nodes_per_run`).
   - For each, use the LLM to infer the tier based on the concept name, description, and its edge neighbors.
   - Update the tier in the database.
   - Count these as part of the gardener's LLM budget.
4. Add a utility function `infer_tier_from_context()` in `domain/graph/types.py` that the gardener can call.
5. Add unit tests for the fallback and backfill behavior.

What stays the same:

- Valid tier assignments pass through unchanged
- Extraction still uses the LLM for primary tier classification
- Gardener budget rules (bounded LLM calls) still apply
- Concept name normalization unchanged

Verification:

- `PYTHONPATH=. pytest tests/domain/test_graph_extraction.py -q`
- `PYTHONPATH=. pytest tests/domain/test_gardener.py -q`
- New test: concept extracted without tier gets fallback "granular"
- New test: gardener run backfills NULL-tier concepts
- Manual check: after gardener run, no concepts remain with tier=NULL

Exit criteria:

- New concepts always get a tier during extraction (no more NULL tiers created)
- Gardener backfills existing NULL-tier concepts on each run
- No concepts with tier=NULL remain after a gardener pass

### GP3. Slice 3: Integrate orphan pruner into gardener and fix document deletion default

Purpose:

- Make the gardener button useful for cleaning up orphan nodes
- Ensure document deletion always prunes orphans by default

Root problem:

- Gardener only merges clusters; orphan nodes from deleted documents accumulate
- Document deletion defaults to `prune_orphan_graph=False`

Files involved:

- `domain/graph/gardener.py`
- `apps/api/routes/graph.py`
- `apps/api/routes/knowledge_base.py`
- `apps/web/features/graph/components/graph-viz-panel.tsx`
- `apps/web/lib/api/client.ts` (if response shape changes)

Implementation steps:

1. In `domain/graph/gardener.py`, add an orphan pruning step after the merge loop:
   - Call `prune_orphan_graph_nodes()` from `domain/graph/orphan_pruner.py`
   - Add pruned concept/edge counts to `GardenerRunResult`
2. Update the `GardenerRunResponse` schema to include `pruned_concepts` and `pruned_edges`.
3. In `apps/api/routes/knowledge_base.py`, change `prune_orphan_graph` default from `False` to `True`.
4. In `apps/web/features/graph/components/graph-viz-panel.tsx`, update the feedback message:
   - Show "Merged X concept(s), pruned Y orphan(s)" instead of just merge count.
   - If both are 0: "No changes needed — graph is clean."

What stays the same:

- Gardener merge logic unchanged
- Orphan pruner logic unchanged
- Document deletion endpoint signature unchanged (just default flipped)

Verification:

- `PYTHONPATH=. pytest tests/domain/test_gardener.py -q`
- Manual check: delete a document, then run gardener — orphan nodes should be cleaned
- Manual check: gardener button shows accurate feedback message

Exit criteria:

- Run Gardener button performs both merge and orphan cleanup
- Document deletion always prunes orphans by default
- UI feedback reflects actual work done

### GP4. Slice 4: Filter concept switching to topic/umbrella tiers only

Purpose:

- Prevent concept switching from triggering on subtopic and granular concept mentions

Root problem:

- `resolve_concept_for_turn()` searches all tiers for candidate concepts; mentions of subtopic/granular concepts trigger unnecessary switch suggestions

Files involved:

- `domain/chat/concept_resolver.py`

Implementation steps:

1. In the concept candidate query, add a tier filter: only return concepts with `tier IN ('topic', 'umbrella')` or `tier IS NULL` (for legacy untiered concepts).
2. Add a test verifying that subtopic/granular concepts are excluded from switch suggestions.
3. Keep the confidence threshold (0.75) intact.

What stays the same:

- Confidence-based switching policy unchanged
- Explicit user switch intent still works
- Concept resolution for evidence retrieval (not switching) continues to use all tiers

Verification:

- `PYTHONPATH=. pytest tests/domain/test_concept_resolver.py -v`
- New test: subtopic concept mention does not trigger switch suggestion

Exit criteria:

- Concept switching only proposes topic or umbrella tier concepts
- Subtopic/granular mentions do not trigger switch suggestions

### GP5. Slice 5: Pass old flashcard content to generation prompt

Purpose:

- Give the flashcard LLM awareness of existing cards so it can generate genuinely novel content

Root problem:

- The generation prompt contains only concept name, description, and adjacent concepts
- Old flashcard content is never shown to the LLM; dedup relies on post-generation fingerprint matching, which misses semantic duplicates

Files involved:

- `domain/learning/practice.py`
- Prompt asset for `practice_practice_flashcards_generate_v1` (if file-based)
- `core/prompting/` (prompt asset if exists)

Implementation steps:

1. In `_context()` or `_build_flashcard_prompt()`, load up to 20 most recent existing flashcard front/back pairs for the concept.
2. Include them in the prompt context under a key like `existing_flashcards` with instructions: "Do not repeat or closely paraphrase these existing flashcards."
3. If the prompt asset is file-based, update it to include the `existing_flashcards` section.
4. Keep the fingerprint dedup as a second safety net.
5. Bound the context: max 20 existing cards, truncate back text if needed.

What stays the same:

- Fingerprint-based dedup remains as a fallback
- Exhaustion detection unchanged
- Flash card generation API contract unchanged

Verification:

- `PYTHONPATH=. pytest tests/domain/test_practice.py -q`
- Manual check: generate flashcards twice for the same concept — second batch should not repeat first batch's content

Exit criteria:

- LLM sees existing flashcard content during generation
- Semantic duplication significantly reduced
- Context size stays bounded

### GP6. Slice 6: Add periodic health dot polling

Purpose:

- Make the health indicator reflect actual backend status over time

Root problem:

- Health dot checks once on mount and never polls again; backend outages after page load are invisible

Files involved:

- `apps/web/components/health-dot.tsx`

Implementation steps:

1. Replace the single `useEffect` with a polling interval (every 30 seconds).
2. Update status on each poll result.
3. Add a visual transition (e.g., brief orange flash) when status changes from ok to error or vice versa.
4. Clean up the interval on unmount.

What stays the same:

- Initial mount check preserved
- healthz endpoint unchanged

Verification:

- Manual check: stop the backend → health dot turns red within 30 seconds
- Manual check: restart the backend → health dot turns green within 30 seconds

Exit criteria:

- Health dot polls periodically and reflects current backend status

### GP7. Slice 7: Redesign onboarding landing with graph browsing and document upload options

Purpose:

- Give users actionable entry paths when starting a new workspace or chat

Root problem:

- Onboarding card only shows gardener-suggested topics; no way to browse graph, search for a topic, or upload documents
- Fallback "Start chatting to build context" provides no guidance

Files involved:

- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/styles/tutor.css`

Implementation steps:

1. Redesign the onboarding card to present three entry paths:
   - **Pick a suggested topic** (existing behavior, preserved)
   - **Browse the graph** (button that opens the graph page or graph drawer)
   - **Upload a document** (button/link that navigates to document upload, with copy explaining this is how the tutor learns)
2. Redesign the empty state (no documents, no topics) to show:
   - A welcome message explaining the tutor
   - A prominent "Upload your first document" CTA
   - A secondary "Or just start chatting" option
3. Improve the visual design of both cards to feel intentional rather than placeholder.

What stays the same:

- Suggested topic chips behavior unchanged
- Document upload flow unchanged (just linked from here)
- Graph page unchanged

Verification:

- Manual check: new workspace → see welcome card with upload CTA
- Manual check: workspace with documents → see topic suggestions + graph browse + upload options
- `npx vitest run` from `apps/web/`

Exit criteria:

- Users have clear entry paths from the tutor landing
- Empty state provides actionable guidance
- No placeholder-looking "Start chatting to build context" text

### GP8. Slice 8: Topic completion cascading to subtopics

Purpose:

- When a topic-tier concept is marked as learned, automatically mark its direct subtopics as learned

Root problem:

- Passing a level-up quiz for a topic-tier concept does not cascade mastery to its subtopics
- Students expect that mastering a topic implies its subtopics are understood

Files involved:

- `domain/learning/level_up.py` (or wherever mastery is updated after quiz grading)
- `domain/graph/explore.py` (to find subtopics of a concept)
- `domain/learner/profile.py` (mastery update)

Implementation steps:

1. After a concept's mastery is updated to "learned" (via level-up quiz pass):
   - Query the graph for all direct subtopics (concepts one hop away with tier = subtopic and edge direction parent → child).
   - For each subtopic that is not already "learned", update its mastery to "learned".
2. Only cascade downward (topic → subtopic → granular), never upward.
3. Add a flag or log entry indicating cascaded mastery vs. directly earned mastery.
4. Add unit tests for cascading behavior.

What stays the same:

- Level-up quiz creation, grading, and promotion unchanged
- Mastery update for the directly-quizzed concept unchanged
- Upward cascade never happens (passing subtopics does not auto-pass topic)

Verification:

- `PYTHONPATH=. pytest tests/domain/test_level_up.py -q`
- New test: passing a topic concept cascades mastery to subtopics
- New test: passing a subtopic does NOT cascade upward

Exit criteria:

- Passing a topic-tier concept marks its subtopics as learned
- Cascading is logged/flagged
- No upward cascading

## Execution Order (Update After Each Run)

1. `GP1` Graph focus — zoom-to-node without simulation restart ✅
2. `GP2` Eliminate NULL-tier concepts ✅
3. `GP3` Gardener + orphan pruner integration ✅
4. `GP4` Concept switch tier filtering ✅
5. `GP5` Flashcard old content awareness ✅
6. `GP6` Health dot polling ✅
7. `GP7` Onboarding landing redesign ✅
8. `GP8` Topic completion cascading ✅

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Block Template

For every completed slice, include this exact structure in the working report or PR note:

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

Slice-specific emphasis:

- `GP1`
  - Manual: click node → zoom/pan → click another → smooth transition
- `GP2`
  - `PYTHONPATH=. pytest tests/domain/test_graph_extraction.py -q`
  - `PYTHONPATH=. pytest tests/domain/test_gardener.py -q`
- `GP3`
  - `PYTHONPATH=. pytest tests/domain/test_gardener.py -q`
  - Manual: delete doc → run gardener → verify orphans removed
- `GP4`
  - `PYTHONPATH=. pytest tests/domain/test_concept_resolver.py -v`
- `GP5`
  - `PYTHONPATH=. pytest tests/domain/test_practice.py -q`
- `GP6`
  - Manual: stop backend → wait 30s → verify dot turns red
- `GP7`
  - Manual: empty workspace landing → verify CTAs
- `GP8`
  - `PYTHONPATH=. pytest tests/domain/test_level_up.py -q`

Manual smoke checklist:

1. Select a graph node → graph smoothly zooms to it, no jitter
2. Run Gardener → feedback shows merge + prune counts
3. Delete a document → orphan nodes automatically cleaned
4. Mention a subtopic in chat → no switch suggestion triggered
5. Generate flashcards twice → second batch has genuinely novel content
6. Stop backend → green dot turns red within 30s
7. New workspace → landing shows upload + browse options
8. Pass a topic quiz → subtopics marked as learned

## What Not To Do

Do not do the following during this pass:

- do not restructure the agentic conductor or evidence planner
- do not modify the tutor prompt pipeline or verifier
- do not add new graph tiers or change the tier hierarchy
- do not change the quiz creation or grading logic
- do not modify the research planner or candidate review flows

## Removal Ledger

Append removal entries here during implementation.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the remaining implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/GRAPH_UX_POLISH_PLAN.md now. This file is the source of truth.
You MUST implement slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/GRAPH_UX_POLISH_PLAN.md using the Removal Entry Template.
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

After every 2 slices OR if your context is compacted/summarized, re-open docs/GRAPH_UX_POLISH_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/GRAPH_UX_POLISH_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/GRAPH_UX_POLISH_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/GRAPH_UX_POLISH_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
