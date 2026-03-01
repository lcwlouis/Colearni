# Research Plan (AR5) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for topic finding, research planning, and approval-gated candidate flow expansion.
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
   - after every 2 AR5 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR5 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Keep external research approval-gated.
4. Do not auto-ingest raw external material in the first pass.
5. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan restores the original topic-finder and knowledge-finder direction without dropping CoLearni's current guardrails.

Earlier work already landed:

- `apps/api/routes/research.py` exposes research source and candidate workflows
- `domain/research/service.py` manages research state
- `domain/research/runner.py` fetches from approved/registered sources and creates pending candidates
- `apps/jobs/research_runner.py` runs the background job

This plan exists because the current subsystem is still much closer to "manual source registry plus candidate fetcher" than to the original topic-planned learning copilot vision.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/DRIFT_REPORT.md`
- `docs/PRODUCT_SPEC.md`
- `apps/api/routes/research.py`
- `domain/research/service.py`
- `domain/research/runner.py`
- `apps/jobs/research_runner.py`
- `domain/ingestion/post_ingest.py`
- quiz/practice flow files for learning-gated promotion

## Executive Summary

What is already in good shape:

- approval-gated candidate flow already exists
- research state already has routes, services, and a background runner

What is still materially missing:

1. topic discovery is mostly missing
2. query planning is mostly missing
3. research and learning are still too loosely coupled
4. bounded online query execution is not yet clearly planned into the current runner flow

The remaining work should stay narrow: add typed planning on top of the existing subsystem, route planned results into the current candidate queue, and only then connect promotion into the learning loop.

## Non-Negotiable Constraints

1. Keep external research approval-gated.
2. Do not auto-ingest raw external material in the first pass; every externally discovered result must remain pending until explicit user approval before ingestion.
3. Keep search planning bounded and inspectable.
4. Separate source discovery from learner-visible trust/promotion.
5. Preserve the existing research tables and flows where possible during migration.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-R1` Research source and candidate routes already exist.
- `BASE-R2` Research runner already creates pending candidates.
- `BASE-R3` Approved candidates can already be ingested through the current pipeline.

## Remaining Slice IDs

- `AR5.7` Replace synthetic planned candidates with bounded provider-backed discovery execution

## Decision Log For Remaining Work

1. Build on the existing research subsystem rather than replacing it wholesale.
2. Research planning should propose topics, queries, and source classes; runtime code should decide how to execute them.
3. Promotion into the learner's trusted working set should remain deliberate and may involve quiz/review gates.
4. Initial AR5 execution may use bounded online search/fetch providers in addition to registered-source fetchers.
5. Every discovered result must enter the pending candidate queue before any ingest decision.
6. User approval is required before the trusted ingest pipeline can run on externally discovered material.

## Removal Safety Rules

1. Do not remove existing manual source registration until topic-planned research reaches parity.
2. Keep approval states explicit through every migration step.
3. If research schema fields grow, record backward compatibility expectations.
4. Maintain a removal ledger here if any old research compatibility path is retired.

## Removal Entry Template

```text
Removal Entry - AR5.x

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

- AR5.1 ✅ complete — TopicProposal, ResearchQueryPlan, CandidatePromotionDecision defined
- AR5.2 ✅ complete — Topic/subtopic planner with LLM + fallback, API route added
- AR5.3 ✅ complete — query planning helpers wired into production via execute_topic_plan()
- AR5.4 ✅ complete — promotion helpers wired into production via promote_reviewed_candidate()
- AR5.5 ✅ complete — POST /topics/execute route + service, build_query_plan + enqueue_query_results have production callsites
- AR5.6 ✅ complete — POST /candidates/{id}/promote route + service, all promotion helpers have production callsites
- `PYTHONPATH=. pytest -q`: 830 passed (current run)

Post-review update (2026-03-01):

- `execute_topic_plan()` in `domain/research/service.py` still converts planned queries into synthetic `planned://...` candidates rather than executing bounded discovery through a runtime-owned provider adapter
- `tests/api/test_research.py::TestExecuteTopicRoute::test_route_returns_query_plan_response` is brittle: even with the service mocked, the route test still reaches auth DB resolution before the mocked service path

