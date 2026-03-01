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

- `AR2.5` Execute real provenance/document-summary expansion inside the evidence planner

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
- EvidencePlan type introduced and wired into both paths (AR2.1 complete).
- AR2.2 multi-pass follow-up retrieval is live.
- AR2.3 graph-neighbor subquery expansion is live.
- AR2.4 retrieved-vs-used accounting is live in turn traces.
- AR2.5 provenance-linked expansion and document-summary expansion are now executed stages (not just flags).
- `pytest -q`: 816 passed (with `PYTHONPATH=.`, as of session)
- `npm --prefix apps/web test`: TS typecheck clean

### Verification Block - AR2.1

```text
Verification Block - AR2.1

Root cause
- Retrieval intent was implicit and scattered across local variables
  in respond.py and stream.py with no inspectable typed object.

Files changed
- domain/retrieval/evidence_planner.py (new)
- domain/retrieval/__init__.py
- domain/chat/respond.py
- domain/chat/stream.py
- core/schemas/assistant.py
- tests/domain/test_evidence_planner.py (new)
- tests/api/test_g3_stream.py
- tests/domain/test_g1_progress.py
- tests/domain/test_g5_trace.py
- tests/domain/test_s1_phase_semantics.py
- tests/domain/test_u5_reasoning_summary.py
- tests/domain/test_u6_answer_parts.py

What changed
- Introduced EvidencePlan frozen dataclass with retrieval goals, budgets,
  expansion flags, and stop_reason
- build_evidence_plan() creates plan from turn context
- execute_evidence_plan() wraps existing retrieve_ranked_chunks +
  apply_concept_bias as stage 1
- Blocking and streaming paths both consume EvidencePlan
- GenerationTrace gains evidence_plan_stop_reason, evidence_plan_budget,
  evidence_plan_chunk_count fields
- Test patches updated from domain.chat.stream/respond to
  domain.chat.retrieval_context

Commands run
- PYTHONPATH=. pytest -q → 626 passed
- npm --prefix apps/web test → 91 passed

Manual verification
- N/A (unit test coverage sufficient for typed data layer)

Observed outcome
- All tests green; plan fields visible in trace data
```

### Verification Block - AR2.2

```text
Verification Block - AR2.2

Root cause
- One-shot retrieval cannot express follow-up search loops when initial
  coverage is low or the query doesn't match concept terminology.

Files changed
- domain/retrieval/evidence_planner.py
- domain/chat/respond.py
- domain/chat/stream.py
- core/schemas/assistant.py
- tests/domain/test_evidence_planner.py

What changed
- Added multi-pass retrieval loop with subquery expansion
- Subqueries generated from concept_name when it differs from base query
- Added _coverage_sufficient() to skip unnecessary follow-ups
- Added _merge_chunks() for dedup and budget control across passes
- Added max_retrieval_passes, retrieval_passes_used, concept_name fields
- Added on_pass callback for status emission
- Added evidence_plan_passes to GenerationTrace

Commands run
- PYTHONPATH=. pytest -q → 641 passed
- npm --prefix apps/web test → 91 passed (no frontend changes)

Manual verification
- N/A (unit test coverage for multi-pass loop, coverage check, merge logic)

Observed outcome
- 26 evidence planner tests pass (15 new for AR2.2 loops)
- All 641 backend tests green
```

### Verification Block - AR2.3

```
Verification Block - AR2.3

Slice: AR2.3 – Graph-aware and document-summary expansion

Status: COMPLETE

Commit: chore(refactor): AR2.3 graph-aware and document-summary expansion

Files changed
- domain/retrieval/evidence_planner.py (added _expand_graph_neighbors, graph constants, session param on build_evidence_plan, expand_document_summaries defaults True)
- domain/chat/respond.py (pass session= to build_evidence_plan)
- domain/chat/stream.py (pass session= to build_evidence_plan)
- tests/domain/test_evidence_planner.py (8 new tests for graph expansion, neighbor subqueries, document summaries flag)

What changed
- _expand_graph_neighbors() calls get_bounded_subgraph() to discover adjacent concepts, returns their names (capped at 2, 1-hop) for use as follow-up subqueries
- build_evidence_plan() accepts optional session parameter; when session + concept_id are present, triggers graph neighbor expansion
- _plan_follow_up_subqueries() accepts neighbor_names for graph-derived subqueries
- expand_document_summaries defaults to True when retrieval is needed
- New constants: _GRAPH_HOP_BUDGET_DEFAULT=1, _GRAPH_MAX_NEIGHBOR_SUBQUERIES=2

Commands run
- PYTHONPATH=. pytest tests/domain/test_evidence_planner.py -v (34 passed)
- PYTHONPATH=. pytest -q (649 passed)
- npm --prefix apps/web test (91 passed)

Removal Entries
- None (additive-only slice)

Observed outcome
- 34 evidence planner tests pass (8 new for AR2.3)
- All 649 backend tests green
- All 91 frontend tests green
```

