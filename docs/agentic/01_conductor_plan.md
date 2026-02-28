# Conductor Plan (AR0 / AR1) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for tutor orchestration and turn planning.
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
   - after every 2 AR0/AR1 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR0/AR1 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one AR0/AR1 sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` here and update the master status ledger.
5. Do not widen this plan into evidence planning, research, or generic frontend work except where this plan explicitly calls for an interface seam.
6. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan turns the current tutor path into a guarded conductor that plans the turn before it retrieves and answers.

Earlier work already landed:

- grounded tutor orchestration in `domain/chat/respond.py`
- streaming tutor orchestration in `domain/chat/stream.py`
- tutor style gating in `domain/chat/tutor_agent.py`
- a query analysis scaffold in `domain/chat/query_analyzer.py`

This plan exists because the planning seam is present but not yet driving runtime execution.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/DRIFT_REPORT.md`
- `docs/PROMPT_REFACTOR_PLAN.md`
- `docs/LLM_CALL_FLOWS.md`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/chat/query_analyzer.py`
- `domain/chat/response_service.py`
- `domain/chat/tutor_agent.py`
- `domain/chat/progress.py`
- `core/schemas/assistant.py`
- `core/verifier.py`
- `apps/web/features/tutor/hooks/use-level-up-flow.ts`
- `apps/web/features/tutor/hooks/use-tutor-page.ts`

## Executive Summary

What is already in good shape:

- the tutor already has grounded blocking and streaming flows
- concept resolution, tutor style gating, and verification are already runtime-owned
- the UI already has a level-up drawer and a programmatic `startLevelUp()` flow

What is still materially missing:

1. query analysis does not yet drive the tutor runtime
2. there is no canonical `TurnPlan`
3. planner decisions are difficult to inspect
4. quiz and review actions are not yet first-class outcomes of tutor planning

The remaining work should stay narrow: wire intent analysis, add a small `TurnPlan`, route the tutor from that plan, and make planner-owned quiz actions deliberate without replacing current guardrails.

## Non-Negotiable Constraints

1. Keep `AssistantResponseEnvelope` as the public tutor response contract.
2. Keep `verify_assistant_draft()` as the final output gate.
3. Do not move concept-switch policy entirely into prompts.
4. Do not bypass `resolve_tutor_style()` or current mastery checks.
5. Maintain parity between blocking and streaming chat paths.
6. Quiz launch decisions may be planner-driven, but actual quiz creation/opening must remain runtime-owned and user-visible.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-C1` Grounded tutor answer path exists in `domain/chat/respond.py`.
- `BASE-C2` Streaming tutor answer path exists in `domain/chat/stream.py`.
- `BASE-C3` Query analyzer prompt asset and parser exist in `domain/chat/query_analyzer.py`.
- `BASE-C4` Quiz drawer and `startLevelUp()` path already exist on the frontend.

These are not execution targets unless an AR0/AR1 slice is blocked by them.

## Remaining Slice IDs

- `AR0.1` Docs truth reset for tutor framing
- `AR1.1` Wire query analysis into runtime
- `AR1.2` Introduce typed `TurnPlan`
- `AR1.3` Route tutor execution from `TurnPlan`
- `AR1.4` Add turn-plan trace metadata
- `AR1.5` Add tutor-driven quiz action flow

## Decision Log For Remaining Work

1. Reuse `QueryAnalysis` instead of inventing a second router first.
2. `TurnPlan` should be proposal-only and runtime-owned.
3. The plan object should stay small: intent, retrieval need, concept focus, teaching mode, research need, quiz/review hints, and stream activities.
4. Social fast-paths can still short-circuit, but should still produce plan-aware traces where safe.
5. The tutor should be able to recommend or trigger a quiz drawer/open flow when the user asks to be tested or when readiness/topic state strongly suggests review.

## Removal Safety Rules

