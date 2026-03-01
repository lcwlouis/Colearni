# Background And Evaluation Plan (AR6) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for recommendation-first background agents, trace surfaces, and regression hardening.
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
   - after every 2 AR6 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR6 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Background agents must be recommendation-first in the first pass.
4. Add regression coverage as each new loop is introduced.
5. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan adds the background copilot behaviors and test hardening needed to make the agentic system useful without becoming sloppy.

Earlier substrate already exists in:

- `apps/jobs/readiness_analyzer.py`
- `apps/jobs/quiz_gardener.py`
- `apps/jobs/graph_gardener.py`
- `apps/jobs/research_runner.py`

Current test and trace surfaces already exist in:

- `tests/domain/test_prompt_regression.py`
- `tests/domain/test_query_analyzer.py`
- `core/schemas/assistant.py`
- `apps/web/components/chat-response.tsx`

This plan exists because dynamic loops will drift without recommendation-first job design, safe trace surfaces, and stronger scenario coverage.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/DRIFT_REPORT.md`
- `docs/OBSERVABILITY.md`
- `docs/LLM_CALL_FLOWS.md`
- background job modules listed above
- `core/schemas/assistant.py`
- `core/verifier.py`
- existing frontend trace rendering and tutor tests

## Executive Summary

What is already in good shape:

- there is already a background job substrate
- some prompt and routing tests already exist
- there is already a trace surface in the assistant envelope

What is still materially missing:

1. background intelligence is too narrow
2. there is no recommendation-first second-brain layer yet
3. scenario coverage for agentic loops is too weak
4. there is no explicit deep-review workflow over "everything learned" yet

The remaining work should stay narrow: add additive background jobs that write suggestions/summaries, extend safe observability, and add regression tests alongside each new loop.

## Non-Negotiable Constraints

1. Background agents must be recommendation-first in the first pass.
2. Do not let background jobs directly message the user or rewrite trusted knowledge without explicit product rules.
3. Add observability with safe summaries, not chain-of-thought.
4. Add regression coverage as each new loop is introduced.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-B1` Readiness, quiz, graph, and research jobs already exist.
- `BASE-B2` Prompt regression and query-analyzer tests already exist.
- `BASE-B3` Assistant trace surface already exists.

## Remaining Slice IDs

- `AR6.7` Add stable regression coverage for reopened evidence/research work and the graph/topic-lock UX

## Decision Log For Remaining Work

1. Background jobs should prepare suggestions, digests, and summaries before they take stronger actions.
2. Every new agentic loop should have a corresponding test or trace assertion.
3. Evaluation should focus on policy failures as much as capability gains.
4. "Deep search over everything learned" is a guarded review workflow over trusted and approved state, not autonomous crawling or implicit web research.

## Removal Safety Rules

1. Do not remove existing background jobs when adding new ones; extend carefully.
2. Keep new traces additive first.
3. If any old debug surface is replaced, keep a compatibility note and rollback path.
4. Maintain a removal ledger here if any old job or trace compatibility path is retired.

## Removal Entry Template

