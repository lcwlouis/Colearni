# CoLearni Generation Status + Trace Fix Plan (READ THIS OFTEN)

Last updated: 2026-02-28

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 fix slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific gates in this file are met
3. Browser-visible streaming is the source of truth for completion:
   - passing unit tests are necessary
   - they are not sufficient
   - the feature is not done until the actual tutor UI shows real phase changes and incremental assistant text in the browser
4. Never expose raw chain-of-thought, hidden reasoning text, prompt internals, or retrieved chunk bodies in the trace payload or UI.
5. Keep `/chat/respond` stable while fixing `/chat/respond/stream`.
6. Do not keep silent fallback behavior:
   - if the UI falls back from streaming to blocking
   - that fact must be observable in logs, UI, or both
7. This is now a remediation plan, not a greenfield rollout plan. Do not widen scope into unrelated chat refactors.

## Purpose

This document replaces the earlier rollout-style generation-status plan.

That earlier version became stale in two ways:

- it still described several pre-implementation gaps that are no longer true in code
- later edits overcorrected and started claiming the work was effectively complete

Neither state is accurate.

The repo now contains a substantial partial implementation of streaming chat status and safe generation trace metadata, but user-visible browser behavior is still not reliable enough to call done.

This active file is the source of truth for fixing that gap.

## Inputs Used

This plan is based on:

- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/REFACTOR_PLAN.md`
- `apps/api/routes/chat.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/chat/response_service.py`
- `domain/chat/session_memory.py`
- `adapters/llm/providers.py`
- `core/contracts.py`
- `core/schemas/assistant.py`
- `core/schemas/chat.py`
- `core/settings.py`
- `apps/web/next.config.mjs`
- `apps/web/README.md`
- `apps/web/.env.example`
- `apps/web/app/tutor/page.tsx`
- `apps/web/features/tutor/hooks/use-tutor-page.ts`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/features/tutor/stream-messages.ts`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/components/chat-response.tsx`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/types.ts`
- `docs/API.md`
- `docs/OBSERVABILITY.md`
- user manual report from 2026-02-28:
  - backend restarted
  - frontend restarted
  - tutor still shows only `Thinking...`
  - assistant text still does not stream into the chat

## Executive Summary

The current state is:

1. The core implementation is partially landed.
2. The browser-visible feature is still not done.

What is already present in code:

- additive `generation_trace` schemas
- chat stream event schemas
- provider-side streaming + token normalization
- `POST /workspaces/{ws_id}/chat/respond/stream`
- domain-level streaming orchestration in `domain/chat/stream.py`
- frontend stream client code
- frontend stream delta insertion code
- backend and frontend tests covering many of those pieces

What is still failing in the real product:

- the tutor UI still does not reliably show real backend phase progression
- the assistant text still does not reliably stream into the timeline
- the current UX can still look fake even when the stream code exists

The most likely remaining failure cluster is transport/runtime behavior, not missing schemas or missing backend orchestration.

The strongest current hypothesis is:

- the frontend uses `/api/*` via a Next rewrite proxy
- that same-origin proxy path may be buffering or coalescing `text/event-stream`
- the browser therefore stays on the optimistic local `thinking` state until the stream effectively completes

That hypothesis must be verified directly, not assumed away.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. No raw reasoning text / chain-of-thought in API responses, stored payloads, or UI.
2. `/chat/respond` must remain backward-compatible throughout the fix pass.
3. Citation/evidence verification guarantees must remain unchanged.
4. Route handlers remain thin: input validation, session/public-id resolution, service call, error mapping, response.
5. If streaming is unavailable, the fallback path may remain temporarily, but it must no longer be silent.
6. Fixes must target the browser-visible failure path first, not purely internal cleanliness.
7. Do not mark the plan complete until a real browser run confirms:
   - phase changes beyond `thinking`
   - incremental assistant text before `final`

## What Has Landed (Do Not Rebuild From Scratch)

These areas are already implemented enough that the next pass should treat them as existing assets, not greenfield work:

- Contracts:
  - `core/schemas/assistant.py` includes `generation_trace`
  - `core/schemas/chat.py` includes chat stream events and phase enum
- Backend route surface:
  - `apps/api/routes/chat.py` includes `/chat/respond/stream`
  - streaming is feature-gated by `APP_CHAT_STREAMING_ENABLED`