1. Do not delete the current linear tutor path until `TurnPlan` reaches parity.
2. Prefer a small compatibility shim while both paths coexist.
3. If `generate_tutor_text()` is split further, document which callers moved.
4. Reuse the current quiz drawer and `startLevelUp()` path before introducing new quiz UI contracts.
5. Maintain a removal ledger here if any tutor orchestration shim is removed.

## Removal Entry Template

```text
Removal Entry - AR1.x

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

- `pytest -q`: not re-run during this planning pass
- `tests/domain/test_query_analyzer.py`: exists, but not re-run during this planning pass
- Runtime wiring of `QueryAnalysis`: not confirmed in the live tutor path

Current hotspots:

| File | Why it still matters |
|---|---|
| `domain/chat/respond.py` | Main blocking tutor orchestration remains mostly linear. |
| `domain/chat/stream.py` | Streaming tutor flow needs the same planning semantics as blocking. |
| `domain/chat/query_analyzer.py` | Planning seam exists but is not yet wired. |
| `domain/chat/response_service.py` | Still owns tutor-generation steps that may need to move behind planning seams. |
| `apps/web/features/tutor/hooks/use-level-up-flow.ts` | Existing quiz-launch seam should be reused by tutor-planned quiz actions. |

## Remaining Work Overview

### 1. Runtime planning is missing

`QueryAnalysis` is scaffolded and tested, but `generate_chat_response()` and `generate_chat_response_stream()` still run a mostly linear flow.

### 2. Tutor orchestration is hard to inspect

Today it is difficult to tell which planning decisions were made before retrieval, prompt assembly, and answer generation.

### 3. Quiz flow is disconnected from tutor planning

The app already supports quiz creation, but the tutor does not yet intentionally launch or recommend quiz flows as part of a coherent turn plan.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR0.1. Slice 1: Docs truth reset for tutor framing

Purpose:

- correct docs so they reflect current prompt/runtime reality and the actual conductor target

Root problem:

- some docs still understate landed prompt runtime or overstate explicit agent boundaries

Files involved:

- `docs/DRIFT_REPORT.md`
- `docs/ARCHITECTURE.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/agentic/01_conductor_plan.md`

Implementation steps:

1. Mark prompt asset infra as already landed.
2. Note that `query_analyzer.py` exists but is not wired into the tutor runtime.
3. Clarify that the next architecture step is guarded conductor logic, not a free-form agent.

What stays the same:

- no runtime behavior changes
- no public API changes

Verification:

- doc review against current runtime files

Exit criteria:

- docs no longer contradict the current runtime state
- docs clearly frame the conductor target

### AR1.1. Slice 2: Wire query analysis into runtime

Purpose:

- run lightweight query analysis before retrieval

Root problem:

- the planner seam exists, but the tutor does not yet use it live

Files involved:

- `domain/chat/query_analyzer.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `adapters/llm/providers.py`
- `core/contracts.py`

Implementation steps:

1. Add a typed LLM entrypoint for query analysis instead of routing it through tutor-only logic implicitly.
2. Call query analysis before retrieval in both blocking and streaming flows.
3. Use conservative fallback behavior on parse or model failure.

What stays the same:

- final answer verification
- current concept resolution still owns the actual concept switch decision

Verification:

- `pytest -q`
- targeted tests for query analysis success and fallback
- manual chat turns for social, learn, and practice intents

Exit criteria:

- runtime can classify turn intent before retrieval
- blocking and streaming paths use the same analysis seam

### AR1.2. Slice 3: Introduce typed `TurnPlan`

Purpose:

- make the tutor path explicitly plan-driven

Root problem:

- tutor orchestration currently depends on scattered local variables rather than a stable plan object

Files involved:

- `domain/chat/turn_plan.py` (new)
- `domain/chat/respond.py`
- `domain/chat/stream.py`

Implementation steps:

1. Define a small dataclass or Pydantic model for `TurnPlan`.
2. Populate it from query analysis, concept context, mastery, and request params.
3. Keep plan fields narrow and inspectable.

Suggested fields:

