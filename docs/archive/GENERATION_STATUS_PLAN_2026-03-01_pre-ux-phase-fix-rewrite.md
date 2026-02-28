# CoLearni Thinking + Streaming Status Plan (READ THIS OFTEN)

Last updated: 2026-02-28

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
   - the feature is not done until the tutor UI shows `Thinking…` before output and only shows content-generation status once text actually begins
4. Never expose raw chain-of-thought, hidden reasoning text, prompt internals, or retrieved chunk bodies in logs, API responses, or UI.
5. Keep `/chat/respond` stable while updating `/chat/respond/stream`.
6. If provider support differs, normalize behavior behind shared contracts and clearly document what is inferred vs actually available.
7. This plan is specifically for thinking/status semantics and safe reasoning metadata. Do not widen it into a general chat rewrite.

## Purpose

This document replaces the earlier generation-status remediation plan.

The streaming transport path is now mostly in place. The next product gap is different:

- the UI currently says `Generating response…` too early
- the backend emits `responding` before any user-visible text delta arrives
- the system only has safe reasoning metadata today, not a trustworthy cross-provider stream of reasoning text

The new goal is:

1. show `Thinking…` while the model is internally working but has not produced visible content
2. switch to `Generating response…` only when the first real text delta arrives
3. keep raw reasoning private
4. optionally support provider-specific reasoning summaries later, but do not depend on them for core UX

## Inputs Used

This plan is based on:

- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/REFACTOR_PLAN.md`
- `apps/api/routes/chat.py`
- `domain/chat/stream.py`
- `domain/chat/respond.py`
- `domain/chat/response_service.py`
- `adapters/llm/providers.py`
- `core/contracts.py`
- `core/schemas/assistant.py`
- `core/schemas/chat.py`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/features/tutor/types.ts`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/components/chat-response.tsx`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/types.ts`
- current repo behavior as of 2026-02-28
- current user requirement:
  - show `Thinking…` while the LLM is still thinking
  - show `Generating response…` only when visible text is actually streaming
  - if there is no streaming and no reasoning-specific signal, `Generating response…` may still be used as fallback

## Executive Summary

Current state:

- the backend can stream `status`, `delta`, `trace`, `final`, and `error`
- the frontend can render text deltas incrementally
- the system captures safe reasoning metadata like `reasoning_tokens`
- the system does NOT have a reliable, provider-neutral stream of raw reasoning text

Current product mismatch:

- `domain/chat/stream.py` emits `responding` before the first text delta
- the frontend maps `responding` to `Generating response…`
- this makes the UI claim content generation has started even when the model may still be thinking internally

Correct target behavior:

1. `Thinking…`
   - after request start
   - during retrieval
   - during model internal work before first visible output token
2. `Generating response…`
   - only after the first visible text delta arrives
3. `Finalizing…`
   - after text generation is done, during verify/persist/final assembly

Reasoning visibility policy:

- safe reasoning metadata is allowed
- raw reasoning text is not
- optional provider-specific reasoning summaries may be explored later behind explicit gating, but are not required for correct phase UX

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. No raw reasoning text / chain-of-thought in logs, API payloads, or UI.
2. `/chat/respond` must remain backward-compatible.
3. Existing evidence/citation verification guarantees must remain unchanged.
4. Route handlers remain thin: input validation, session/public-id resolution, service call, error mapping, response.
5. `responding` must no longer mean "LLM call started"; it must mean "visible response text has started".
6. Thinking-state UX must not depend on provider-specific reasoning text support.
7. If no streaming is available, fallback semantics must be explicit and documented.

## What Has Landed (Do Not Rebuild From Scratch)

These areas already exist and should be reused:

- `apps/api/routes/chat.py`
  - streaming route exists
- `domain/chat/stream.py`
  - emits chat stream events and text deltas
- `adapters/llm/providers.py`
  - supports streaming text deltas
  - extracts safe reasoning metadata (`reasoning_tokens`) when available
- `core/contracts.py`
  - includes `TutorTextStream`
