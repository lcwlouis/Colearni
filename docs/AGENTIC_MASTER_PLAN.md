# CoLearni Agentic Master Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new nested plan set; no active plan is being replaced)

Template usage:
- This is a task-specific master plan for the agentic tutor / agentic RAG / second-brain refactor.
- It does not replace `docs/REFACTOR_PLAN.md`.
- The child plans under `docs/agentic/` are subordinate execution plans; this file is the cross-track source of truth.

## Plan Completeness Checklist

This master plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered track list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of every run
   - after every 2 sub-slices across child plans
   - after any context compaction / summarization event
   - before claiming any child-plan slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the active child plan are met
3. Work in SMALL PR-sized chunks:
   - one sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` in the active child plan and update this master status ledger.
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions recorded here
6. If implementation uncovers a behavior-change risk, STOP and update the active child plan and this file before widening scope.
7. This is an architecture / orchestration refactor. Do not mix in unrelated product work.
8. Completing one child plan is NOT run completion. The run is only complete when every track in the master status ledger is marked `complete` or explicitly `blocked`.
9. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This document is the master execution plan for steering CoLearni from a grounded tutor over uploaded materials into a guarded learning copilot with:

1. agentic evidence planning over the current hybrid retrieval stack
2. richer tutor orchestration and learner modeling
3. deliberate tutor-triggered quiz and review flows
4. synchronized backend/frontend status reporting
5. approval-gated research and second-brain workflows

Earlier refactor work already landed important substrate:

- file-based prompt assets under `core/prompting/`
- grounded answer verification in `core/verifier.py`
- SSE streaming in `apps/api/routes/chat.py` and `domain/chat/stream.py`
- hybrid retrieval in `domain/chat/retrieval_context.py`
- quiz, practice, and readiness mechanics

This new plan exists because the remaining gap is no longer prompt storage. The gap is orchestration: planning, multi-step evidence assembly, learner-state adaptation, research workflows, and frontend status sync.

## Inputs Used

This plan is based on:

- `docs/prompt_templates/refactor_plan.md`
- `docs/PROMPT_REFACTOR_PLAN.md`
- `docs/GENERATION_STATUS_PLAN.md`
- `docs/DRIFT_REPORT.md`
- `docs/LLM_CALL_FLOWS.md`
- `docs/ARCHITECTURE.md`
- current repository layout and runtime files as of 2026-03-01:
  - `domain/chat/respond.py`
  - `domain/chat/stream.py`
  - `domain/chat/query_analyzer.py`
  - `domain/chat/retrieval_context.py`
  - `domain/chat/evidence_builder.py`
  - `domain/chat/session_memory.py`
  - `domain/research/service.py`
  - `domain/research/runner.py`
  - `apps/api/routes/chat.py`
  - `apps/api/routes/research.py`
  - `apps/web/features/tutor/hooks/use-tutor-messages.ts`
  - `apps/web/features/tutor/hooks/use-level-up-flow.ts`
  - `apps/web/features/tutor/types.ts`
  - `core/schemas/chat.py`
  - `core/schemas/assistant.py`
  - `core/verifier.py`

## Executive Summary

What is already in good shape:

- prompt assets are already live and versioned
- blocking and streaming chat already exist
- answer verification and citation enforcement already exist
- retrieval is already hybrid rather than vector-only
- quiz, readiness, and practice mechanics already exist

What is still materially missing:

1. the tutor loop is still mostly linear instead of plan-driven
2. retrieval is hybrid but not yet agentic, multi-step, or graph-first enough
3. quiz and review flows exist, but are not yet planner-driven inside the tutor loop
4. learner state is fragmented instead of assembled into a typed profile
5. research remains manual-source oriented rather than topic-planned
6. frontend phase UX intentionally collapses real backend work into generic "Thinking..."

The remaining work should stay narrow:

- build on current substrate instead of replacing it
- keep runtime guardrails in code
- stage the work through small child-plan slices

## Non-Negotiable Constraints

These constraints apply to every remaining track:

1. Preserve `verify_assistant_draft()` as the final answer gate.
2. Keep topic lock, concept switching, and mastery gating runtime-owned.
3. Do not auto-ingest externally discovered research; every such result must remain pending until explicit user approval before ingestion.
4. Do not let subagents emit final user-facing responses directly.
5. Treat the canonical graph and provenance links as first-class evidence surfaces, not just ranking hints.
6. Keep routes thin and keep existing public endpoints stable where practical.
7. Prefer additive / compatibility-first changes before deletion.
8. Treat "deep search over everything learned" as a guarded synthesis workflow over trusted workspace docs, approved and ingested research, graph state, mastery/readiness signals, quiz/practice history, and learner snapshots; it is not autonomous crawling.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `BASE1` File-based prompt runtime exists in `core/prompting/`.
- `BASE2` Tutor, quiz, practice, grading, and post-ingest prompt assets are already wired.
- `BASE3` Streaming transport exists from `apps/api/routes/chat.py` to `domain/chat/stream.py`.
- `BASE4` Grounded response schema, citations, and trace surfaces exist in `core/schemas/assistant.py`.
- `BASE5` Retrieval is already hybrid in `domain/chat/retrieval_context.py`.
- `BASE6` Level-up quiz creation / submission flows already exist and are UI-accessible.

These are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Track IDs

Use these stable IDs in commits, reports, and verification blocks:

- `AR0` Docs truth reset and drift correction
- `AR1` Tutor conductor and turn planning
- `AR2` Agentic evidence planning
- `AR3` Stream status protocol and frontend sync
- `AR4` Learner profile assembly
- `AR5` Research planner and candidate review
- `AR6` Background copilots, observability, and evaluation hardening

## Child Plan Map

Use these child files as the execution source of truth for each track:

- `docs/agentic/01_conductor_plan.md`
- `docs/agentic/02_evidence_plan.md`
- `docs/agentic/03_stream_sync_plan.md`
- `docs/agentic/04_learner_model_plan.md`
- `docs/agentic/05_research_plan.md`
- `docs/agentic/06_background_eval_plan.md`

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. Build on the current grounded tutor rather than replacing it with a generic agent loop.
2. Treat `domain/chat/query_analyzer.py` as the first planning seam; it is scaffolded and tested but not yet wired into the tutor runtime.
3. Upgrade retrieval into a bounded evidence planner rather than swapping out the current hybrid retriever.
4. Treat the canonical graph and provenance links as first-class evidence surfaces, not only a ranking bias.
5. Let the tutor propose quiz launch and review actions, but keep actual quiz creation/opening under runtime/UI control.
6. Expand the stream protocol instead of inventing a parallel status channel.
7. Use typed proposal objects for subagents and keep policy decisions in runtime code.
8. Keep research approval-gated and learner-facing ingestion deliberate.
9. Allow AR5 to use bounded online search/fetch adapters, but route every discovered result into pending candidate review before any ingest decision.

## Clarifications Requested

These points should be treated as already-decided clarifications for the remaining phase:

1. AR5 is intended to support online research in a bounded, inspectable way through runtime-owned adapters.
2. External search hits do not become trusted knowledge directly; they first enter the existing candidate-review queue.
3. "Deep search over everything learned" means a guarded review pack that synthesizes trusted workspace docs, approved and ingested research, graph state, mastery/readiness signals, quiz/practice history, and learner snapshots into outputs like:
   - what you have covered
   - what seems shaky
   - contradictions or open questions
   - what to review next
   - what changed recently
4. The current execution plan remains a guarded conductor. The future free-form multi-agent direction is intentionally deferred to `docs/FUTURE_FREEFORM_MULTI_AGENT.md`.

## Deferred Follow-On Scope (Not Active Execution Targets)

These are useful follow-ons but are not active implementation targets in this plan:

1. Extend uploaded-file ingestion beyond current formats to include `docx` and `pptx`.
2. Revisit a more free-form multi-agent runtime only after the guarded conductor, learner model, approval-gated research, and background review layers are stable.

## Removal Safety Rules

These rules apply whenever any child plan removes, replaces, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion:
   - deprecate -> route through facade/shim -> migrate callers -> delete
3. For deletions larger than trivial dead code, capture:
   - prior import/call sites
   - replacement module path
   - tests or checks proving parity
4. If a public route, payload, or CSS contract is removed or changed, record a compatibility note and rollback path in the child plan verification block.
5. Maintain the detailed removal ledger in the active child plan and summarize meaningful removals here.

## Removal Entry Template

Use this exact structure for every meaningful removal:

```text
Removal Entry - <track-id>

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

