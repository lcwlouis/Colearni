# CoLearni Tutor Phase UX Fix Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `docs/archive/GENERATION_STATUS_PLAN_2026-03-01_pre-ux-phase-fix-rewrite.md`

Template source:
- `docs/prompt_templates/refactor_plan.md`

## Plan Completeness Checklist

This active plan should be treated as invalid if any of the following are missing:

1. archive snapshot references
2. current verification status
3. ordered remaining slices with stable IDs
4. verification block template
5. browser-visible acceptance targets
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 implementation slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Browser-visible behavior is the source of truth:
   - tests are necessary
   - they are not sufficient
   - the phase UX is not done until the tutor UI shows `Thinking…` before first output, switches to `Generating response…` only when visible text starts, and does not show `Finalizing…`
4. Keep FastAPI routes thin and keep `/chat/respond` stable.
5. Do not expose raw chain-of-thought, hidden reasoning text, prompt internals, or retrieved chunk bodies in logs, API responses, or UI.
6. Do not reopen completed backend streaming transport work unless the current slice is blocked by it.
7. This plan is specifically for tutor phase UX correctness. Do not widen it into a general chat rewrite.
8. This document is incomplete unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by a fenced code block containing the execution prompt

## Purpose

This document replaces the earlier thinking/streaming status plan.

The stream transport and delta plumbing are already in place. The remaining gap is narrower and user-visible:

- the frontend does not reliably show `Thinking…` before pre-output work
- the frontend exposes `Searching knowledge base…` as the first visible state
- the frontend still exposes `Finalizing…`, which is not necessary user-facing copy

The current goal is:

1. show `Thinking…` from request start until the first visible answer text
2. switch to `Generating response…` only when the first visible delta arrives
3. keep `searching` and `finalizing` available for backend/internal semantics if useful, but do not require them as user-facing labels
4. keep raw reasoning private and continue using metadata-only reasoning signals

## Inputs Used

This plan is based on:

- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/REFACTOR_PLAN.md`
- `docs/archive/GENERATION_STATUS_PLAN_2026-03-01_pre-ux-phase-fix-rewrite.md`
- `domain/chat/stream.py`
- `apps/api/routes/chat.py`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/features/tutor/types.ts`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/types.ts`
- `tests/domain/test_s1_phase_semantics.py`
- `tests/api/test_g3_stream.py`
- `apps/web/lib/api/client.test.ts`
- `apps/web/features/tutor/stream-messages.test.ts`
- current user report from 2026-03-01:
  - frontend goes from `searching` to streamed response to `finalising`
  - `thinking` is not visibly shown
  - `finalising` is probably unnecessary to show

## Executive Summary

The earlier plan is no longer accurate.

What is already true in the repo:

- the backend stream route exists
- text deltas render incrementally in the tutor UI
- the backend emits `responding` on the first non-empty visible delta, not at stream start
- safe reasoning metadata exists without exposing raw reasoning text
- blocking fallback no longer uses fake timer phases

What is still failing at the product level:

- `setChatPhase("thinking")` is immediately overwritten by incoming `searching` status events
- `searching` is still mapped to visible copy instead of being treated as part of the pre-output thinking period
- `finalizing` is still mapped to visible copy even though the user does not want it shown
- there is no targeted frontend test proving the visible phase sequence

The next work is mainly frontend semantics and acceptance verification, not backend streaming implementation.

## Browser-Visible Acceptance Target

The feature is only complete when a real browser run behaves like this:

1. Request starts:
   - visible label is `Thinking…`
2. Retrieval / prompt assembly / model internal work:
   - visible label remains `Thinking…`
   - `Searching knowledge base…` is not shown as the primary user-facing label
3. First visible streamed text delta arrives:
   - visible label switches to `Generating response…`
4. Stream completes / persist / verification:
   - `Finalizing…` is not shown to the user
   - the response simply settles into its final rendered state
5. Blocking or degraded fallback:
   - visible label stays `Thinking…` until final content is available
   - no fake intermediate generation label unless there is truly visible incremental output

## Current Verification Status

Current repo verification status:

- `.venv/bin/pytest -q tests/domain/test_s1_phase_semantics.py tests/api/test_g3_stream.py`: passing (`9 passed`)
- `npm --prefix apps/web test -- lib/api/client.test.ts features/tutor/stream-messages.test.ts`: passing (`15 passed`)
- no automated frontend test currently proves the visible `thinking -> generating` UX
- no browser automation was run in this check

Observed implementation state:

- backend semantic fix is landed
- frontend streaming parser and delta rendering are landed
- browser-visible phase UX is still incomplete based on the current code and user report

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered landed for this phase:

- `L1` Stream transport route and SSE framing
- `L2` Incremental text delta rendering
- `L3` Backend first-delta `responding` semantics
- `L4` Safe reasoning metadata contract
- `L5` Blocking fallback without fake timer phases
- `L6` Stream log spam reduction

Do not reopen these slices unless the current fix is blocked by them or the code no longer matches this plan.

## Current Findings

### 1. Backend timing is no longer the main bug

`domain/chat/stream.py` now emits `responding` only when the first non-empty delta is observed.

That earlier backend mismatch should be treated as fixed, not as remaining scope.

### 2. The visible `thinking` state is being replaced too early

`apps/web/features/tutor/hooks/use-tutor-messages.ts` sets `thinking` before starting the request, but then any `status` event directly replaces it.

That means a fast `searching` event can become the first label the user ever sees.

### 3. `searching` and `finalizing` are still exposed as user-facing labels

`apps/web/features/tutor/types.ts` still maps:

- `searching -> Searching knowledge base…`
- `finalizing -> Finalizing…`

That is now the main UX mismatch with the desired behavior.

### 4. The frontend lacks a dedicated test for visible phase policy

Current tests cover:

- SSE parsing
- delta assembly
- backend status sequence

Current tests do NOT cover:

- visible phase derivation in the tutor UI
- hiding `finalizing`
- collapsing pre-output work under `Thinking…`

### 5. The previous plan had become internally inconsistent

It still described old backend issues as remaining work even though the repo now contains fixes and passing tests for those areas.

This rewrite resets the plan to the actual remaining scope.

## Current Hotspots

| File | Why it matters now |
|---|---|
| `apps/web/features/tutor/hooks/use-tutor-messages.ts` | Current source of truth for how incoming status events become visible tutor phases. |
| `apps/web/features/tutor/types.ts` | Current mapping from internal phase names to user-facing copy. |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Current rendering surface for the status badge shown during chat loading. |
| `apps/web/lib/api/types.ts` | Stream status union should stay backward-compatible even if UI hides some phases. |
| `domain/chat/stream.py` | Backend contract is already mostly correct and should only be touched if the frontend fix proves impossible without small contract cleanup. |

## Decision Log

These decisions are already made for this fix plan:

1. `Thinking…` is the only required pre-output user-facing status.
2. `Generating response…` starts only after the first visible text delta.
3. `searching` may remain part of the internal/backend stream contract, but it does not need to remain a distinct user-facing label.
4. `finalizing` may remain part of the internal/backend contract, but it should not be shown to users unless a new explicit product need appears.
5. Raw reasoning text remains out of scope.
6. Safe reasoning metadata remains allowed.
7. This is a frontend semantics fix first; backend changes are optional and should be minimal.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `U0` Plan Reset and Acceptance Lock
- `U1` Visible Phase Policy
- `U2` Frontend Phase Derivation
- `U3` Frontend Test Coverage
- `U4` Manual Browser Verification
- `U5` Docs Closeout

### Completion Status

| Slice | Status | Summary |
|---|---|---|
| U0 | ✅ Done | Plan rewritten to match current repo state and real remaining UX gaps. |
| U1 | ✅ Done | PHASE_LABELS updated: searching/finalizing → "Thinking…". Added `visiblePhaseLabel()` helper. |
| U2 | ✅ Done | Hook no longer regresses from responding to pre-output phases on finalizing event. Delta safety net simplified. |
| U3 | ✅ Done | 8 frontend tests in `visible-phase.test.ts` covering all phase labels, no Searching/Finalizing visible. |
| U4 | ⏳ Manual | Requires real browser verification — see manual steps below. |
| U5 | ✅ Done | Plan updated, docs consistent. |

## Slice Plan

### U1. Visible Phase Policy

Purpose:
- define the user-facing meaning of each phase before changing code

Changes:
- lock the visible status policy to:
  - pre-output work: `Thinking…`
  - visible streamed text: `Generating response…`
  - post-stream cleanup: no user-facing label change
- decide whether `searching` and `finalizing` remain internal-only or are collapsed at the UI boundary

Verification:
- the implementation plan, tests, and UI copy all use the same visible phase policy

Exit criteria:
- there is no remaining ambiguity about what the user should see

### U2. Frontend Phase Derivation

Purpose:
- make the tutor UI reflect the visible policy instead of the raw stream contract

Changes:
- update `apps/web/features/tutor/hooks/use-tutor-messages.ts` so pre-output work stays visibly in `Thinking…`
- do not let early `searching` events become the first visible user label
- stop surfacing `finalizing` in the loading indicator
- keep the first-delta safety net for `responding`
- keep blocking fallback semantics aligned with the same visible policy

Verification:
- frontend unit coverage or focused logic tests for:
  - initial request shows `Thinking…`
  - `searching` does not replace visible `Thinking…`
  - first delta transitions to `Generating response…`
  - `finalizing` is not shown

Exit criteria:
- the UI no longer shows `Searching knowledge base…` as the primary initial status
- the UI no longer shows `Finalizing…`

### U3. Frontend Test Coverage

Purpose:
- add regression coverage for the actual UX contract

Changes:
- add tests for visible phase derivation and/or tutor timeline rendering
- prefer a small pure helper if it makes the phase policy easier to test directly

Verification:
- `npm --prefix apps/web test -- <targeted files>` passes

Exit criteria:
- the visible phase sequence is protected by frontend tests

### U4. Manual Browser Verification

Purpose:
- prove the actual browser behavior matches the plan

Changes:
- run the tutor flow with streaming enabled
- confirm the visible indicator sequence during a normal grounded answer
- confirm fallback behavior if streaming is disabled or unavailable

Verification:
- manual browser run confirms:
  - request starts with `Thinking…`
  - no visible `Searching knowledge base…`
  - text begins streaming before or as `Generating response…` appears
  - no visible `Finalizing…`

Exit criteria:
- browser-visible behavior matches the acceptance target

### U5. Docs Closeout

Purpose:
- leave the plan and related docs internally consistent

Changes:
- update this file with final completion status
- update any related docs only if the public API contract or observability story changed

Verification:
- plan state matches repo state
- no stale claims remain about backend timing being the active bug

Exit criteria:
- docs and implementation agree on what is done and what remains

## Verification Block Template

Use this exact structure for each completed slice:

```text
Verification Block - <slice-id>