- `core/schemas/chat.py`
  - includes `ChatPhase` and stream event models
- `core/schemas/assistant.py`
  - includes `GenerationTrace`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
  - already consumes stream events
- `apps/web/features/tutor/types.ts`
  - already has `thinking`, `searching`, `responding`, `finalizing`

Do not reopen this work as if streaming does not exist.

## Reality Check

What the system can safely know today:

- whether the request has started
- whether retrieval is in progress
- whether the first visible output delta has arrived
- whether streaming is complete
- whether reasoning metadata like `reasoning_tokens` was present after completion

What the system cannot safely assume today:

- that OpenAI or LiteLLM will provide raw thought text
- that a cross-provider "thinking trace" is available in real time
- that provider-specific reasoning items can be treated as stable product UX

Therefore:

- core UX should be driven by actual output timing, not hidden-thought payloads

## Current Verification Status

Current implementation baseline:

- stream route exists
- delta rendering exists
- safe trace metadata exists

Current semantic mismatch:

- backend `responding` event is still emitted before first delta
- frontend label for `responding` is still `Generating response…`

Manual acceptance still required:

- start a chat turn
- observe `Thinking…` before any streamed text
- observe `Generating response…` only after streamed text begins

## Current Remaining Hotspots

| File | Lines | Why it still matters now |
|---|---:|---|
| `domain/chat/stream.py` | 363 | Current source of truth for lifecycle event timing; `responding` is emitted too early. |
| `adapters/llm/providers.py` | 563 | Current provider abstraction; only safe reasoning metadata is available cross-provider today. |
| `core/schemas/chat.py` | 127 | Phase contract may need semantic clarification and/or new safe metadata events. |
| `core/contracts.py` | 90 | Shared stream contract may need explicit first-delta or reasoning-capability semantics. |
| `apps/web/features/tutor/hooks/use-tutor-messages.ts` | 265 | Frontend status behavior and delta handling meet here. |
| `apps/web/features/tutor/types.ts` | 43 | Labels still map `responding` to generation regardless of whether content has started. |
| `apps/web/components/chat-response.tsx` | 115 | Optional future place for safe reasoning metadata or reasoning summary UI. |
| `docs/API.md` | 1650 | Will need to document the new phase semantics if the contract changes. |
| `docs/OBSERVABILITY.md` | 168 | Will need to document what reasoning metadata is logged and what is intentionally not logged. |

## Current-State Findings

### 1. OpenAI and LiteLLM do not give us a safe universal "thought stream"

From current implementation and provider constraints:

- both providers can stream visible text deltas
- both may expose usage metadata
- some reasoning-capable models may expose reasoning-related metadata
- neither path should be treated as a stable, universal raw-thought stream for product UI

Therefore:

- "Thinking…" should be inferred from the absence of visible output after generation starts
- not from raw reasoning text

### 2. The current `responding` event is semantically wrong for UX

Right now the backend emits `responding` before output actually appears.

That makes the frontend label inaccurate even when the stream transport works correctly.

### 3. Safe reasoning metadata is still useful

It is reasonable to log and optionally persist:

- `reasoning_requested`
- `reasoning_supported`
- `reasoning_used`
- `reasoning_tokens`
- provider/model identity

It is not reasonable by default to log:

- raw reasoning text
- private chain-of-thought
- provider-specific hidden traces

### 4. Optional reasoning summaries are future work, not baseline UX

If a future provider path can expose an explicit reasoning summary safely:

- that should be additive
- feature-gated
- provider-specific
- never required for correct status semantics

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `S0` Status Semantics Reset
- `S1` Backend First-Delta Phase Correction
- `S2` Safe Reasoning Metadata Contract
- `S3` Frontend Thinking-vs-Generating UX
- `S4` Fallback and Non-Streaming Semantics
- `S5` Optional Reasoning Summary Exploration
- `S6` Docs and Acceptance Closeout

### Completion Status

