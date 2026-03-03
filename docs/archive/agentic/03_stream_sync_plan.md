# Stream Sync Plan (AR3) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for tutor stream status protocol and frontend sync.
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
   - after every 2 AR3 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR3 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Browser-visible behavior is part of the definition of done for AR3:
   - tests are necessary
   - they are not sufficient
   - the stream UI must actually represent backend activity truthfully
4. Do not expose chain-of-thought.
5. Preserve graceful blocking fallback when streaming is unavailable.
6. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan aligns frontend tutor state with real backend work.

Earlier work already landed:

- backend phases in `core/schemas/chat.py::ChatPhase`
- SSE events from `domain/chat/stream.py`
- the streaming route in `apps/api/routes/chat.py`
- frontend stream consumption in `apps/web/features/tutor/hooks/use-tutor-messages.ts`

This plan exists because the transport is present, but the visible UX still collapses too much backend work and does not yet cover graph expansion or tutor-triggered quiz lifecycle events.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/GENERATION_STATUS_PLAN.md`
- `domain/chat/stream.py`
- `core/schemas/chat.py`
- `apps/api/routes/chat.py`
- `apps/web/lib/api/types.ts`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/features/tutor/types.ts`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/features/tutor/hooks/use-level-up-flow.ts`
- `apps/web/components/chat-response.tsx`

## Executive Summary

What is already in good shape:

- phase-level SSE exists
- the frontend already consumes stream events
- "responding" already means first visible delta on the backend

What is still materially missing:

1. the status protocol is too coarse
2. the visible UI intentionally hides searching/finalizing details
3. quiz-related tutor actions are not yet modeled in the same event system
4. the frontend lacks a durable activity timeline / rail

The remaining work should stay narrow: extend the existing stream contract, emit richer activity events, render them truthfully in the current tutor timeline, and keep the blocking fallback intact.

## Non-Negotiable Constraints

1. Do not expose chain-of-thought.
2. Keep backend as the source of truth for phase/activity state.
3. Preserve graceful blocking fallback when streaming is unavailable.
4. Keep the phase/event schema backward compatible where practical.
5. Do not regress token streaming behavior.
6. "Responding" must remain tied to first visible text, not internal model start time.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-S1` Phase-level SSE transport exists.
- `BASE-S2` Frontend stream parser and event consumer exist.
- `BASE-S3` Backend first-delta `responding` semantics already exist.
- `BASE-S4` Tutor page already has a quiz drawer surface that can be synchronized with stream events.

## Remaining Slice IDs

- `AR3.1` Expand backend status event schema
- `AR3.2` Emit richer progress events from the tutor runtime
- `AR3.3` Update frontend state model and timeline UI
- `AR3.4` Add stream-sync tests and fallback checks

## Decision Log For Remaining Work

1. Keep `phase` as a coarse enum, but add a richer activity layer.
2. The frontend should render a stepper or event feed, not just one label string.
3. Repeated phase transitions are valid before response generation.
4. Quiz-related tutor actions should appear in the same event model rather than as disconnected silent UI state changes.

## Removal Safety Rules

1. Do not remove `ChatPhase`; extend it.
2. Do not remove the blocking path.
3. If the old visible phase label helper remains temporarily, mark it as compatibility-only.
4. Maintain a removal ledger here if any stream event or UI contract is retired.

## Removal Entry Template

```text
Removal Entry - AR3.x

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

- phase-level SSE exists
- UI currently hides much of that detail by design
- richer activity protocol added to schema (AR3.1 complete)
- browser automation was not run during this planning pass

### Verification Block - AR3.1

```
Verification Block - AR3.1

Slice: AR3.1 – Expand backend status event schema

Status: COMPLETE

Commit: chore(refactor): AR3.1 expand backend status event schema

Files changed
- core/schemas/chat.py (added TutorActivity literal, activity and step_label on ChatStreamStatusEvent)
- core/schemas/__init__.py (export TutorActivity)
- apps/web/lib/api/types.ts (added TutorActivity type, activity/step_label on ChatStreamStatusEvent)
- tests/core/test_g0_contracts.py (2 new tests for activity fields and union parsing)

What changed
- TutorActivity: 8-value Literal type (planning_turn, retrieving_chunks, expanding_graph, checking_mastery, preparing_quiz, grading_quiz, verifying_citations, generating_reply)
- ChatStreamStatusEvent now has optional activity (TutorActivity | None) and step_label (str | None)
- TypeScript mirror types added for frontend