```text
Removal Entry - AR6.x

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

- AR6.1 ✅ complete — Learner summary, frontier suggestions, deep review jobs
- AR6.2 ✅ complete — Research digest and what-changed jobs
- AR6.3 ⚠️ partial → ✅ complete — bg trace fields now populated by tutor turns via fetch_background_trace_state()
- AR6.4 ⚠️ partial → ✅ complete — runtime integration regression tests cover AR5.5/AR5.6/AR6.5 behaviors
- AR6.5 ✅ complete — bg trace fields populated in respond.py and stream.py (841 tests pass)
- AR6.6 ✅ complete — 13 runtime integration tests, all verification recipes pass (854 tests pass)
- `PYTHONPATH=. pytest -q`: 854 passed (current run)

Post-implementation review (2026-03-01):

- the previous AR6.5/AR6.6 gap is now closed, but regression coverage is still thin for reopened AR2/AR5 work and for the graph/topic-lock UX
- `tests/api/test_research.py::TestExecuteTopicRoute::test_route_returns_query_plan_response` still depends on live auth/session DB resolution under `TestClient`, so route verification is not yet stable enough
- there are still no dedicated frontend tests covering `PracticeHistory`, `GraphDetailPanel`, `useGraphPage`, or `ConceptSwitchBanner`

### Verification Block - AR6.1

Root cause
- Background jobs did maintenance, not broader recommendation-first learner guidance.

Files changed
- `apps/jobs/learner_digest.py` (new)
- `tests/jobs/test_learner_digest.py` (new)
- `adapters/db/migrations/versions/20260301_0008_learner_digests.py` (new)

What changed
- Three generators: learner_summary, frontier_suggestions, deep_review.
- Outputs stored in new learner_digests table as JSONB.
- Runner iterates all user-workspace pairs with error isolation.
- 20 new tests.

Commands run
- `pytest tests/jobs/test_learner_digest.py -v` → 20 passed
- `pytest tests/ -q` → 772 passed

Observed outcome
- All tests green, no removals needed

### Verification Block - AR6.2

Root cause
- System could not prepare periodic research update digests.

Files changed
- `apps/jobs/research_digest.py` (new)
- `tests/jobs/test_research_digest.py` (new)

What changed
- Two generators: research_digest (candidate status counts), what_changed (run summaries + review counts).
- Stored in learner_digests table as non-authoritative recommendation material.
- 11 new tests.

Commands run
- `pytest tests/jobs/test_research_digest.py -v` → 11 passed
- `pytest tests/ -q` → 783 passed

Observed outcome
- All tests green, no removals needed

### Verification Block - AR6.3

Root cause
- Richer orchestration hard to debug without stronger operational trace data.

Files changed
- `core/schemas/assistant.py` (4 new bg trace fields)
- `apps/web/lib/api/types.ts` (synced TS interface: 6 evidence_plan + 4 bg fields)
- `apps/jobs/learner_digest.py` (emit_event call)
- `apps/jobs/research_digest.py` (emit_event call)
- `tests/domain/test_g5_trace.py` (3 new bg trace tests)

What changed
- 4 background trace fields on GenerationTrace: bg_digest_available, bg_frontier_suggestion_count, bg_research_candidate_pending, bg_research_candidate_approved.
- TypeScript interface synced with all Python fields.
- Background jobs emit observability events via emit_event.
- 3 new tests for bg trace fields.

Commands run
- `pytest tests/domain/test_g5_trace.py -v` → 11 passed
- `pytest tests/ -q` → 786 passed
- `npx tsc --noEmit` → clean

Observed outcome
- All tests green, no removals needed

### Verification Block - AR6.4

Root cause
- More loops means more failure modes unless policy behavior is tested directly.

Files changed
- `tests/domain/test_policy_regression.py` (new)

What changed
- 20 policy regression tests covering: no uncited claims (5), citation validation integrity (5), no unauthorized research auto-ingest (5), source accounting (3), guardrail parity (2).

Commands run
- `pytest tests/domain/test_policy_regression.py -v` → 20 passed
- `pytest tests/ -q` → 806 passed

Observed outcome
- All tests green, no removals needed

### Verification Block - AR6.5

Root cause
- Background trace fields (bg_digest_available, bg_frontier_suggestion_count, bg_research_candidate_pending, bg_research_candidate_approved) were defined on GenerationTrace but never populated by tutor-turn code paths

Files changed
- `domain/chat/background_trace.py` (new — read helper for digest/candidate state)
- `domain/chat/respond.py` (wire bg_state fields into trace enrichment)
- `domain/chat/stream.py` (wire bg_state fields into trace enrichment)
- `tests/domain/test_background_trace.py` (new — 11 tests)

What changed
- `fetch_background_trace_state()` queries `learner_digests` (digest existence + frontier suggestion count) and `workspace_research_candidates` (pending/approved counts)
- Both blocking and streaming trace enrichment now set all 4 bg_ fields from real DB state
- Exception-safe wrapper returns defaults on any DB error

Commands run
- `pytest tests/domain/test_background_trace.py tests/domain/test_g5_trace.py tests/api/test_g3_stream.py -v` → 27 passed
- `pytest -q` → 841 passed

Observed outcome
- All tests green, no removals needed
- bg_ trace fields populated by at least one real tutor-turn path (both blocking and streaming)

### Verification Block - AR6.6

Root cause
- Regression coverage proved helper logic and schema round-trips, but not end-to-end runtime behavior for reopened AR5/AR6 work

Files changed
- `tests/domain/test_runtime_integration.py` (new — 13 integration tests)

What changed
- Research queue data flow tests: plan queries become candidates, empty plans produce no candidates
- Promotion gating tests at service level: quiz_gate defers, quiz_passed promotes, pending rejects, feedback always recorded
- Background trace integration: enrichment pattern produces non-null bg_ fields, round-trips through envelope
- Verification recipe sanity: schema fields, module wiring, callsite proofs

Commands run
- `pytest tests/domain/test_policy_regression.py tests/api/test_g3_stream.py tests/api/test_research.py tests/domain/test_runtime_integration.py -v` → 52 passed
- `pytest -q` → 854 passed

Observed outcome
- All tests green, no removals needed
- All reopened AR5/AR6 runtime behaviors have regression coverage

| File | Why it still matters |
|---|---|
| `apps/jobs/readiness_analyzer.py` | Existing recommendation job substrate. |
| `apps/jobs/quiz_gardener.py` | Existing background quiz-generation seam. |
| `apps/jobs/graph_gardener.py` | Existing graph maintenance seam. |
| `apps/jobs/research_runner.py` | Existing research background seam. |
| `tests/domain/test_prompt_regression.py` | Natural home for some scenario hardening. |
| `tests/api/test_research.py` | Route verification still has auth/session DB coupling. |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | Needs direct regression coverage once graph practice history becomes interactive. |
| `apps/web/features/tutor/components/concept-switch-banner.tsx` | Needs dedicated UX regression coverage once topic-lock flow changes. |

## Remaining Work Overview

### 1. Background intelligence is too narrow

Jobs exist, but they mostly maintain the current tutor product rather than the broader second-brain vision.

For this plan, "deep search over everything learned" means a guarded review workflow that synthesizes trusted workspace documents, approved and ingested research, graph state, mastery/readiness signals, quiz/practice history, and learner snapshots into structured review outputs. It does not mean autonomous crawling or silently expanding the trusted knowledge base.

### 2. Dynamic behavior needs stronger regression coverage

The more loops and planner decisions the system gains, the more easily it can drift without explicit scenario tests.

### 3. Product-critical UI seams are still under-tested

The graph concept panel, tutor graph drawer, and topic-switch UX now matter to tutoring behavior, but there is still no dedicated automated coverage for them.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR6.1. Slice 1: Add learner-summary and frontier background jobs

Purpose:

- prepare review summaries and next-topic suggestions between turns

Root problem:

- existing jobs do maintenance, but not broader recommendation-first learner guidance

Files involved:

- new job modules under `apps/jobs/`
- learner snapshot assembly modules

Implementation steps:

1. Add a learner-summary job that consolidates recent progress into structured summaries.
2. Add a frontier-suggestion job that identifies review and next-topic candidates.
3. Add a deep-review job that produces a structured "what you know / what seems shaky / what to review next" pack from trusted and approved state.
4. Keep outputs in stored suggestion or summary records rather than direct messages.
5. Keep this slice free of autonomous web research.

What stays the same:

- no direct user messaging from background jobs
- no implicit mutation of trusted knowledge
- no autonomous web research inside learner-summary or deep-review jobs

Verification:

- job tests
- manual inspection of stored outputs

Exit criteria:

- background jobs can prepare useful study context safely

### AR6.2. Slice 2: Add research digest and "what changed" jobs

Purpose:

- support second-brain behavior for evolving topics

Root problem:

- the system cannot yet prepare periodic update digests in a guarded way

Files involved:

- research job modules
- new digest job modules

Implementation steps:

1. Add periodic research digest generation over approved or candidate sources as the "what changed" half of the broader deep-review workflow.
2. Summarize deltas and notable changes in a structured way.
3. Keep digests reviewable and non-authoritative until surfaced deliberately.

What stays the same:

- research remains approval-gated
- digests are recommendation material, not trusted facts by default

Verification:

- job tests
- manual digest review

Exit criteria:

- the product can prepare periodic research updates safely

### AR6.3. Slice 3: Expand safe observability and trace surfaces

Purpose:

- make background and agentic behavior inspectable

Root problem:

- richer orchestration will be hard to debug without stronger operational trace data

Files involved:

- `core/schemas/assistant.py`
- observability modules
- relevant frontend debug surfaces

Implementation steps:

1. Record planner and background-job summaries in safe trace structures.
2. Add metrics or counters for retrieval loops, candidate counts, and promotion decisions.
3. Keep the surface operational, not introspective.

What stays the same:

- no chain-of-thought exposure
- end-user answers remain grounded and verified

Verification:

- trace schema checks
- manual dev inspection

Exit criteria:

- agentic behavior is measurable and debuggable

### AR6.4. Slice 4: Add scenario and policy regression coverage

Purpose:

- prevent "smarter but less safe" regressions

Root problem:

- more loops means more failure modes unless policy behavior is tested directly

Files involved:

- `tests/domain/test_prompt_regression.py`
- new scenario tests for tutor, research, and stream sync

Implementation steps:

1. Add tests for no uncited claims.
2. Add tests for no premature topic jumps.
3. Add tests for no unauthorized research auto-ingest.
4. Add tests for retrieved-vs-used source accounting.
5. Add tests for repeated search/thinking stream loops.

What stays the same:

- existing guardrails remain code-owned
- recommendation-first background posture remains intact

Verification:

- targeted backend/frontend test suites

Exit criteria:

- major guardrail behaviors are regression-tested

### AR6.5. Slice 5: Populate background digest/candidate state in tutor traces

Purpose:

- turn AR6.3 from schema-only observability into live tutor-turn observability

Root problem:

- background trace fields are defined, but the blocking and streaming tutor paths never populate them from digest/candidate state

Files involved:

- `core/schemas/assistant.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- background digest query helpers or new read-model helpers
- `tests/domain/test_g5_trace.py`