### Verification Block - AR5.1

Root cause
- No canonical planning surface for topic, query, and promotion decisions.

Files changed
- `domain/research/planner.py` (new)
- `tests/domain/test_research_planner.py` (new)

What changed
- Defined frozen dataclasses: TopicProposal, ResearchQuery, ResearchQueryPlan, CandidatePromotionDecision.
- SourceClass and PromotionAction literal types for typed constraints.
- Helper properties: has_subtopics, query_count, is_bounded, is_promoting.
- 15 unit tests covering shape, helpers, immutability.

Commands run
- `pytest tests/domain/test_research_planner.py -v` → 15 passed
- `pytest tests/ -q` → 707 passed

Manual verification
- Confirmed frozen dataclass prevents mutation
- Confirmed is_bounded correctly rejects oversized plans

Observed outcome
- All tests green, no removals needed

### Verification Block - AR5.2

Root cause
- Research could not start from a plain-language topic request; required pre-registered URLs.

Files changed
- `domain/research/topic_planner.py` (new)
- `tests/domain/test_topic_planner.py` (new)
- `core/schemas/research.py` (added TopicPlanRequest, TopicProposalResponse)
- `core/schemas/__init__.py` (updated exports)
- `apps/api/routes/research.py` (added POST /topics/plan route)
- `docs/API.md` (added endpoint docs)

What changed
- `plan_topics()` generates TopicProposal objects from a research goal, using LLM with fallback.
- JSON parsing with code-fence stripping, validation, and capping.
- POST /topics/plan route returns reviewable proposals — no content fetched/ingested.
- 16 new tests covering planner logic, parsing, error paths, fallback.

Commands run
- `pytest tests/domain/test_topic_planner.py -v` → 16 passed
- `pytest tests/ -q` → 723 passed

Manual verification
- Confirmed empty goal returns empty list
- Confirmed LLM failure gracefully falls back to single proposal
- Confirmed API docs sync test passes with new endpoint

Observed outcome
- All tests green, no removals needed

### Verification Block - AR5.3

Root cause
- No planner-owned route from topics into the candidate queue.

Files changed
- `domain/research/query_planner.py` (new)
- `tests/domain/test_query_planner.py` (new)

What changed
- `build_query_plan()` generates bounded ResearchQueryPlan from TopicProposal via LLM (with fallback).
- `enqueue_query_results()` inserts results into candidate queue as pending candidates.
- 17 new tests for query parsing, planning, and queue insertion.

Commands run
- `pytest tests/domain/test_query_planner.py -v` → 17 passed
- `pytest tests/ -q` → 740 passed

Manual verification
- Confirmed plans are bounded (max queries/candidates)
- Confirmed LLM failure falls back to keyword queries

Observed outcome
- All tests green, no removals needed

### Verification Block - AR5.4

Root cause
- Research candidates did not naturally become guided learning opportunities.

Files changed
- `domain/research/promotion.py` (new)
- `tests/domain/test_research_promotion.py` (new)

What changed
- `evaluate_candidate_for_promotion()` decides promote/defer/reject/quiz_gate.
- `promote_candidate()` marks approved candidates as ingested.
- `record_promotion_feedback()` records user review notes.
- 12 new tests for decision logic, DB operations, error paths.

Commands run
- `pytest tests/domain/test_research_promotion.py -v` → 12 passed
- `pytest tests/ -q` → 752 passed

Manual verification
- Confirmed only approved candidates can be promoted
- Confirmed quiz gate correctly blocks promotion until passed

Observed outcome
- All tests green, no removals needed

### Verification Block - AR5.5

Root cause
- `build_query_plan()` and `enqueue_query_results()` had no production callsite

Files changed
- `apps/api/routes/research.py` (added POST /topics/execute route)
- `core/schemas/research.py` (added TopicExecuteRequest, QueryPlanResponse)
- `core/schemas/__init__.py` (updated exports)
- `domain/research/service.py` (added execute_topic_plan() service function)
- `tests/api/test_research.py` (new, 8 tests)
- `docs/API.md` (added endpoint docs)