Root cause
- <what was actually wrong>

Files changed
- <absolute or repo-relative paths>

What changed
- <concise summary of behavior change>

Commands run
- <exact commands>

Manual verification steps
- <browser or local checks performed>

Observed outcome
- <what passed, what remains, and any residual risk>
```

## Verification Matrix

| Area | Must pass |
|---|---|
| Backend targeted tests | `.venv/bin/pytest -q tests/domain/test_s1_phase_semantics.py tests/api/test_g3_stream.py` |
| Frontend targeted tests | `npm --prefix apps/web test -- <targeted files>` |
| Frontend typecheck | `npm --prefix apps/web run typecheck` |
| Browser UX | visible `Thinking…` before first delta; no visible `Searching knowledge base…`; no visible `Finalizing…` |
| Safety | no raw reasoning text in logs, API payloads, or UI |
| Plan consistency | this file reflects the actual current repo state |

## Risks and Controls

### Risk 1: Fixing the UI by changing the backend contract unnecessarily

- Control: prefer UI-layer derivation first; keep API/status enums backward-compatible unless a small cleanup is clearly needed

### Risk 2: Hiding `searching` removes useful diagnostics

- Control: keep `searching` in the stream contract if it is useful internally; only collapse it at the user-facing label layer

### Risk 3: `finalizing` is still needed for some edge cases

- Control: keep it internal until a concrete UX case proves it should be shown again

### Risk 4: Browser behavior still diverges from tests

- Control: require a real browser verification slice before closing the plan

## What Not To Do

- Do not rebuild the SSE transport.
- Do not reopen provider reasoning-summary work.
- Do not log or display raw chain-of-thought.
- Do not show `Searching knowledge base…` as the first visible status if the acceptance target is `Thinking…`.
- Do not show `Finalizing…` unless a new explicit product requirement justifies it.

## Deliverables

1. A tutor UI that visibly starts with `Thinking…`
2. A tutor UI that switches to `Generating response…` only when text starts arriving
3. No visible `Finalizing…` in the normal streamed flow
4. Frontend regression tests for the visible phase policy
5. A plan that matches the actual repo state

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open docs/GENERATION_STATUS_PLAN.md now. This file is the source of truth.
Treat backend streaming transport and first-delta responding semantics as already landed.
The current bug is browser-visible phase UX:
- the user should see Thinking… before output
- Searching knowledge base… should not be the primary visible status
- Generating response… should begin only when visible text starts
- Finalizing… should not be shown to the user

Do not rebuild streaming from scratch.
Do not widen this into a general chat rewrite.
Do not expose raw reasoning text.
Prefer a frontend-layer fix unless a very small backend cleanup is clearly required.

For each completed slice, report:
- Root cause
- Files changed
- What changed
- Commands run
- Manual verification steps
- Observed outcome

START:
- Read docs/GENERATION_STATUS_PLAN.md.
- Begin with U1 and U2.
- Stop after each slice for verification before continuing.
```