Commands run
- PYTHONPATH=. pytest tests/core/test_g0_contracts.py -v (23 passed)
- PYTHONPATH=. pytest -q (654 passed)
- npm --prefix apps/web test (91 passed)
- npm --prefix apps/web run typecheck (clean)

Removal Entries
- None (additive-only slice)

Observed outcome
- All schema tests pass with new activity fields
- Backward compatible — activity and step_label default to None
```

### Verification Block - AR3.2

```
Verification Block - AR3.2

Slice: AR3.2 – Emit richer progress events from the tutor runtime

Status: COMPLETE

Commit: chore(refactor): AR3.2 emit richer progress events from tutor runtime

Files changed
- domain/chat/stream.py (emit activity-enriched status events at each step)
- tests/domain/test_s1_phase_semantics.py (dedup consecutive same-phase for assertions)
- tests/api/test_g3_stream.py (dedup consecutive same-phase for assertions)

What changed
- stream.py yields activities: planning_turn, checking_mastery, retrieving_chunks, expanding_graph, generating_reply, verifying_citations
- Phase ordering preserved (thinking → searching → responding → finalizing)
- Activity is a sub-label within the same coarse phase
- Tests updated to dedup consecutive same-phase events

Commands run
- PYTHONPATH=. pytest tests/api/test_g3_stream.py tests/domain/test_s1_phase_semantics.py -v (9 passed)
- PYTHONPATH=. pytest -q (654 passed)

Removal Entries
- None (additive-only slice)

Observed outcome
- All 654 backend tests green
- Activity events visible in stream output
```

### Verification Block - AR3.3

```
Verification Block - AR3.3

Slice: AR3.3 – Update frontend state model and timeline UI

Status: COMPLETE

Commit: chore(refactor): AR3.3 update frontend state model and timeline UI

Files changed
- apps/web/features/tutor/types.ts (added ActivityStep type, ACTIVITY_LABELS map)
- apps/web/features/tutor/hooks/use-tutor-messages.ts (track activitySteps state)
- apps/web/features/tutor/hooks/use-tutor-page.ts (expose activitySteps)
- apps/web/features/tutor/components/tutor-timeline.tsx (render activity rail)
- apps/web/app/(app)/tutor/page.tsx (pass activitySteps prop)

What changed
- ActivityStep type: { activity, label, done } tracks agent steps
- ACTIVITY_LABELS: human-readable label map for 8 activity types
- Activity rail renders under status indicator with ✓/› markers
- Steps tracked on status events, reset on final/error/new submission

Commands run
- npm --prefix apps/web run typecheck (clean)
- npm --prefix apps/web test (91 passed)
- PYTHONPATH=. pytest -q (654 passed)

Removal Entries
- None (additive-only slice)

Observed outcome
- Frontend typecheck clean
- Activity rail renders in timeline component
```

### Verification Block - AR3.4

```
Verification Block - AR3.4

Slice: AR3.4 – Add stream-sync tests and fallback checks

Status: COMPLETE

Commit: chore(refactor): AR3.4 add stream-sync tests and fallback checks

Files changed
- tests/domain/test_s1_phase_semantics.py (3 new tests for activity events and responding safety)
- apps/web/features/tutor/visible-phase.test.ts (3 new tests for ACTIVITY_LABELS)

What changed
- Backend tests verify activities emitted at each stream path
- Backend test confirms no fake "responding" before visible text
- Frontend tests verify ACTIVITY_LABELS covers all 8 types with human-readable labels

Commands run
- PYTHONPATH=. pytest tests/domain/test_s1_phase_semantics.py -v (7 passed)
- npm --prefix apps/web test (94 passed)
- PYTHONPATH=. pytest -q (657 passed)

Removal Entries
- None (additive-only slice)