Current repo verification status at plan creation time:

- `pytest -q`: 555 passed (with `PYTHONPATH=.`, as of 2026-02-28)
- `npm --prefix apps/web test`: 87 passed (13 test files, as of 2026-02-28)
- `npm --prefix apps/web run typecheck`: not re-run during this planning pass

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `domain/chat/respond.py` | Main blocking tutor orchestration remains mostly linear. |
| `domain/chat/stream.py` | SSE phases exist but the protocol is still coarse. |
| `domain/chat/query_analyzer.py` | Planning seam exists but is not yet wired into runtime call paths. |
| `domain/chat/retrieval_context.py` | Hybrid retrieval exists, but graph and provenance expansion are still underused. |
| `apps/web/features/tutor/hooks/use-level-up-flow.ts` | Quiz flow exists, but the tutor does not yet orchestrate it deliberately. |
| `apps/web/features/tutor/types.ts` | UI intentionally collapses backend states into generic labels. |
| `domain/research/runner.py` | Research is approval-gated but still manual-source oriented. |
| `domain/chat/session_memory.py` | Session memory exists but is not assembled into a richer learner model. |

## Remaining Work Overview

### 1. Tutor planning is not explicit yet

The current tutor flow retrieves, assembles context, and answers. It does not yet expose a typed turn plan, query intent routing, or planner-owned action decisions.