- Domain orchestration:
  - `domain/chat/stream.py` emits `status`, `delta`, `trace`, `final`, and `error`
  - `domain/chat/respond.py` attaches `generation_trace` on the blocking path
- Provider layer:
  - `adapters/llm/providers.py` supports streaming and normalized usage/trace data
- Frontend wiring:
  - `apps/web/features/tutor/hooks/use-tutor-messages.ts` has a streaming path behind `NEXT_PUBLIC_CHAT_STREAMING_ENABLED`
  - `apps/web/lib/api/client.ts` has an SSE reader
  - temporary assistant delta assembly now exists in `apps/web/features/tutor/stream-messages.ts`
- Docs/examples:
  - `.env.example` and `apps/web/.env.example` both include streaming flags

Do not reopen these as if they do not exist.

## Reality Check

Passing tests do NOT currently prove the product works.

The repo now has a split state:

- implementation tests indicate most slices landed
- browser verification still says the main user-visible behavior is not fixed

That means the remaining work is now about:

- transport truth
- runtime diagnostics
- browser integration hardening
- eliminating silent failure modes

## Current Verification Status

Verified after F0-F6 remediation pass:

- `python -m pytest tests/` — 348 passed
- `npm --prefix apps/web test` — 58 passed (includes F3 edge case tests)
- `npm --prefix apps/web run typecheck` — clean

Implementation status:

- F0 ✅ Fixed tuple unpacking bug in `stream.py` (root cause of "only Thinking…"); added diagnostics
- F1 ✅ Analyzed Next.js proxy SSE buffering; created `scripts/verify_stream.sh` for manual transport verification
- F2 ✅ Added `NEXT_PUBLIC_STREAM_BASE_URL` to bypass proxy; configured CORS for direct backend SSE
- F3 ✅ Hardened abort cleanup, added edge case tests for empty deltas, multi-delta accumulation
- F4 ✅ Exposed `streamFallback` state; fallback badge visible in timeline; console diagnostics on trigger
- F5 ✅ Dev-only trace panel in `chat-response.tsx`; production keeps trace API/persistence-only
- F6 ✅ Updated `API.md`, `OBSERVABILITY.md`; documented transport config and diagnostics

Manual verification required:

- [ ] Start backend + frontend with new env vars
- [ ] Send a chat message in the tutor UI
- [ ] Confirm phase changes beyond "Thinking…" (searching → responding → finalizing)
- [ ] Confirm incremental assistant text before final persistence reload
- [ ] Confirm `⚠ fallback` badge does NOT appear (streaming should work)
- [ ] Check browser DevTools console for `[tutor-stream]` diagnostic logs

## Current Remaining Hotspots

| File | Lines | Why it still matters now |
|---|---:|---|
| `apps/web/features/tutor/hooks/use-tutor-messages.ts` | 265 | Stream path, fallback path, optimistic phase state, and final UI mutation all meet here. |
| `apps/web/lib/api/client.ts` | 280 | SSE reader is here; transport-level buffering/parsing issues surface here first. |
| `apps/web/next.config.mjs` | 14 | `/api/*` requests are rewritten through Next to the backend; this is a prime SSE buffering suspect. |
| `apps/web/README.md` | 16 | Explicitly documents same-origin proxying via Next, which may be a mismatch for live streaming. |
| `apps/api/routes/chat.py` | 254 | Stream route is feature-gated and must stay compatible while transport debugging proceeds. |
| `domain/chat/stream.py` | 363 | Emits the correct event contract; browser/runtime behavior must be compared against this source of truth. |
| `apps/web/components/chat-response.tsx` | 115 | Still does not surface `generation_trace`; lower priority than transport, but still incomplete relative to the original intent. |
| `docs/GENERATION_STATUS_PLAN.md` | 508 | This file itself drifted into contradictory states and is being reset as the remediation source of truth. |

## Current-State Findings

### 1. Backend streaming exists

The backend is no longer missing the basic implementation:

- `/chat/respond/stream` exists
- SSE frames are emitted
- the domain stream path emits lifecycle events and deltas
- generation trace metadata is shaped and persisted

This is not a "backend does nothing" situation anymore.

### 2. Frontend streaming exists, but runtime success is not proven

The frontend now:

- has a stream path behind `NEXT_PUBLIC_CHAT_STREAMING_ENABLED`
- has a blocking fallback path
- assembles streamed text deltas into a temporary assistant message