| Slice | Status | Summary |
|---|---|---|
| S0 | ✅ Done | ChatPhase docstring updated with semantic contract |
| S1 | ✅ Done | Removed premature `responding` emit; now fires on first non-empty delta |
| S2 | ✅ Done | Added `reasoning_requested/supported/used` to GenerationTrace |
| S3 | ✅ Done | Frontend auto-transitions to `responding` on first delta (safety net) |
| S4 | ✅ Done | Blocking fallback keeps `Thinking…` until response arrives; no fake timers |
| S5 | ✅ Deferred | Raw reasoning summaries explicitly deferred; metadata fields sufficient |
| S6 | ✅ Done | API.md, OBSERVABILITY.md, and plan updated |

## Decision Log For Remaining Work

These decisions are already made for this phase:

1. `Thinking…` is the default pre-output state.
2. `Generating response…` begins only after the first visible text delta.
3. Raw reasoning text is out of scope and should not be logged or shown.
4. Safe reasoning metadata is allowed.
5. Provider-specific reasoning summaries, if any, are optional future work.
6. The user should not need provider-specific reasoning support to get correct status behavior.

## Slice Plan

### S0. Status Semantics Reset

Purpose:
- define the correct phase meanings before changing code

Changes:
- update this plan to make phase semantics explicit
- define canonical meanings:
  - `thinking`: request started, no visible output yet
  - `searching`: retrieval/context assembly work
  - `responding`: first visible text delta has arrived
  - `finalizing`: post-generation verification/persistence
- define fallback meaning when there is no streaming

Verification:
- plan, docs, and implementation target all use the same semantics

Exit criteria:
- there is no ambiguity about when each phase should appear

### S1. Backend First-Delta Phase Correction

Purpose:
- make the backend event stream reflect real visible generation timing

Changes:
- update `domain/chat/stream.py` so it does NOT emit `responding` before the first text delta
- emit `responding` only when:
  - the first non-empty visible text delta is observed, or
  - a non-streaming fallback path starts producing final content without incremental deltas
- ensure clarification and social fast-paths still behave coherently

Verification:
- backend tests for:
  - no `responding` before first delta
  - `responding` emitted once
  - no duplicate phase transitions

Exit criteria:
- backend phase events match real visible output timing

### S2. Safe Reasoning Metadata Contract

Purpose:
- make reasoning-related metadata explicit without exposing raw thought text

Changes:
- extend or clarify `GenerationTrace` and/or stream trace metadata with safe reasoning fields such as:
  - `reasoning_requested`
  - `reasoning_supported`
  - `reasoning_used`
  - `reasoning_tokens`
- keep all raw reasoning text excluded
- ensure OpenAI and LiteLLM behavior is normalized where possible, and clearly nullable where not possible

Verification:
- schema tests
- adapter tests for missing vs present reasoning metadata

Exit criteria:
- safe reasoning metadata is explicit and raw reasoning text remains impossible through the normal contract

### S3. Frontend Thinking-vs-Generating UX

Purpose:
- show the right status at the right time

Changes:
- update `apps/web/features/tutor/hooks/use-tutor-messages.ts` and related types/UI so:
  - `Thinking…` persists until first visible delta
  - `Generating response…` begins only once text is actually streaming
  - `Finalizing…` remains reserved for post-generation work
- keep transient stream rendering stable while status changes

Verification:
- frontend tests for phase transitions
- manual browser run confirming the visible sequence

Exit criteria:
- the UI no longer claims content generation before content exists

### S4. Fallback and Non-Streaming Semantics

Purpose:
- make status behavior correct even when there is no incremental stream

Changes:
- define and implement explicit fallback semantics for:
  - blocking path
  - stream failure
  - provider with no delta stream
- recommended default:
  - keep `Thinking…` until final content is available
  - optionally switch directly to final content without a fake intermediate generating state
  - only use `Generating response…` in fallback when there is truly no reasoning/thinking distinction available and that compromise is documented

Verification:
- manual and automated fallback-path tests

Exit criteria:
- fallback behavior is explicit and no longer misleading