### 2. Evidence planning is not yet multi-surface enough

The product already has hybrid retrieval, a canonical graph, and provenance links, but the tutor path does not yet combine them as a bounded evidence planner.

### 3. UX still under-represents backend work

The backend can already emit streaming phases, but the frontend collapses much of that detail. Quiz actions, graph expansion, and planning states are not yet visible as first-class tutor activity.

### 4. Learner and research loops are still too narrow

Mastery, readiness, and research candidate flows exist, but the broader learner-model and second-brain behaviors are still missing.

## Cross-Track Execution Order

The remaining work should be executed in the order below.

Each child-plan slice should end with green targeted tests before the next child plan starts.

### AR0 / AR1. Conductor track

Purpose:

- turn the tutor into a guarded conductor with typed turn planning

Root problem:

- current tutor orchestration is mostly linear and hard to inspect

Child plan:

- `docs/agentic/01_conductor_plan.md`

### AR2. Evidence planning track

Purpose:

- make evidence retrieval multi-step, graph-aware, and provenance-aware

Root problem:

- current evidence selection is still mostly one-shot

Child plan:

- `docs/agentic/02_evidence_plan.md`

### AR3. Stream sync track

Purpose:

- make backend activity visible to the frontend in a truthful, stable way

Root problem:

- current status protocol is too coarse and the frontend hides too much

Child plan:

- `docs/agentic/03_stream_sync_plan.md`

### AR4. Learner model track

Purpose:

- assemble a typed learner snapshot from the existing state fragments

Root problem:

- learner state is fragmented and underused

Child plan:

- `docs/agentic/04_learner_model_plan.md`

### AR5. Research track

Purpose:

- restore topic finding and approval-gated knowledge finding

Root problem:

- research is still manual-source oriented

Child plan:

- `docs/agentic/05_research_plan.md`

### AR6. Background / evaluation track

Purpose:

- add recommendation-first background copilots and harden regression coverage

Root problem:

- dynamic behavior will drift without stronger observability and tests

Child plan:

- `docs/agentic/06_background_eval_plan.md`

## Master Status Ledger

Update this table during execution:

| Track | Status | Last note |
|---|---|---|
| `AR0/AR1` Conductor | ✅ complete | All 6 slices done (AR0.1, AR1.1–AR1.5); 583 backend / 87 frontend tests passing |
| `AR2` Evidence planning | ✅ complete | All 4 slices done (AR2.1–AR2.4); 652 backend / 91 frontend tests passing |
| `AR3` Stream sync | ✅ complete | All 4 slices done (AR3.1–AR3.4); 657 backend / 94 frontend tests passing |
| `AR4` Learner model | ✅ complete | All 4 slices done (AR4.1–AR4.4); 692 backend tests passing |
| `AR5` Research | ✅ complete | All 4 slices done (AR5.1–AR5.4); 752 backend tests passing |
| `AR6` Background/eval | ✅ complete | All 4 slices done (AR6.1–AR6.4); 806 backend tests passing |

## Verification Block Template

```text
Verification Block - <track-id>

Root cause
- <why the old behavior was insufficient>

Files changed
- <path>
- <path>

What changed
- <implementation summary>

Commands run
- <command>
- <command>

Manual verification
- <user flow>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md.
Select the first child plan in execution order that still has incomplete slices.
Read that child plan and begin with its current incomplete slice exactly as described.

Execution loop:

1. Work on exactly one sub-slice at a time and keep the change set PR-sized.
2. Preserve all constraints in docs/AGENTIC_MASTER_PLAN.md and the active child plan.
3. Run the slice verification steps before claiming completion.
4. When a slice is complete, update:
   - the active child plan with a Verification Block
   - the active child plan with any Removal Entries added during that slice
   - docs/AGENTIC_MASTER_PLAN.md with the updated status ledger / remaining status note
5. After every 2 completed slices OR if your context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and the active child plan and restate which slices remain.
6. If the active child plan still has incomplete slices, continue to the next slice.
7. If the active child plan is complete, go back to docs/AGENTIC_MASTER_PLAN.md, pick the next incomplete child plan in order, and continue.

Stop only if:

- verification fails
- the current repo behavior does not match plan assumptions and the plan must be updated first
- a blocker requires user input or approval
- completing the next slice would force a risky scope expansion

Do NOT stop because one child plan is complete.
Do NOT stop because you updated the session plan, todo list, or status ledger.
The run is only complete when docs/AGENTIC_MASTER_PLAN.md shows no remaining incomplete tracks.

Treat core/prompting/ as already landed infrastructure. Preserve verify_assistant_draft(), preserve runtime-owned topic/mastery policy, and do not auto-ingest external research.

START:

Read docs/AGENTIC_MASTER_PLAN.md.
Pick the first incomplete child plan in execution order.
Begin with the current slice in that child plan exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/AGENTIC_MASTER_PLAN.md before every move to the next child plan. It can be dynamically updated. Check the latest version and continue.
```