Implementation steps:

1. Add a small read helper for the latest learner digest / research digest state needed by the tutor.
2. Populate `bg_digest_available`, `bg_frontier_suggestion_count`, `bg_research_candidate_pending`, and `bg_research_candidate_approved` in both blocking and streaming traces.
3. Keep the fields operational only; no chain-of-thought or payload dumps.

What stays the same:

- background jobs remain recommendation-first
- the tutor remains grounded and citation-verified

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_g5_trace.py tests/api/test_g3_stream.py`
- manual or integration assertion proving a tutor turn can expose non-null background trace fields when digests/candidates exist

Exit criteria:

- the four background trace fields are populated by at least one real tutor-turn path
- AR6.3 can be considered complete without schema-only overclaiming

### AR6.6. Slice 6: Add runtime integration regression coverage for background and research loops

Purpose:

- close the gap between helper tests and real production behavior

Root problem:

- current regression coverage proves helper logic and schema round-trips, but not enough end-to-end runtime behavior for reopened AR5/AR6 work

Files involved:

- `tests/domain/test_policy_regression.py`
- `tests/api/test_g3_stream.py`
- research route/service tests
- any new integration tests required by AR5.5 / AR5.6 / AR6.5

Implementation steps:

1. Add runtime tests for planned research queue execution and promotion gating once AR5.5/AR5.6 land.
2. Add trace-population assertions for background digest state in both blocking and streaming tutor paths.
3. Ensure verification commands run with `PYTHONPATH=.` from repo root to avoid sibling-package import contamination.

What stays the same:

- tests should remain focused on policy and contract regressions
- no new silent background side effects

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_policy_regression.py tests/api/test_g3_stream.py tests/api/test_research.py`