### S5. Optional Reasoning Summary Exploration

Purpose:
- evaluate whether provider-specific reasoning summaries are worth adding later

Changes:
- investigate a gated path for safe reasoning summaries where providers support them
- if explored, keep it behind:
  - provider capability checks
  - explicit feature flag
  - clear UI separation from normal answer text
- do not block S1-S4 on this work

Verification:
- docs or prototype showing exact supported cases

Exit criteria:
- either:
  - a small safe design is accepted, or
  - the plan explicitly defers this work

Status: **DEFERRED**
Decision: Raw reasoning summaries are explicitly deferred. The S2 safe reasoning metadata
(`reasoning_requested`, `reasoning_supported`, `reasoning_used`, `reasoning_tokens`) provides
sufficient operational visibility. Provider reasoning summary text varies in format, quality,
and availability across OpenAI reasoning models and LiteLLM-proxied providers. Exposing it
would require per-provider parsing, sanitization, and a separate UI surface with clear
separation from the answer text. This work is not justified until there is a concrete user
need. The metadata fields already allow the frontend to show "This response used reasoning"
without displaying any reasoning content.

### S6. Docs and Acceptance Closeout

Purpose:
- document the final semantics and close the loop with real UX validation

Changes:
- update `docs/API.md` if event semantics changed
- update `docs/OBSERVABILITY.md` to state what reasoning metadata is logged
- keep this file accurate with the final result

Verification:
- browser run confirms:
  - `Thinking…` before first output
  - `Generating response…` only after first visible delta
  - no raw reasoning text exposed

Exit criteria:
- implementation, docs, and browser behavior all match

## Verification Matrix

| Area | Must pass |
|---|---|
| Backend tests | targeted `pytest -q` for stream/status semantics |
| Frontend tests | `npm --prefix apps/web test` |
| Frontend typecheck | `npm --prefix apps/web run typecheck` |
| Browser UX | `Thinking…` before first delta; `Generating response…` only after text appears |
| Safety | no raw reasoning text in logs, API payloads, or UI |
| Docs | event semantics and reasoning metadata accurately documented |

## Risks and Controls

### Risk 1: Provider differences make "thinking" semantics inconsistent

- Control: drive UX from output timing, not hidden provider-specific thought payloads

### Risk 2: Raw reasoning accidentally leaks through logs or trace payloads

- Control: keep reasoning contract allowlist-based and metadata-only

### Risk 3: Non-streaming fallback becomes misleading

- Control: define explicit fallback semantics instead of pretending generation started

### Risk 4: Optional reasoning summaries distract from the core UX fix

- Control: keep them strictly later and gated

## What Not To Do

- Do not log or display raw chain-of-thought.
- Do not use provider-specific hidden reasoning payloads as the baseline UX contract.
- Do not show `Generating response…` before visible text exists.
- Do not block the core status fix on optional reasoning-summary work.

## Deliverables

1. Correct phase semantics tied to real visible output timing.
2. Safe reasoning metadata contract with no raw reasoning leakage.
3. Frontend UX that distinguishes thinking from generating.
4. Explicit fallback semantics for non-streaming or degraded paths.
5. Updated docs describing the final behavior.

## Unified Kickoff Prompt

Use this prompt to start or resume implementation:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open docs/GENERATION_STATUS_PLAN.md now. This file is the source of truth.
Treat streaming transport as already mostly implemented.
The goal is now semantic correctness:
- show Thinking… until the first visible output delta
- show Generating response… only after text actually starts streaming
- never expose raw chain-of-thought
- only use safe reasoning metadata

Do not rebuild streaming from scratch.
Do not depend on provider-specific reasoning text to get correct UX.
Keep /chat/respond stable.
Keep routes thin.

For each completed slice, report:
- Root cause
- Files changed
- What changed
- Commands run
- Manual verification steps
- Observed outcome

START:
- Read docs/GENERATION_STATUS_PLAN.md.
- Begin with S1 unless you discover the contract must change first.
- Stop after each slice for verification before continuing.
```