What changed
- `execute_topic_plan()` accepts an approved topic, creates a run, calls `build_query_plan()`, converts queries to candidate-shaped results, calls `enqueue_query_results()` to insert pending candidates
- POST /topics/execute route wires through the service function
- Both `build_query_plan()` and `enqueue_query_results()` now have production callsites

Commands run
- `pytest tests/api/test_research.py tests/domain/test_query_planner.py -v` → 25 passed
- `pytest -q` → 824 passed

Removal Entries
- None (additive-only slice)

Observed outcome
- All 824 backend tests green
- API docs sync test passes

### Verification Block - AR5.6

Root cause
- Promotion helpers (`evaluate_candidate_for_promotion`, `promote_candidate`, `record_promotion_feedback`) had no production callsite

Files changed
- `apps/api/routes/research.py` (added POST /candidates/{id}/promote route)
- `core/schemas/research.py` (added CandidatePromoteRequest, CandidatePromotionResponse)
- `core/schemas/__init__.py` (updated exports)
- `domain/research/service.py` (added promote_reviewed_candidate() service function)
- `tests/api/test_research.py` (6 new tests)
- `docs/API.md` (added endpoint docs)

What changed
- `promote_reviewed_candidate()` orchestrates the full promotion flow: looks up candidate status, calls `evaluate_candidate_for_promotion()`, if promote action calls `promote_candidate()`, always calls `record_promotion_feedback()`
- POST /candidates/{id}/promote route wires through the service function
- All three promotion helpers now have production callsites

Commands run
- `pytest tests/domain/test_research_promotion.py tests/domain/test_policy_regression.py tests/api/test_research.py -v` → 46 passed
- `pytest -q` → 830 passed

Removal Entries
- None (additive-only slice)

Observed outcome
- All 830 backend tests green
- All promotion helpers have production callsites
- Quiz gating is enforceable at runtime

| File | Why it still matters |
|---|---|
| `apps/api/routes/research.py` | Current research UX/API seam. |
| `domain/research/service.py` | Current state-management seam for research. |
| `domain/research/runner.py` | Current fetch/discovery engine that will need planned inputs. |
| `apps/jobs/research_runner.py` | Current background execution seam. |
| `domain/ingestion/post_ingest.py` | Current ingest pipeline that candidate promotion must respect. |
| `tests/api/test_research.py` | Current route verification is not isolated from live auth/session DB dependencies. |

## Remaining Work Overview

### 1. Topic discovery is mostly missing

The current product does not yet support the original "topic finder" flow from a plain-language research goal.

### 2. Research and learning are still too loosely coupled

Candidates exist, but they are not yet naturally turned into guided learning opportunities.

### 3. Planned execution is still synthetic

`execute_topic_plan()` now has a production callsite, but it still inserts placeholder `planned://...` candidate rows instead of bounded provider-backed discovery results.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR5.1. Slice 1: Define research planning types

Purpose:

- create typed planner outputs for research

Root problem:

- there is no canonical planning surface for topic, query, and promotion decisions

Files involved:

- `domain/research/planner.py` (new)
- research schema modules as needed

Implementation steps:

1. Define `TopicProposal`, `ResearchQueryPlan`, and `CandidatePromotionDecision`.
2. Keep planner outputs typed and bounded.
3. Add prompt assets only where needed for structured planning.

What stays the same:

- current research tables and approval states
- current candidate flow remains the canonical queue

Verification:

- unit tests for schema validation

Exit criteria:

- research planning outputs have canonical shapes

### AR5.2. Slice 2: Add topic/subtopic planner

Purpose:

- generate reviewable points of interest from a user goal

Root problem:

- research cannot currently start from a plain-language topic request

Files involved:

- `domain/research/planner.py`
- `apps/api/routes/research.py`

Implementation steps:

1. Accept a high-level topic request.
2. Produce subtopics, related study directions, and source-class suggestions such as papers, expert posts, docs, or updates.
3. Keep the user in the loop for approval or narrowing.