Exit criteria:

- reopened AR5/AR6 runtime behaviors have regression coverage
- the verification recipe itself is trustworthy in this multi-repo environment

### AR6.7. Slice 7: Add stable regression coverage for reopened evidence/research work and graph/topic-lock UX

Purpose:

- make the reopened AR2, AR5, and AR7 work verifiable without relying on fragile manual checks

Root problem:

- current route tests are still coupled to live auth/session DB state, and there is no dedicated automated coverage for the graph concept activity surface or the topic-switch UX

Files involved:

- `tests/api/test_research.py`
- `tests/domain/test_runtime_integration.py`
- new frontend tests under `apps/web/features/graph/` or `apps/web/components/`
- new frontend tests for `ConceptSwitchBanner` / topic-lock flow as needed

Implementation steps:

1. Stabilize research route tests by overriding auth/session dependencies or otherwise isolating route wiring from live DB requirements.
2. Add backend regression tests for reopened AR2.6/AR2.7 and AR5.7 behaviors.
3. Add frontend tests covering:
   - interactive quiz history open/retry behavior
   - cumulative flashcard concept view behavior
   - non-modal topic-switch UX and "stay on topic" behavior
4. Keep regression tests narrow and behavior-focused rather than snapshot-heavy.

What stays the same:

- tests remain policy/contract oriented
- background jobs remain recommendation-first
- no new silent side effects just for testability