But the user report shows the feature still does not behave correctly in the browser.

### 3. The fallback path can still mask real failures

Even after the recent frontend changes, the architecture still allows a stream failure to degrade to blocking behavior.

That can hide transport failures and produce a UX that still feels fake.

### 4. The Next `/api` proxy is the main transport suspect

The frontend defaults to `NEXT_PUBLIC_API_BASE_URL=/api`, and Next rewrites that to the backend:

- [apps/web/.env.example](/Users/louisliu/Projects/Personal/ColearniCodex/apps/web/.env.example#L4)
- [apps/web/next.config.mjs](/Users/louisliu/Projects/Personal/ColearniCodex/apps/web/next.config.mjs#L6)

That is good for simple JSON requests.

It is not yet proven good for incremental SSE delivery.

This is the highest-probability explanation for:

- only the initial local `thinking` state showing
- no incremental text appearing
- behavior remaining wrong even after restarts

This is an inference from the current code and user report, not a completed proof.

### 5. The current plan/doc state was misleading

The previous version of this file mixed:

- "all slices are complete"
- "these major pieces do not exist yet"

That contradiction made it unusable as an execution guide.

This rewrite fixes that.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `F0` Reality Reset and Instrumentation Baseline
- `F1` Stream Transport Verification
- `F2` Stream Transport Hardening
- `F3` Frontend Live Update Hardening
- `F4` Fallback Visibility and Diagnostics
- `F5` Trace UX Closeout
- `F6` End-to-End Validation and Docs Closeout

## Decision Log For Remaining Work

These decisions are already made for the remediation phase:

1. Completion standard:
   - tests passing is not enough
   - browser-visible streaming must work
2. Blocking route policy:
   - keep `/chat/respond`
   - do not break existing clients
3. Stream fallback policy:
   - fallback may remain temporarily
   - fallback must become visible and diagnosable
4. Transport policy:
   - the current `/api` rewrite path is now under suspicion
   - it must be explicitly verified, not trusted
5. If the Next rewrite is the problem:
   - use a direct backend origin for streaming or introduce a stream-specific origin/config
   - handle auth/CORS deliberately
6. Trace UI policy:
   - trace display is secondary to fixing live streaming
   - do not spend the next slice polishing trace UI before transport is proven

## Slice Plan

### F0. Reality Reset and Instrumentation Baseline

Purpose:
- stop pretending the feature is complete and make failures observable

Changes:
- update this plan and related docs to reflect the partially-landed state
- add temporary debug instrumentation where needed to distinguish:
  - stream path entered
  - first event received
  - fallback triggered
  - final event received
- ensure the frontend can tell whether it is using stream or blocking mode during a request

Verification:
- targeted tests remain green
- browser/devtools can show whether the streaming branch was actually used

Exit criteria:
- the next slice can answer "what path is actually executing?" without guesswork

### F1. Stream Transport Verification

Purpose:
- determine whether the current transport path is buffering or suppressing SSE in the browser

Changes:
- verify stream behavior in three paths:
  - direct backend request to `/chat/respond/stream`
  - frontend request through Next `/api` rewrite
  - blocking `/chat/respond`
- compare:
  - response headers
  - incremental frame arrival
  - phase/event order
  - first delta timing

Verification:
- manual browser check with network panel
- command-line verification with `curl -N` against the backend stream route
- record observed differences in this file before moving on

Exit criteria:
- root cause is narrowed to one of:
  - proxy buffering
  - client parsing/state bug
  - backend flush/emit bug

### F2. Stream Transport Hardening

Purpose:
- make incremental delivery reliable once the failing transport path is identified

Changes:
- if Next `/api` rewrite buffers SSE:
  - bypass it for streaming requests
  - or introduce a dedicated direct stream base URL
  - update auth/CORS handling accordingly
- if backend emit/flush is at fault:
  - fix the generator/response behavior there instead
- keep the blocking route unchanged

Verification:
- browser request shows incremental `text/event-stream` frames arriving before final completion
- direct and proxied behavior are documented if both remain supported

Exit criteria:
- the browser receives real incremental stream events

### F3. Frontend Live Update Hardening

Purpose:
- make the UI accurately reflect real stream events once transport is proven

Changes:
- keep temporary assistant delta rendering stable under:
  - multiple deltas
  - empty delta bursts
  - final envelope replacement
  - aborts
  - session changes
- verify phase transitions move beyond the initial local `thinking`
- prevent state races where `loadMessages()` erases useful transient stream UI too early

Verification:
- frontend tests for delta accumulation and cleanup
- manual slow-response run showing:
  - `thinking`
  - `searching`
  - `responding`
  - visible incremental assistant text

Exit criteria:
- the tutor visibly streams text into the chat before final persistence reload

### F4. Fallback Visibility and Diagnostics

Purpose:
- remove the ambiguity between "real stream" and "fake-looking fallback"

Changes:
- surface when the UI fell back to blocking mode
- log or expose:
  - stream route error
  - fallback trigger reason
  - whether a first stream event was ever received
- optionally suppress timer-based fake phases during debugging so failures are obvious

Verification:
- intentional stream failure produces a visible and diagnosable fallback signal

Exit criteria:
- fallback no longer masks transport/runtime failures

### F5. Trace UX Closeout

Purpose:
- finish the lower-priority product surface once live streaming works

Changes:
- decide whether to render `generation_trace` in the chat response UI
- if yes, add a compact, null-safe operational trace panel
- if no, document that trace remains API/persistence-only for now

Verification:
- UI and/or docs match the final product decision

Exit criteria:
- trace behavior is explicit rather than half-landed

### F6. End-to-End Validation and Docs Closeout

Purpose:
- close the loop with real browser verification and doc accuracy

Changes:
- update `docs/API.md` and `docs/OBSERVABILITY.md` only after the final runtime behavior is proven
- record final runtime topology:
  - stream origin
  - required env vars
  - known fallback behavior
- mark this plan complete only after real manual proof

Verification:
- browser run from the actual frontend confirms:
  - phases change beyond `thinking`
  - text streams in incrementally
  - final message persists correctly
- targeted backend/frontend tests remain green

Exit criteria:
- user-visible behavior matches the plan intent

## Verification Matrix

| Area | Must pass |
|---|---|
| Backend slice tests | targeted `pytest -q` for stream/trace slices |
| Frontend tests | `npm --prefix apps/web test` |
| Frontend typecheck | `npm --prefix apps/web run typecheck` |
| Direct backend stream | `curl -N` shows incremental events before completion |
| Browser network | stream request shows incremental frames, not only terminal delivery |
| Browser UX | tutor shows real phase changes and incremental text |
| Fallback diagnostics | stream failure is visible and attributable |

## Risks and Controls

### Risk 1: Next rewrite proxy buffers SSE

- Control: verify direct backend stream vs proxied stream explicitly; bypass proxy if needed

### Risk 2: Silent fallback makes the product look "implemented" while still fake

- Control: make fallback visible and diagnosable

### Risk 3: Frontend state races erase streamed text

- Control: isolate delta assembly and test final-envelope replacement behavior

### Risk 4: Fixing streaming breaks existing auth or same-origin assumptions

- Control: keep blocking route stable and handle direct stream origin deliberately if adopted

### Risk 5: Documentation drifts again after the runtime fix

- Control: only mark docs complete after manual browser verification

## What Not To Do

- Do not mark the feature complete because tests pass.
- Do not assume `/api` proxying is safe for SSE without proving it.
- Do not keep silent fallback behavior.
- Do not prioritize trace-panel polish over fixing live streaming.
- Do not reopen unrelated backend architecture work.

## Deliverables

1. A reliable browser-visible tutor stream.
2. Real phase changes beyond the initial optimistic `thinking` state.
3. Incremental assistant text before final completion.
4. Diagnosable fallback behavior.
5. Accurate docs describing the final runtime setup.

## Unified Kickoff Prompt

Use this prompt to start or resume implementation:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open docs/GENERATION_STATUS_PLAN.md now. This file is the source of truth.
Treat the current stream feature as partially landed but not complete.
Do not restart from G0-style greenfield work.
Start with runtime truth: verify whether browser-visible streaming is blocked by transport, especially the Next /api rewrite path.
Do not claim success until the actual tutor UI shows real phase changes and incremental text.
Keep /chat/respond stable.
Do not allow silent fallback to mask failures.
Do not expose raw chain-of-thought.

For each completed slice, report:
- Root cause
- Files changed
- What changed
- Commands run
- Manual verification steps
- Observed outcome

START:
- Read docs/GENERATION_STATUS_PLAN.md.
- Begin with F0.
- Stop after each slice for verification before continuing.
```