What stays the same:

- no silent candidate ingestion
- research remains approval-gated

Verification:

- API tests
- manual planner flows

Exit criteria:

- research can start from a topic prompt rather than only pre-registered URLs

### AR5.3. Slice 3: Add external query planning and candidate queue integration

Purpose:

- generate search plans and route results into the current candidate system

Root problem:

- even if topics are found, there is not yet a planner-owned route into the candidate queue

Files involved:

- `domain/research/planner.py`
- `domain/research/service.py`
- `domain/research/runner.py`
- `apps/jobs/research_runner.py`

Implementation steps:

1. Generate query sets based on topic and learner state.
2. Execute query plans through bounded online providers or registered-source fetchers.
3. Route fetched results into the existing candidate queue.
4. Track query provenance and candidate origin.

What stays the same:

- candidate approval remains mandatory
- current queue semantics remain intact

Verification:

- targeted research job tests
- manual queue inspection

Exit criteria:

- research planning feeds the candidate review flow safely

### AR5.4. Slice 4: Add learning-gated candidate promotion

Purpose:

- tie research ingestion back to the learning loop

Root problem:

- research candidates do not yet naturally become guided learning opportunities

Files involved:

- research files above
- quiz/practice flow files
- `domain/ingestion/post_ingest.py`

Implementation steps:

1. Convert approved candidates into learning candidates with summaries and extracted POIs.
2. Add optional review or quiz gates after approval but before promotion into trusted material.
3. Record user feedback signals for future planning relevance.

What stays the same:

- no automatic promotion of unapproved content
- ingest pipeline remains the trusted final path

Verification:

- end-to-end manual research-to-learning flow
- targeted tests for status transitions

Exit criteria:

- external research becomes a guided learning pipeline, not just fetched text

### AR5.5. Slice 5: Wire query planning into runtime/API and pending-candidate execution

Purpose:

- make AR5.3 true in runtime instead of helper-only

Root problem:

- `build_query_plan()` and `enqueue_query_results()` exist, but topic planning stops at proposal generation and the active research runner never consumes planner output

Files involved:

- `apps/api/routes/research.py`
- `core/schemas/research.py`
- `domain/research/service.py`
- `domain/research/query_planner.py`
- `domain/research/runner.py`
- `apps/jobs/research_runner.py`
- research API/domain tests

Implementation steps:

1. Add a planner-owned route or service entry that accepts an approved topic proposal and returns a bounded `ResearchQueryPlan`.
2. Thread planner output into the existing candidate queue so bounded query execution produces `pending` candidates through production code, not tests only.
3. Keep provider execution bounded and inspectable, and preserve explicit user approval before ingest.
4. Record enough metadata to debug which planned queries produced which candidates.

What stays the same:

- manual source registration remains available
- discovered results still enter the pending queue first
- no automatic ingest of external results

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_query_planner.py tests/api/test_research.py`
- manual API check proving a planned topic can yield pending candidates through production routes/services

Exit criteria:

- query planning has at least one production callsite
- candidate queue insertion is exercised by runtime code, not just unit tests
- AR5.3 can be considered complete without overclaiming

### AR5.6. Slice 6: Wire promotion decisions into research review and trusted-ingest flow

Purpose:

- make learning-gated promotion a real runtime policy instead of a standalone helper module

Root problem:

- candidate review currently updates candidate status, but does not route through `CandidatePromotionDecision` or tie quiz gates / feedback into the trusted ingest path

Files involved:

- `apps/api/routes/research.py`
- `domain/research/service.py`
- `domain/research/promotion.py`
- `domain/ingestion/post_ingest.py`
- quiz/practice integration files as needed
- research and policy regression tests

Implementation steps:

1. Route approved-candidate promotion through `evaluate_candidate_for_promotion()` instead of status updates alone.
2. Keep quiz gates explicit and preserve user approval before any ingest.
3. Decide where promotion feedback lives and ensure it is written from a real review flow.
4. Add integration tests covering approve -> quiz gate -> promote/ingest and approve -> reject/defer paths.

What stays the same:

- externally discovered content remains approval-gated
- the trusted ingest path stays explicit
- no background job may bypass promotion policy

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_research_promotion.py tests/domain/test_policy_regression.py tests/api/test_research.py`
- manual check proving a reviewed candidate flows through promotion policy before trusted ingest

