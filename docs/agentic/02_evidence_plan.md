# Evidence Planning Plan (AR2) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for agentic RAG and evidence planning.
- It does not replace `docs/REFACTOR_PLAN.md`.
- `docs/AGENTIC_MASTER_PLAN.md` remains the parent source of truth for cross-track constraints and status.

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
   - after every 2 AR2 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR2 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one AR2 sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. Preserve grounding and citation enforcement while changing retrieval behavior.
5. This plan is for evidence planning only. Do not widen it into generic research crawling or prompt refactors.
6. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan upgrades the current retrieval path into agentic evidence planning.

Earlier work already landed:

- `domain/chat/retrieval_context.py::retrieve_ranked_chunks` already uses `HybridRetriever`
- concept biasing already exists via `apply_concept_bias()`
- evidence and citations are assembled in `domain/chat/evidence_builder.py`
- graph traversal APIs already exist in `domain/graph/explore.py`

This plan exists because the product already has the raw pieces, but the tutor still uses them in a mostly one-shot retrieval flow.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/DRIFT_REPORT.md`
- `docs/LLM_CALL_FLOWS.md`
- `domain/chat/retrieval_context.py`
- `domain/chat/evidence_builder.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/graph/explore.py`
- `apps/api/routes/graph.py`
- `core/schemas/assistant.py`

## Executive Summary

What is already in good shape:

- hybrid retrieval is already live
- evidence building and citation filtering already exist
- concept bias already connects chat and graph state

What is still materially missing:

1. there is no canonical `EvidencePlan`
2. retrieval is still mostly one-shot
3. graph traversal and provenance-linked chunks are underused as direct evidence sources
4. retrieved-vs-used source accounting is not explicit enough for debugging

The remaining work should stay narrow: keep the current hybrid retriever as stage 1, add a bounded evidence planner above it, then layer graph/provenance/document-summary expansion without weakening answer verification.

## Non-Negotiable Constraints

1. Preserve grounding and citation enforcement.
2. Keep bounded retrieval budgets.
3. Separate retrieved sources from used sources.
4. Treat the graph as a first-class retrieval surface, not only a post-retrieval ranking hint.
5. Do not let evidence planning silently widen into arbitrary tool use.
6. Keep the final answer path deterministic after evidence is selected.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-E1` Hybrid retrieval already exists in `domain/chat/retrieval_context.py`.
- `BASE-E2` Concept biasing already exists via `apply_concept_bias()`.
- `BASE-E3` Evidence and citation assembly already exist in `domain/chat/evidence_builder.py`.
- `BASE-E4` Canonical graph traversal already exists in `domain/graph/explore.py`.

## Remaining Slice IDs

- `AR2.1` Introduce `EvidencePlan`
- `AR2.2` Add bounded follow-up retrieval loops
- `AR2.3` Add graph-aware and document-summary expansion
- `AR2.4` Add retrieved-vs-used source accounting

## Decision Log For Remaining Work

1. Reuse the current hybrid retriever as the first-stage retrieval engine.
2. Evidence planning should propose expansions such as subqueries, graph-neighbor lookups, provenance-linked concept lookups, or document-summary lookups, then stop on budget.
3. "Used sources" must remain a post-generation subset of "retrieved sources".
4. The planner should produce safe activity events for the stream layer.

## Removal Safety Rules

1. Do not remove `retrieve_ranked_chunks()`; wrap it as stage 1 of evidence planning.
2. Do not remove `filter_used_citations()`; build on top of it.
3. Keep the current single-pass path available until the planner reaches parity.
4. Reuse current graph exploration and provenance paths before adding a separate graph retrieval subsystem.
5. Maintain a removal ledger here if any retrieval shim is removed.

## Removal Entry Template