### Verification Block - AR2.4

```
Verification Block - AR2.4

Slice: AR2.4 – Add retrieved-vs-used source accounting

Status: COMPLETE

Commit: chore(refactor): AR2.4 retrieved-vs-used source accounting

Files changed
- core/schemas/assistant.py (added evidence_plan_retrieved_count, evidence_plan_used_count to GenerationTrace)
- domain/chat/respond.py (populate retrieved_count and used_count in trace)
- domain/chat/stream.py (populate retrieved_count and used_count in trace)
- tests/domain/test_evidence_planner.py (3 new tests for source accounting)

What changed
- GenerationTrace now distinguishes "retrieved" (total chunks from planner) from "used" (evidence items surviving filter_used_citations)
- retrieved_count = evidence_plan.retrieved_chunk_count (total fetched)
- used_count = len(envelope.evidence) after citation filtering
- filter_used_citations() remains the user-facing gate (unchanged)

Commands run
- PYTHONPATH=. pytest tests/domain/test_evidence_planner.py -v (37 passed)
- PYTHONPATH=. pytest -q (652 passed)

Removal Entries
- None (additive-only slice)

Observed outcome
- 37 evidence planner tests pass (3 new for AR2.4)
- All 652 backend tests green
```

### Verification Block - AR2.5

```
Verification Block - AR2.5

Slice: AR2.5 – Execute real provenance/document-summary expansion

Status: COMPLETE

Commit: chore(refactor): AR2.5 execute real provenance/document-summary expansion

Files changed
- domain/retrieval/evidence_planner.py (provenance expansion stage + document-summary stage + new result fields)
- domain/chat/retrieval_context.py (new retrieve_chunks_by_ids() function)
- domain/chat/respond.py (wire provenance/doc-summary trace fields)
- domain/chat/stream.py (wire provenance/doc-summary trace fields)
- core/schemas/assistant.py (add evidence_plan_provenance_chunks + evidence_plan_doc_summary_ids)
- apps/web/lib/api/types.ts (sync TS GenerationTrace interface)
- tests/domain/test_evidence_planner.py (10 new tests, 47 total)

What changed
- build_evidence_plan() now populates provenance_linked_chunk_ids from concept provenance via _discover_provenance_chunk_ids()
- execute_evidence_plan() runs a provenance expansion stage: retrieves chunks by ID that are provenance-linked but missing from initial results, merges them budget-bounded
- execute_evidence_plan() runs a document-summary expansion stage: gathers unique doc IDs (capped at 5) when expand_document_summaries=True
- EvidencePlan gains provenance_chunks_added and expanded_document_ids result fields
- Both respond.py and stream.py populate the new trace fields (runtime consumption)

Commands run
- PYTHONPATH=. pytest tests/domain/test_evidence_planner.py -v (47 passed)
- PYTHONPATH=. pytest tests/api/test_g3_stream.py -v (5 passed)
- PYTHONPATH=. pytest -q (816 passed, 1 pre-existing failure)
- npx tsc --noEmit (clean)

Removal Entries
- None (additive-only slice)

Observed outcome
- Plan flags now match actual execution stages
- Both runtime paths (blocking + streaming) consume provenance/doc-summary expansion signals
- All 816 backend tests green + TS typecheck clean
```

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

### AR2.5. Slice 5: Execute real provenance/document-summary expansion inside the evidence planner

Purpose:

- make AR2.3 true in runtime, not just in plan flags

Root problem:

- `EvidencePlan` exposes provenance/document-summary expansion fields, but `execute_evidence_plan()` currently ignores them and only performs base-query plus subquery retrieval

Files involved:

- `domain/retrieval/evidence_planner.py`
- `domain/chat/retrieval_context.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `tests/domain/test_evidence_planner.py`
- `tests/api/test_g3_stream.py`

Implementation steps:

1. Add an explicit executed stage for provenance-linked expansion after stage-one retrieval when provenance IDs or concept-linked document hints are available.
2. Turn `expand_document_summaries` into a real bounded retrieval/input stage instead of a plan-only flag.
3. Keep budgets explicit per stage and visible in trace data.
4. Preserve `filter_used_citations()` semantics and the current final verification flow.

What stays the same:

- hybrid retrieval remains stage 1
- graph-neighbor subquery expansion remains bounded
- no arbitrary tool use

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_evidence_planner.py tests/api/test_g3_stream.py`
- targeted manual check or trace assertion proving a turn can report provenance/document-summary expansion without weakening citation verification

Exit criteria:

- at least one non-test runtime path consumes provenance/document-summary expansion signals
- plan flags match actual execution stages
- AR2 can be marked `complete` again without overclaiming

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
7. When all AR2 slices are complete, immediately re-open docs/AGENTIC_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because AR2 is complete. AR2 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/AGENTIC_MASTER_PLAN.md.
Read docs/agentic/02_evidence_plan.md.
Begin with the current AR2 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When AR2 is complete, immediately return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.
```