- `intent`
- `requested_mode`
- `needs_retrieval`
- `resolved_concept_hint`
- `teaching_strategy`
- `research_need`
- `should_offer_quiz`
- `should_start_quiz`
- `quiz_kind`
- `quiz_concept_id`
- `status_steps`

What stays the same:

- existing tutor response contract
- runtime-owned mastery and concept policy

Verification:

- unit tests for plan construction
- manual trace inspection

Exit criteria:

- tutor orchestration uses a canonical plan object
- plan fields are small and inspectable

### AR1.3. Slice 4: Route tutor execution from `TurnPlan`

Purpose:

- use the plan to decide whether to retrieve, clarify, answer directly, or suggest next actions

Root problem:

- even with a plan object, behavior will remain linear unless execution is actually routed through it

Files involved:

- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/chat/response_service.py`

Implementation steps:

1. Gate retrieval on `TurnPlan.needs_retrieval`.
2. Derive tutor style and clarification behavior from the plan.
3. Route quiz and review recommendations into structured actions.
4. Keep blocking and streaming logic aligned.

What stays the same:

- grounded verification and persistence order
- existing public routes

Verification:

- `pytest -q`
- streaming/manual parity checks for representative turns

Exit criteria:

- the plan materially controls runtime execution
- no parity regressions between blocking and streaming paths

### AR1.4. Slice 5: Add turn-plan trace metadata

Purpose:

- make planner decisions observable without exposing chain-of-thought

Root problem:

- planner behavior will be hard to debug without a safe trace surface

Files involved:

- `core/schemas/assistant.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `apps/web/components/chat-response.tsx`

Implementation steps:

1. Add safe planner metadata to `generation_trace` or a sibling trace field.
2. Emit planner summary fields, not raw reasoning.
3. Render developer-safe trace details in the UI only where already permitted.

What stays the same:

- no chain-of-thought exposure
- no prompt-body persistence requirements

Verification:

- unit tests for trace shape
- manual UI inspection in dev mode

Exit criteria:

- turn planning is inspectable and debuggable

### AR1.5. Slice 6: Add tutor-driven quiz action flow

Purpose:

- let the tutor deliberately launch or strongly recommend a quiz as part of the learning flow

Root problem:

- quiz creation already exists, but it is not yet a coherent planner-owned tutor action

Files involved:

- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `core/schemas/assistant.py`
- `domain/readiness/analyzer.py`
- `apps/web/features/tutor/hooks/use-level-up-flow.ts`
- `apps/web/features/tutor/hooks/use-tutor-page.ts`
- `apps/web/components/chat-response.tsx`
- `apps/web/features/tutor/components/tutor-timeline.tsx`

Implementation steps:

1. Expand `ActionCTA` or adjacent action metadata so a quiz action can distinguish "offer quiz" from "start quiz now".
2. Add planner/runtime rules for when the tutor may suggest a quiz, auto-open the quiz drawer, or immediately start quiz creation after explicit user intent.
3. Keep user-visible confirmation in the UI before or as quiz creation begins.
4. Reuse the existing level-up flow and quiz drawer rather than building a second quiz surface.

What stays the same:

- the existing quiz API routes
- the existing drawer-based quiz UI surface

Verification:

- targeted tests for action payload shape
- manual flows for explicit "quiz me" and tutor-recommended review

Exit criteria:

- quiz launch is a deliberate part of the tutor orchestration
- explicit user quiz requests can open/start the existing flow safely

## Verification Block Template

```text
Verification Block - AR1.x

Root cause
- <why the old tutor flow was too linear or opaque>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <turns tested>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/01_conductor_plan.md.
Begin with the next incomplete AR0/AR1 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR0/AR1 slice at a time.
2. Preserve AssistantResponseEnvelope, verify_assistant_draft(), blocking/streaming parity, and runtime-owned topic/mastery policies.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed AR0/AR1 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/01_conductor_plan.md and restate which AR0/AR1 slices remain.
6. Continue to the next incomplete AR0/AR1 slice once the previous slice is verified.
7. When all AR0/AR1 slices are complete, return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.
```