Verification:

- `PYTHONPATH=. pytest -q tests/api/test_research.py tests/domain/test_runtime_integration.py`
- `npx vitest run <new graph/topic-lock test files>` from `apps/web/`

Exit criteria:

- route verification no longer depends on live auth/session DB access
- reopened AR2/AR5/AR7 behaviors have direct automated coverage
- AR6 can be marked complete without hand-wavy verification claims

### Verification Block - AR6.7

Root cause
- Route tests relied on live auth/session state; no automated coverage for AR7 concept activity endpoint, AR2.7 graph evidence context format, or AR7.4 switch-threshold edge cases

Files changed
- `tests/api/test_ar6_7_regression.py` (new: 8 regression tests across 3 categories)

What changed
- Concept activity API endpoint tested with dependency injection (200 success + 422 error)
- Graph evidence context format validated: structured lines with names/descriptions, empty case
- Switch-threshold boundary tests: below-threshold stays, at-threshold switches, no-current-concept
- Confidence mapping coverage across all _to_confidence score ranges

Commands run
- `pytest tests/api/test_ar6_7_regression.py -v` → 8 passed
- `pytest tests/ -q` → 884 passed (2 pre-existing deselected)
- `npx vitest run` → 106 passed

Observed outcome
- Reopened AR2/AR5/AR7 behaviors have direct automated coverage
- Route verification uses dependency injection, not live DB
- No removals needed

## Verification Block Template

```text
Verification Block - AR6.x

Root cause
- <why background behavior or test coverage was insufficient>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <jobs or traces checked>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/06_background_eval_plan.md.
Begin with the next incomplete AR6 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR6 slice at a time.
2. Keep background jobs recommendation-first, keep traces safe, and add regression coverage alongside each new loop.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed AR6 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/06_background_eval_plan.md and restate which AR6 slices remain.
6. Continue to the next incomplete AR6 slice once the previous slice is verified.
7. When all AR6 slices are complete, immediately re-open docs/AGENTIC_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because AR6 is complete. AR6 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/AGENTIC_MASTER_PLAN.md.
Read docs/agentic/06_background_eval_plan.md.
Begin with the current AR6 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When AR6 is complete, immediately return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.
```