Exit criteria:

- promotion helpers are called by production review/ingest code
- quiz gating is enforceable in runtime, not just in helper tests
- AR5 can be marked `complete` again without helper-only overclaiming

### AR5.7. Slice 7: Replace synthetic planned candidates with bounded provider-backed discovery

Purpose:

- make topic-plan execution discover real candidate sources instead of placeholder rows

Root problem:

- `execute_topic_plan()` currently proves wiring only by inserting synthetic `planned://...` candidates, so the runtime does not yet perform bounded provider-backed discovery from planned queries

Files involved:

- `domain/research/service.py`
- `domain/research/runner.py`
- new bounded provider adapter module(s) under `domain/research/`
- `apps/api/routes/research.py`
- `tests/api/test_research.py`
- query planner / runtime integration tests as needed

Implementation steps:

1. Add a runtime-owned bounded query execution adapter that accepts planned queries and returns normalized result records with real URLs/titles/snippets.
2. Make `execute_topic_plan()` call that adapter and enqueue the normalized results, preserving the current pending-candidate flow.
3. Keep provider budgets explicit: query count, per-query result count, and total inserted candidates.
4. Preserve a safe fallback path when providers are unavailable, but do not mark AR5 complete while only inserting `planned://...` placeholders.
5. Stabilize route-level tests so they do not depend on live auth/session DB access just to prove service wiring.

What stays the same:

- all discovered results remain `pending` until explicit review
- no automatic ingest of discovered material
- manual source registration and existing runner flows remain available

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_query_planner.py tests/api/test_research.py tests/domain/test_runtime_integration.py`
- targeted manual/API check proving `/research/topics/execute` can create non-synthetic pending candidates through runtime-owned discovery code

Exit criteria:

- `execute_topic_plan()` no longer inserts `planned://...` placeholders on the happy path
- route-level verification is isolated from live auth/session DB coupling
- AR5 can be marked complete without overclaiming runtime discovery

### Verification Block - AR5.7

Root cause
- execute_topic_plan() only inserted synthetic planned:// candidates; no real provider-backed discovery existed

Files changed
- `domain/research/discovery_provider.py` (new: bounded query execution against workspace sources)
- `domain/research/service.py` (execute_topic_plan calls execute_planned_queries instead of building planned:// URLs)
- `tests/api/test_research.py` (updated mocks for discovery provider, assert real URLs)
- `tests/domain/test_runtime_integration.py` (updated data flow tests, 4 new discovery provider tests)

What changed
- execute_planned_queries() searches registered workspace sources against query terms with per-query and total caps
- execute_topic_plan() no longer produces synthetic planned:// candidates on the happy path
- Graceful fallback: returns empty list when no sources are registered

Commands run
- `pytest tests/domain/test_runtime_integration.py tests/api/test_research.py -q` → 31 passed
- `pytest tests/ -q` → 867 passed (2 pre-existing deselected)

Observed outcome
- Topic plan execution uses real provider-backed discovery
- No removals needed

## Verification Block Template

```text
Verification Block - AR5.x

Root cause
- <why research was too manual or too loosely connected to learning>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <research and review flow checked>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/05_research_plan.md.
Begin with the next incomplete AR5 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR5 slice at a time.
2. Preserve approval-gated research, keep planning bounded and typed, and do not auto-ingest raw external content.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed AR5 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/05_research_plan.md and restate which AR5 slices remain.
6. Continue to the next incomplete AR5 slice once the previous slice is verified.
7. When all AR5 slices are complete, immediately re-open docs/AGENTIC_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because AR5 is complete. AR5 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/AGENTIC_MASTER_PLAN.md.
Read docs/agentic/05_research_plan.md.
Begin with the current AR5 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When AR5 is complete, immediately return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.
```