```text
Removal Entry - AR2.x

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

- Hybrid retrieval exists and is live.
- Evidence and citation filtering exist and are live.
- Multi-step evidence planning is not confirmed in current runtime.
- `pytest -q`: not re-run during this planning pass.

Current hotspots:

| File | Why it still matters |
|---|---|
| `domain/chat/retrieval_context.py` | Owns the current stage-one retrieval path. |
| `domain/chat/respond.py` | Still performs largely one-shot evidence assembly. |
| `domain/chat/stream.py` | Needs parity with blocking evidence planning. |
| `domain/chat/evidence_builder.py` | Existing evidence/citation shaping must remain intact. |
| `domain/graph/explore.py` | Provides graph-neighborhood traversal that should become a first-class evidence source. |

## Remaining Work Overview

### 1. Retrieval is still mostly one-shot

The tutor retrieves chunks once, applies concept bias, and immediately assembles the prompt.

### 2. Coverage decisions are implicit

There is no explicit planning around contradiction checking, neighbor expansion, or subquery widening.

### 3. Graph retrieval is underused in the tutor path

The product already has canonical graph traversal in `get_bounded_subgraph()`, but tutor retrieval mostly uses the graph as concept bias rather than as a direct evidence planning surface.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR2.1. Slice 1: Introduce `EvidencePlan`

Purpose:

- make evidence selection explicit and inspectable

Root problem:

- current retrieval intent is spread across local variables and implicit sequencing

Files involved:

- `domain/retrieval/evidence_planner.py` (new)
- `domain/chat/respond.py`
- `domain/chat/stream.py`

Implementation steps:

1. Define a typed `EvidencePlan` with retrieval goals, budgets, and expansion decisions.
2. Capture first-pass retrieval results and next-step intents.
3. Make the planner reusable from blocking and streaming paths.

Suggested fields:

- `base_query`
- `subqueries`
- `candidate_concept_ids`
- `expand_graph_neighbors`
- `graph_root_concept_id`
- `graph_hop_budget`
- `provenance_linked_chunk_ids`
- `expand_document_summaries`
- `retrieval_budget`
- `stop_reason`

What stays the same:

- hybrid retrieval remains stage 1
- final answer verification remains unchanged

Verification:

- unit tests for plan creation and budget stopping

Exit criteria:

- retrieval intent is visible in code and trace data
- blocking and streaming paths can consume the same plan shape

### AR2.2. Slice 2: Add bounded follow-up retrieval loops

Purpose:

- let the tutor retrieve, reconsider, and retrieve again before generating

Root problem:

- one-shot retrieval cannot express follow-up search loops

Files involved:

- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/retrieval/evidence_planner.py`

Implementation steps:

1. Allow one or more bounded follow-up subqueries.
2. Stop when evidence coverage is sufficient or budgets are exhausted.
3. Emit status activities for each retrieval/thinking loop.

What stays the same:

- no arbitrary tool execution
- evidence/citation verification remains final-gate logic

Verification:

- targeted tests for repeated search/thinking cycles
- manual streaming checks that phase/activity changes are coherent

Exit criteria:

- tutor can legally alternate between search and reasoning before answering
- loop stopping is budgeted and inspectable

### AR2.3. Slice 3: Add graph-aware and document-summary expansion

Purpose:

- use the graph and stored summaries as bounded evidence expansion tools

Root problem:

- the tutor does not yet use graph neighborhoods and provenance-linked chunks as first-class evidence sources

Files involved:

- `domain/chat/evidence_builder.py`
- `domain/graph/explore.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`

Implementation steps:

1. Expand to graph-adjacent concepts when the plan calls for it.
2. Pull graph neighborhoods from canonical graph traversal and provenance-linked chunk sets when the plan calls for it.
3. Pull document summaries when broad context is needed.
4. Keep expansion bounded and logged.

Suggested evidence sources:

- hybrid chunk retrieval by lexical/vector query
- chunks linked through concept provenance
- bounded canonical graph neighborhoods
- document summaries for broader source framing

What stays the same:

- no general web search here
- citation policy remains evidence-driven

Verification:

- tests for expansion selection
- manual tutor questions spanning adjacent concepts

Exit criteria:

- retrieval is no longer limited to the original lexical query only
- graph evidence is a planner-owned surface, not just a score bias

### AR2.4. Slice 4: Add retrieved-vs-used source accounting

Purpose:

- make source reporting honest and debuggable

Root problem:

- today it is too easy to blur "looked at" with "actually used"

Files involved:

- `core/schemas/assistant.py`
- `domain/chat/evidence_builder.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`

Implementation steps:

1. Record retrieved evidence candidates separately from final cited/used sources.
2. Preserve `filter_used_citations()` as the user-facing citation gate.
3. Expose retrieved-vs-used counts in trace data.

What stays the same:

- final user-visible citations remain filtered and verified
- answer envelope remains grounded-response oriented

Verification:

- schema tests
- manual trace inspection

Exit criteria:

- source accounting distinguishes "looked at" from "actually used"

## Verification Block Template

```text
Verification Block - AR2.x

Root cause
- <why one-shot retrieval was insufficient>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <query flows tested>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/02_evidence_plan.md.
Begin with the next incomplete AR2 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR2 slice at a time.
2. Preserve hybrid retrieval as the stage-one engine, keep evidence/citation verification intact, keep budgets explicit, and record retrieved sources separately from used sources.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed AR2 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/02_evidence_plan.md and restate which AR2 slices remain.
6. Continue to the next incomplete AR2 slice once the previous slice is verified.
7. When all AR2 slices are complete, return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.
```
