# Learner Model Plan (AR4) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for learner-profile assembly and adaptive tutor state.
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
   - after every 2 AR4 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR4 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Keep learner state typed and inspectable.
4. Do not let prompts become the primary source of truth for mastery or readiness.
5. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan restores the original "current knowledge/config of user" idea in a typed, inspectable form.

Earlier work already landed learner-state fragments across:

- mastery data in `adapters/db/mastery.py`
- readiness analysis in `domain/readiness/analyzer.py`
- chat/session memory in `domain/chat/session_memory.py`
- tutor profile routes in `apps/api/routes/auth.py`

This plan exists because the app has the data fragments, but not the canonical learner snapshot that should guide tutor planning, research planning, and review policy.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/DRIFT_REPORT.md`
- `docs/PRODUCT_SPEC.md`
- `adapters/db/mastery.py`
- `domain/readiness/analyzer.py`
- `domain/chat/session_memory.py`
- `apps/api/routes/auth.py`
- `domain/chat/tutor_agent.py`
- `domain/chat/respond.py`

## Executive Summary

What is already in good shape:

- mastery state exists
- readiness scoring exists
- chat/session history exists
- the tutor already consumes some stateful context

What is still materially missing:

1. there is no canonical learner snapshot type
2. adaptive tutoring sees fragments rather than a coherent profile
3. the original user-model vision is only partially represented

The remaining work should stay narrow: define a read-model first, assemble it from existing sources, then feed it into tutor planning and traces without replacing current policy ownership.

## Non-Negotiable Constraints

1. Keep learner state typed and inspectable.
2. Do not let prompts become the primary source of truth for mastery or readiness.
3. Prefer derived snapshots over user-editable freeform blobs.
4. Preserve current mastery and readiness calculations unless a slice explicitly changes them.
5. Keep privacy boundaries explicit if more learner metadata is surfaced.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-L1` Mastery data and status already exist.
- `BASE-L2` Readiness scoring and quiz recommendation logic already exist.
- `BASE-L3` Session memory and assessment context already exist.
- `BASE-L4` Tutor profile route already exists.

## Remaining Slice IDs

- `AR4.1` Define learner snapshot types
- `AR4.2` Add learner snapshot assembly service
- `AR4.3` Feed learner snapshots into tutor planning and prompt assembly
- `AR4.4` Expose safe learner-state traces and UI surfaces

## Decision Log For Remaining Work

1. Build snapshots from existing DB truth instead of maintaining a separate mutable profile blob first.
2. The first version should support tutor adaptation, research planning, and review suggestions.
3. Learner modeling should influence prompts and runtime policy, but not replace policy.

## Removal Safety Rules

1. Do not delete existing mastery or readiness paths when adding the snapshot layer.
2. Keep snapshot assembly as a read-model first.
3. Do not remove current auth/profile fields without a migration note.
4. Maintain a removal ledger here if any legacy profile helper is retired.

## Removal Entry Template

```text
Removal Entry - AR4.x

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

- learner-related data exists in pieces
- no unified learner snapshot type is confirmed in current runtime
- `pytest -q`: not re-run during this planning pass

Current hotspots:

| File | Why it still matters |
|---|---|
| `adapters/db/mastery.py` | Current mastery truth source. |
| `domain/readiness/analyzer.py` | Current readiness and quiz recommendation source. |
| `domain/chat/session_memory.py` | Current session-memory source. |
| `domain/chat/respond.py` | Current tutor path that will need learner snapshot input. |
| `apps/api/routes/auth.py` | Existing tutor-profile exposure that may need to align with the new snapshot model. |

## Remaining Work Overview

### 1. Adaptive tutoring is underpowered by fragmented state

The tutor can see mastery and some history, but not a broader topic-state picture.

### 2. The original user-model vision is only partially present

Interests, weak areas, recent misconceptions, and study frontier are not assembled into one object.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR4.1. Slice 1: Define learner snapshot types

Purpose:

- create canonical shapes for learner and topic state

Root problem:

- there is no stable typed surface for the tutor or research planner to consume

Files involved:

- `domain/learner/profile.py` (new)
- adjacent schema modules if needed

Implementation steps:

1. Define `LearnerProfileSnapshot`.
2. Define `TopicStateSnapshot`.
3. Keep fields narrow and grounded in existing data sources.

Suggested fields:

- goals
- interests
- weak_topics
- strong_topics
- recent_misconceptions
- current_frontier
- review_queue
- recent_documents

What stays the same:

- mastery and readiness remain source-of-truth systems
- no freeform profile blob is introduced yet

Verification:

- unit tests for shape and serialization

Exit criteria:

- learner state has a canonical typed form

### AR4.2. Slice 2: Add learner snapshot assembly service

Purpose:

- assemble learner state from existing systems

Root problem:

- current data is fragmented and expensive to reason about at each call site

Files involved:

- `domain/learner/profile.py`
- `adapters/db/mastery.py`
- `domain/readiness/analyzer.py`
- `domain/chat/session_memory.py`

Implementation steps:

1. Build a service that aggregates mastery, readiness, session memory, and recent activity.
2. Keep data derivation deterministic and safe on missing fields.
3. Add logging or trace hooks so snapshot construction is inspectable.

What stays the same:

- current DB truth sources
- existing readiness/mastery algorithms

Verification:

- unit tests with representative fixtures

Exit criteria:

- runtime can request a learner snapshot for a turn

### AR4.3. Slice 3: Feed learner snapshots into tutor planning and prompt assembly

Purpose:

- make tutoring and retrieval planning adapt to the learner's actual state

Root problem:

- even with a snapshot type, adaptation will remain fragmented unless the tutor actually uses it

Files involved:

- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/chat/prompt_kit.py`
- `domain/chat/tutor_agent.py`

Implementation steps:

1. Pass learner snapshots into `TurnPlan` construction.
2. Feed the relevant summary into prompt sections.
3. Keep mastery/topic lock decisions runtime-owned.

What stays the same:

- topic lock and mastery policy ownership
- public tutor response contract

Verification:

- targeted tutor tests
- manual flows covering weak-topic review and level-up readiness

Exit criteria:

- tutor adaptation is driven by a structured learner snapshot

### AR4.4. Slice 4: Expose safe learner-state traces and UI surfaces

Purpose:

- make adaptive behavior debuggable without surfacing private internals indiscriminately

Root problem:

- adaptive behavior will be hard to debug and productize without a visible surface

Files involved:

- backend trace surfaces
- relevant frontend learner/tutor views

Implementation steps:

1. Add safe summary fields to traces or debug panels.
2. Consider UI surfaces for current frontier, weak topics, and review nudges.
3. Keep sensitive or noisy raw state out of end-user explanations.

What stays the same:

- no raw sensitive learner profile dump in the main tutor answer
- traces remain operational rather than introspective

Verification:

- UI inspection
- trace checks

Exit criteria:

- learner adaptation is inspectable and productized

## Verification Block Template

```text
Verification Block - AR4.x

Root cause
- <why learner state was too fragmented>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <adaptive behavior checked>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/04_learner_model_plan.md.
Begin with the next incomplete AR4 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR4 slice at a time.
2. Keep learner state typed, derived from existing DB truth, and runtime-safe.
3. Preserve current mastery/readiness policy ownership.
4. Run the listed verification steps before claiming a slice complete.
5. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
6. After every 2 completed AR4 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/04_learner_model_plan.md and restate which AR4 slices remain.
7. Continue to the next incomplete AR4 slice once the previous slice is verified.
8. When all AR4 slices are complete, return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.
```