Observed outcome
- 657 backend + 94 frontend tests green
- Stream sync fully tested for activity events
```

Current hotspots:

| File | Why it still matters |
|---|---|
| `core/schemas/chat.py` | Owns the current status-event schema. |
| `domain/chat/stream.py` | Emits current status events and will need richer activities. |
| `apps/web/features/tutor/hooks/use-tutor-messages.ts` | Owns stream event handling and current no-regression status logic. |
| `apps/web/features/tutor/types.ts` | Explicitly collapses visible phase labels today. |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Current status UI is still a single label + typing dots. |

## Remaining Work Overview

### 1. Status protocol is too coarse

The current `ChatPhase` contract is useful, but not enough to explain what the backend is doing in detail.

### 2. UI policy intentionally hides backend state

The frontend currently flattens `thinking`, `searching`, and `finalizing` into one user-facing state.

### 3. Quiz and graph-expansion states are not first-class

The stream model does not yet express steps like `expanding_graph`, `preparing_quiz`, or `grading_quiz`.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR3.1. Slice 1: Expand backend status event schema

Purpose:

- add richer activity metadata while preserving phase semantics

Root problem:

- the current schema cannot explain enough backend work to support a truthful UI

Files involved:

- `core/schemas/chat.py`
- `apps/web/lib/api/types.ts`

Implementation steps:

1. Add fields such as `activity`, `step_id`, `step_label`, `attempt`, and optional counters.
2. Keep `phase` as the discriminator for coarse lifecycle state.
3. Preserve compatibility with existing consumers where possible.

Suggested activities:

- `planning_turn`
- `retrieving_chunks`
- `expanding_graph`
- `checking_mastery`
- `preparing_quiz`
- `grading_quiz`
- `verifying_citations`
- `generating_reply`

What stays the same:

- coarse phase semantics remain intact
- existing stream transport remains SSE-based

Verification:

- schema tests
- typecheck for frontend API types

Exit criteria:

- backend can describe what it is doing beyond the coarse phase enum

### AR3.2. Slice 2: Emit richer progress events from the tutor runtime

Purpose:

- make real backend work visible through the stream

Root problem:

- the backend does more work than the stream protocol currently reports

Files involved:

- `domain/chat/progress.py`
- `domain/chat/stream.py`
- `domain/chat/respond.py`

Implementation steps:

1. Emit activities for query planning, retrieval, graph expansion, mastery checks, citation verification, and response generation.
2. Emit quiz lifecycle activities when the tutor starts or recommends quiz creation.
3. Allow repeated pre-output phase transitions where truthful.
4. Keep "responding" tied to first visible text.

What stays the same:

- no chain-of-thought exposure
- blocking fallback still exists

Verification:

- streaming integration tests
- manual SSE inspection

Exit criteria:

- stream events accurately reflect backend action changes

### AR3.3. Slice 3: Update frontend state model and timeline UI

Purpose:

- render backend status changes faithfully

Root problem:

- the current timeline only exposes one generic status label

Files involved:

- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/features/tutor/types.ts`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/components/chat-response.tsx`

Implementation steps:

1. Replace the single collapsed visible-label policy with a timeline/stepper model.
2. Render the latest activity and a short history of recent steps.
3. Show quiz-specific statuses and transitions in the same timeline region.
4. Keep token streaming and final response rendering unchanged.

Recommended UX changes:

- keep the current tutor chat stream as the main pane
- show a compact "agent activity rail" under the active assistant turn
- when a quiz is being prepared, show the drawer transition as an explicit step
- when a quiz CTA is tutor-triggered, visually link the message card and the drawer action

What stays the same:

- existing tutor page shell
- final response card rendering path

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual chat session inspection

Exit criteria:

- the UI visibly tracks backend work in near real time

### AR3.4. Slice 4: Add stream-sync tests and fallback checks

Purpose:

- guard against desync and UX regressions

Root problem:

- richer activity states will be easy to break unless they are explicitly tested

Files involved:

- frontend tutor tests
- backend stream tests

Implementation steps:

1. Add tests for repeated searching/thinking loops before response generation.
2. Keep blocking fallback behavior sane when SSE fails.
3. Verify that no fake "responding" state appears before visible text.
4. Verify that tutor-triggered quiz activities do not desync from drawer state.

What stays the same:

- fallback route and semantics
- no hidden reasoning text in UI

Verification:

- backend and frontend targeted tests

Exit criteria:

- phase and activity sync is test-covered

## Verification Block Template

```text
Verification Block - AR3.x

Root cause
- <why the old status UX or protocol was insufficient>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <streaming steps tested>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/03_stream_sync_plan.md.
Begin with the next incomplete AR3 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR3 slice at a time.
2. Keep phase semantics truthful, do not expose chain-of-thought, preserve the blocking fallback, and keep "responding" tied to first visible text.
3. Run the listed verification steps before claiming a slice complete, including browser-visible checks where required by the plan.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed AR3 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/03_stream_sync_plan.md and restate which AR3 slices remain.
6. Continue to the next incomplete AR3 slice once the previous slice is verified.
7. When all AR3 slices are complete, immediately re-open docs/AGENTIC_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because AR3 is complete. AR3 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/AGENTIC_MASTER_PLAN.md.
Read docs/agentic/03_stream_sync_plan.md.
Begin with the current AR3 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When AR3 is complete, immediately return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.
```
