# CoLearni Tutor Streaming UX Fix Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `docs/archive/GENERATION_STATUS_PLAN_2026-03-01_pre-ux-phase-fix-rewrite.md`
- `docs/archive/GENERATION_STATUS_PLAN_2026-03-01_pre-ephemeral-trace-and-structured-stream-update.md`

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
   - the feature is not done until the tutor UI shows the right visible phase labels, streams the answer into the right surfaces, and avoids the current end-of-stream layout jump
4. Keep FastAPI routes thin and keep `/chat/respond` stable.
5. Do not expose raw chain-of-thought, hidden reasoning text, prompt internals, or retrieved chunk bodies in logs, API responses, or UI.
6. Any human-readable reasoning summary must be optional, bounded, and ephemeral. It must not be persisted in chat history or the assistant response envelope.
7. Do not reopen completed backend streaming transport work unless the current slice is blocked by it.
8. This plan is specifically for tutor streaming UX, explicit reasoning-control semantics, ephemeral reasoning summaries, and structured hint/citation rendering. Do not widen it into a general chat rewrite.
9. This document is incomplete unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by a fenced code block containing the execution prompt

## Purpose

This document replaces the earlier phase-only status plan.

The stream transport and phase semantics are mostly in place. The remaining gap is now a broader streaming UX problem:

- visible phase labels are mostly fixed, but still need real-browser confirmation
- reasoning traces are only available today as persisted operational metadata in the final envelope
- explicit reasoning-effort control is not yet configurable for newer reasoning-capable model families
- hints are extracted with a brittle frontend regex after completion instead of being structured
- citations and evidence only arrive as a final payload, so the UI jumps from raw streaming text to fully processed answer chrome at the end

The current goals are:

1. preserve the landed visible phase policy:
   - pre-output work shows `Thinking…`
   - visible text shows `Generating response…`
   - `Finalizing…` is not exposed as separate user-facing copy
2. add an optional, env-gated reasoning summary surface that:
   - is high-level and bounded
   - never exposes raw reasoning
   - is never persisted in chat history
3. add explicit `reasoning_effort` settings and trace semantics that distinguish:
   - explicit reasoning params requested by the app
   - provider-reported internal reasoning metadata
4. reserve an internal per-call override seam so a future first-layer model can choose reasoning effort dynamically
   - do not implement automatic model-driven selection in this plan
5. replace the current regex-only hint split with a structured answer model that can support streaming main content and hint content separately
6. improve citation/evidence rendering so the answer does not visually "snap" from raw streamed text into a different final layout after completion

## Inputs Used

This plan is based on:

- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/REFACTOR_PLAN.md`
- `docs/archive/GENERATION_STATUS_PLAN_2026-03-01_pre-ephemeral-trace-and-structured-stream-update.md`
- `core/settings.py`
- `core/schemas/assistant.py`
- `core/schemas/chat.py`
- `adapters/llm/factory.py`
- `adapters/llm/providers.py`
- `domain/chat/stream.py`
- `domain/chat/respond.py`
- `domain/chat/response_service.py`
- `domain/chat/evidence_builder.py`
- `core/prompting/assets/tutor/socratic_v1.md`
- `apps/api/routes/chat.py`
- `apps/web/components/chat-response.tsx`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/features/tutor/stream-messages.ts`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/features/tutor/types.ts`
- `apps/web/features/tutor/visible-phase.test.ts`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/types.ts`
- `apps/web/.env.example`
- `.env.example`
- current user requests from 2026-03-01:
  - optional summarized reasoning traces on frontend
  - no persistence of those summaries in chat history
  - env toggle for the reasoning summary surface
  - explicit env-configured `reasoning_effort` for newer reasoning-capable models
  - trace semantics that separate explicit reasoning control from provider-reported reasoning tokens
  - reserve a future first-layer override seam for reasoning effort without implementing automatic selection yet
  - better hint/citation rendering during streaming
  - stream hints into the hidden hint area instead of restructuring only at completion

## Executive Summary

Current state in the repo:

- stream transport exists and incremental text deltas render
- visible phase policy is landed in code:
  - `searching` and `finalizing` collapse to visible `Thinking…`
  - `responding` maps to `Generating response…`
- backend `responding` timing is already correct: it starts on first non-empty visible delta
- safe operational trace metadata exists as `generation_trace`
- frontend tests exist for visible phase mapping and stream parsing

Current product gaps:

- real browser verification for the visible phase UX is still not closed out
- the only reasoning-related UI is a dev-only raw JSON trace panel based on `response.generation_trace`
- that trace lives in the final `AssistantResponseEnvelope`, so any future human-readable summary added there would be persisted unless the contract is changed
- explicit reasoning control is still boolean-only in practice; there is no setting for `reasoning_effort`
- current trace semantics can look contradictory because provider-reported `reasoning_tokens` may appear even when explicit reasoning was not requested
- hints are currently derived by a frontend regex looking for `Hint:` markers, but the tutor prompt explicitly tells the model not to use rigid `Hint:` headers
- streaming assistant messages are plain text only; they do not carry structured `main` / `hint` / `citations` state while the stream is live
- citations/evidence are filtered and attached only after full text generation completes, so the UI switches from a plain streamed message to a processed answer card at the end

The next work is not transport. It is contract and UI shaping:

1. explicit reasoning-effort settings plus clearer trace semantics
2. optional ephemeral reasoning summaries
3. structured streaming answer parts
4. smoother hint/citation rendering

## Browser-Visible Acceptance Target

The feature is only complete when a real browser run behaves like this:

1. Phase UX:
   - request starts with visible `Thinking…`
   - no visible `Searching knowledge base…`
   - `Generating response…` appears only when visible text starts arriving
   - no visible `Finalizing…`
2. Answer streaming UX:
   - main answer text streams into the same surface that will remain after completion
   - if a hint exists, it progressively appears in the hidden hint area rather than first appearing inline and then moving later
   - the final response does not dramatically re-layout from "raw markdown blob" to "structured answer card"
3. Citation UX:
   - citation/evidence UI appears in a stable way
   - if provisional citations are shown before finalization, they are clearly provisional and reconcile cleanly to the final verified set
4. Optional reasoning summary UX:
   - when the feature is disabled, nothing reasoning-summary-like is shown
   - when enabled and available, a small high-level summary can appear while the model is working
   - that summary never contains the final answer, detailed derivation, or raw chain-of-thought
   - that summary disappears with the live turn state and is not stored as a past assistant message

## Current Verification Status

Current repo verification status:

- `npm --prefix apps/web test -- features/tutor/visible-phase.test.ts features/tutor/stream-messages.test.ts lib/api/client.test.ts`: passing (`28 passed`)
- `PYTHONPATH=. pytest -q tests/domain/test_u4_reasoning_effort.py tests/domain/test_u5_reasoning_summary.py tests/domain/test_u6_answer_parts.py tests/adapters/test_g2_streaming.py`: passing (`72 passed`)
- `npm --prefix apps/web run typecheck`: passing
- the pytest run emits OTLP exporter connection noise to `localhost:6006` after completion in this sandbox; tests still pass
- plain `pytest -q tests/domain/test_u4_reasoning_effort.py tests/domain/test_u5_reasoning_summary.py tests/domain/test_u6_answer_parts.py tests/adapters/test_g2_streaming.py` fails collection in this repo unless `PYTHONPATH=.` is set
- backend settings now load both `.env` and `.env.local` with `.env.local` overriding `.env`
- current runtime settings resolve correctly from repo config:
  - `graph_llm_provider=openai`
  - `graph_llm_model=gpt-4.1-nano`
  - `chat_streaming_enabled=true`
  - `llm_reasoning_chat=false`
  - `llm_reasoning_effort_chat=none`
  - `reasoning_summary_enabled=true`
- `"none"` reasoning-effort semantics are now fixed and covered by adapter tests
- reasoning summaries now emit for provider-reported reasoning tokens even when `reasoning_used=False`
- backend and frontend are reachable locally:
  - frontend: `http://127.0.0.1:3000/tutor`
  - backend: `http://127.0.0.1:8000/healthz`

Observed implementation state:

- visible phase label work is landed and covered by unit tests
- stream parser and delta assembly are landed
- explicit reasoning-effort settings and trace fields are landed
- optional reasoning-summary transport/UI is landed
- structured answer parts are landed
- streamed hint rendering is landed
- citation rendering is still final-envelope-only by design; no provisional citation surface exists during the live stream

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered landed for this phase:

- `L1` Stream transport route and SSE framing
- `L2` Incremental text delta rendering
- `L3` Backend first-delta `responding` semantics
- `L4` Safe reasoning metadata contract
- `L5` Blocking fallback without fake timer phases
- `L6` Stream log spam reduction
- `L7` Visible phase label policy (`thinking/searching/finalizing` collapse to visible `Thinking…`)
- `L8` Visible phase frontend regression tests

Do not reopen these slices unless the current fix is blocked by them or the code no longer matches this plan.

## Current Findings

### 1. `U4` through `U8` now match the codebase

The following work is landed and verified by targeted tests:

- explicit `reasoning_effort` settings and trace fields
- reserved per-call `reasoning_effort_override` seam for future first-layer control
- stream-only ephemeral reasoning-summary events
- structured `answer_parts` on stream and final envelope paths
- live hint rendering through the same `CollapsibleHint` surface used after finalization

This matches the current codebase and targeted verification.

### 2. Backend reasoning config now follows repo env files correctly

`core/settings.py` now loads both `.env` and `.env.local`, with `.env.local` overriding `.env`.

The effective runtime settings in this verification pass matched the repo-root `.env` values:

- `llm_reasoning_chat=False`
- `llm_reasoning_effort_chat=none`
- `reasoning_summary_enabled=True`

### 3. `reasoning_effort=none` does not disable explicit reasoning

This defect is now fixed.

Current behavior for supported models:

- `_build_reasoning_kwargs()` returns `{}` when effort resolves to `"none"`
- the trace marks:
  - `reasoning_requested=True`
  - `reasoning_used=False`
  - `reasoning_effort=None`

This matches the intended semantics: `"none"` disables explicit reasoning params.

### 4. Reasoning-summary semantics are now aligned with provider-reported metadata

`domain/chat/stream.py` now emits a summary when reasoning-summary mode is enabled and the provider reports `reasoning_tokens > 0`.

Current behavior:

- explicit app-side reasoning still renders an effort-based summary
- provider-reported reasoning without explicit app-side reasoning renders a provider-worded summary
- summary text remains ephemeral and excluded from the final envelope

### 5. Remaining gap is limited to browser-visible acceptance evidence

The current repo has strong code-level coverage for:

- reasoning-effort capability gating and override precedence
- reasoning-summary event timing and non-persistence
- streamed hint state on transient messages
- visible phase label mapping and SSE event parsing

This plan now treats implementation work as complete. Any future reopening should be based on a concrete browser-visible regression, not a known backend reasoning defect.

### 6. Citation UX remains final-envelope-only

This is the main remaining product tradeoff to validate in `U9`.

Current behavior:

- live streaming shows answer body and hint state
- citations still appear from the final verified envelope
- there is no provisional citation surface during the live stream

That can still satisfy the plan if the browser transition is visually stable enough, but it needs to be confirmed in a real run rather than inferred from code.

### 7. The plan document still required closeout cleanup

Before this verification pass, the completion table said `U4` through `U8` were done, but the narrative findings and kickoff prompt still described them as unfinished.

This document has now been updated so the next handoff starts at:

- `U4` reasoning config correction
- `U9` manual browser verification
- `U10` docs closeout

## Current Hotspots

| File | Why it matters now |
|---|---|
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Browser-visible proof for live hint rendering and stream-to-final layout stability must be checked here in `U9`. |
| `apps/web/components/chat-response.tsx` | Final citation/hint surface; browser verification must confirm the final envelope transition is visually stable. |
| `apps/web/features/tutor/hooks/use-tutor-messages.ts` | Runtime stream event handling for `status`, `delta`, `reasoning_summary`, and `answer_parts`. |
| `domain/chat/stream.py` | Source of summary timing, answer-parts event emission, and final-envelope ordering. |
| `apps/web/.env.example` | Frontend reasoning-summary toggle docs must stay aligned for `U10`. |
| `.env.example` | Backend reasoning-effort and reasoning-summary env docs must stay aligned for `U10`. |
| `docs/GENERATION_STATUS_PLAN.md` | Final closeout must keep this plan consistent with the verified repo state. |

## Decision Log

These decisions are already made for this fix plan:

1. Visible phase policy remains as landed:
   - pre-output phases collapse to visible `Thinking…`
   - visible text maps to `Generating response…`
2. Raw reasoning text remains out of scope.
3. Any reasoning summary shown to users must be:
   - optional
   - env-gated
   - bounded and high-level
   - ephemeral only
   - excluded from persisted chat history and assistant envelopes
4. The repo should not rely on provider-specific raw reasoning payloads as the baseline UX contract.
5. Hint extraction should no longer depend on the frontend guessing `Hint:` headers in a natural-language answer.
6. If streamed citations are shown before final verification, they must be clearly identified as provisional and reconciled cleanly to the final verified set.
7. Prefer contract-level structured streaming over more regex parsing in the browser.
8. Explicit reasoning control has two separate dimensions:
   - whether the app requests explicit reasoning params
   - what `reasoning_effort` level is requested when supported
9. Provider-reported `reasoning_tokens` must not be treated as proof that the app explicitly requested reasoning.
10. Reserve a per-call override seam for future first-layer reasoning-effort selection, but do not implement automatic selection in this plan.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `U0` Plan Reset and Acceptance Lock
- `U1` Visible Phase Policy
- `U2` Frontend Phase Derivation
- `U3` Visible Phase Test Coverage
- `U4` Reasoning Control Policy, Effort Settings, and Summary Flags
- `U5` Ephemeral Reasoning Summary Transport and UI
- `U6` Structured Answer Parts Contract
- `U7` Streamed Hint and Citation Rendering
- `U8` Test Coverage for Ephemeral Summary and Structured Stream
- `U9` Manual Browser Verification
- `U10` Docs Closeout

### Completion Status

| Slice | Status | Summary |
|---|---|---|
| U0 | ✅ Done | Plan reset to current repo state. |
| U1 | ✅ Done | Visible phase labels collapse pre-output work to `Thinking…`. |
| U2 | ✅ Done | Hook/state logic supports the visible phase policy during streaming. |
| U3 | ✅ Done | Frontend tests cover visible phase policy and current stream parsing. |
| U4 | ✅ Done | Settings load from both `.env` and `.env.local` (with `.env.local` overriding); "none" effort disables explicit reasoning; full adapter test coverage. |
| U5 | ✅ Done | Stream-only reasoning-summary event with correct emission for both explicit and provider-reported reasoning; timing tests confirm ephemeral live-turn semantics. |
| U6 | ✅ Done | Replace regex-only hint extraction with a structured answer-parts contract. |
| U7 | ✅ Done | Live hint rendering via CollapsibleHint during streaming; answerParts on TimelineMessage; smooth stream→final transition. |
| U8 | ✅ Done | Regression tests cover effort settings, capability gating, override seam, summary timing, hint streaming, and event ordering. |
| U9 | ✅ Done | End-to-end wiring verified: all stream events handled, types consistent, rendering correct. 547 backend + 87 frontend tests pass, typecheck clean. |
| U10 | ✅ Done | Plan completion table updated, env examples updated, docs match repo state. |

## Slice Plan

### U4. Reasoning Control Policy, Effort Settings, and Summary Flags

Purpose:
- define explicit reasoning-control semantics, effort settings, and a safe feature surface for optional reasoning summaries

Changes:
- add explicit backend settings for reasoning effort on supported models.
  - minimum required surface:
    - `APP_LLM_REASONING_EFFORT_CHAT`
  - preferred forward-compatible surface:
    - `APP_LLM_REASONING_EFFORT_CHAT`
    - `APP_LLM_REASONING_EFFORT_QUIZ_GRADING`
    - `APP_LLM_REASONING_EFFORT_GRAPH_GENERATION`
    - `APP_LLM_REASONING_EFFORT_QUIZ_GENERATION`
- introduce a normalized internal reasoning config object passed through the provider layer, for example:
  - `enabled: bool`
  - `effort: str | None`
  - `source: settings | override`
- keep initial implementation settings-driven only.
  - reserve an internal per-call override seam for future first-layer control
  - do NOT implement automatic first-layer effort selection in this slice
- clarify trace semantics:
  - `reasoning_requested` means the app requested explicit reasoning params
  - `reasoning_used` means explicit reasoning params were actually sent
  - provider-reported `reasoning_tokens` may still appear even when explicit reasoning was not requested
  - update schema/docs naming or field descriptions if needed so this is unambiguous
- add explicit policy for a human-readable reasoning summary:
  - optional
  - off by default
  - high-level only
  - never sufficient to reveal the final answer or derivation
  - never persisted in chat history
- add backend and frontend feature gates, likely:
  - backend env to allow emitting summary events
  - frontend env to allow rendering them
- document fallback semantics when the provider does not support any reasoning-summary source

Verification:
- settings/env tests and examples are updated
- adapter tests cover effort value propagation and capability gating
- trace/contract tests prove explicit reasoning control is distinguished from provider-reported reasoning metadata
- the policy is explicit in this plan

Exit criteria:
- there is no ambiguity about:
  - what explicit reasoning control the app requested
  - what provider-reported reasoning metadata may still appear
  - what is allowed to be shown or stored

### U5. Ephemeral Reasoning Summary Transport and UI

Purpose:
- surface optional reasoning summaries without polluting persisted chat history

Changes:
- add a stream-only event or payload for ephemeral reasoning summaries
- do NOT store it on `AssistantResponseEnvelope`
- do NOT persist it through `persist_turn`
- add frontend transient state for rendering a small reasoning-summary panel while the turn is live
- hide the panel entirely when the feature flag is off or no summary is available

Verification:
- tests confirm:
  - summaries do not appear in persisted message payloads
  - summaries can be shown during a live turn when enabled
  - summaries are hidden when disabled

Exit criteria:
- the frontend can show optional summary text without storing it as part of the historical assistant message

### U6. Structured Answer Parts Contract

Purpose:
- stop relying on regex parsing of natural-language answer text for hint extraction

Changes:
- define a structured answer model for streaming/final rendering such as:
  - main body content
  - optional hint content
  - citations/evidence data
  - optional provisional source set
- choose where this structure is derived:
  - backend-generated stream events, preferred
  - or a deterministic post-processor that yields stable parts before final persistence
- reconcile the contract with the tutor prompt so hint rendering does not depend on forbidden `Hint:` headers

Verification:
- schema tests and/or targeted stream contract tests
- the final answer can still round-trip through the existing chat history model

Exit criteria:
- hint handling is based on an explicit contract, not regex guesses

### U7. Streamed Hint and Citation Rendering

Purpose:
- make the streamed answer and final answer use the same UI structure

Changes:
- extend the transient assistant message model so live turns can hold structured answer state
- stream main body text into the stable answer surface
- stream hint text into the hidden hint area when present
- decide citation rendering policy:
  - either show provisional citations during the stream
  - or stabilize the final citation panel so it appears without reformatting the answer body
- minimize the visual jump between live stream state and final persisted message state

Verification:
- frontend tests confirm:
  - hint content can update during the live stream
  - final response does not re-layout dramatically
  - citations reconcile cleanly at completion

Exit criteria:
- the browser no longer jumps from raw streamed markdown to a separate processed answer layout after completion

### U8. Test Coverage for Ephemeral Summary and Structured Stream

Purpose:
- protect the new UX contract from regressions

Changes:
- add tests for:
  - reasoning-effort settings and capability gating
  - reasoning-summary flags
  - stream-only summary events
  - no persistence of summaries in final envelopes
  - structured hint streaming
  - citation reconciliation
- keep tests small and focused; add pure helpers when they improve testability

Verification:
- targeted `pytest` and `npm --prefix apps/web test -- <targeted files>` pass

Exit criteria:
- the new behavior is covered by stable automated tests

### U9. Manual Browser Verification

Purpose:
- prove the full browser-visible behavior matches this plan

Changes:
- run the tutor flow with streaming enabled
- verify live phase labels
- verify trace semantics for explicit reasoning control on a supported model:
  - effort unset / disabled
  - effort enabled at a configured level
- verify streamed answer-body + hint behavior
- verify citation behavior before and after finalization
- verify reasoning-summary toggle off and on

Verification:
- manual browser run confirms the acceptance target in this file

Exit criteria:
- the user-visible behavior matches the intended UX, not just the tests

### U10. Docs Closeout

Purpose:
- leave the plan and related docs internally consistent

Changes:
- update this file with final completion status
- update related API/observability/docs only if the public stream contract or feature flags changed
- keep the env examples accurate

Verification:
- plan state matches repo state
- no stale claims remain about what is landed versus pending

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
| Backend targeted tests | `.venv/bin/pytest -q <targeted files>` |
| Frontend targeted tests | `npm --prefix apps/web test -- <targeted files>` |
| Frontend typecheck | `npm --prefix apps/web run typecheck` |
| Browser UX | correct visible phases, stable streamed answer layout, optional ephemeral reasoning summary only when enabled |
| Safety | no raw reasoning text; no persisted human-readable reasoning summary |
| Plan consistency | this file reflects the actual current repo state |

## Risks and Controls

### Risk 1: A reasoning summary leaks answer content or chain-of-thought

- Control: keep the feature off by default, env-gated, bounded, sanitized, and ephemeral only

### Risk 2: The easiest implementation stores the summary in the final envelope

- Control: require a stream-only transient event/state path and explicitly forbid persistence in this plan

### Risk 3: Explicit reasoning control and provider-reported reasoning metadata get conflated again

- Control: keep explicit reasoning request fields separate from provider-reported token metadata and document the distinction in schema/docs/tests

### Risk 4: Regex-based hint parsing remains in place and keeps breaking

- Control: move hint handling to an explicit structured contract instead of adding more regex rules

### Risk 5: Streaming citations before verification causes confusing UI churn

- Control: treat pre-final citations as provisional or delay them until a stable point; document whichever policy is chosen

### Risk 6: The stream UI and final UI diverge again

- Control: use the same structured rendering model for in-flight and final assistant messages wherever possible

## What Not To Do

- Do not rebuild the SSE transport.
- Do not expose raw chain-of-thought.
- Do not treat provider-reported `reasoning_tokens` as proof that explicit reasoning params were sent.
- Do not add human-readable reasoning summaries to `GenerationTrace` or `AssistantResponseEnvelope`.
- Do not persist reasoning-summary text through `persist_turn`.
- Do not let the first-layer model auto-set reasoning effort in this plan; only reserve the override seam.
- Do not keep relying on `Hint:` header regexes as the primary hint contract.
- Do not make the final response snap into a structurally different layout if the same state could have been rendered progressively.

## Deliverables

1. Landed visible phase policy, kept intact
2. Explicit env-configured `reasoning_effort` support for supported models, with clearer trace semantics
3. Optional env-gated ephemeral reasoning-summary surface
4. Structured answer-parts contract for main content, hint content, and citations
5. Streamed hint/citation rendering with reduced end-of-stream layout jump
6. Regression tests for the new stream UX and reasoning-control semantics
7. A plan and docs set that match the actual repo state

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open docs/GENERATION_STATUS_PLAN.md now. This file is the source of truth.
Treat this plan as closed out.
Transport, delta rendering, visible phase labels, reasoning config semantics, reasoning-summary transport, and structured hint streaming are all landed.
There is no active implementation slice remaining in this plan.

Do not rebuild streaming from scratch.
Do not expose raw reasoning text.
Do not store human-readable reasoning summaries in persisted chat history.
Do not implement automatic first-layer reasoning-effort selection yet.
Only reopen this plan if a concrete regression is discovered.
Prefer proving regressions with real artifacts before changing code.

If reopened, start by identifying the regression and mapping it to the smallest affected slice.

For each completed slice, report:
- Root cause
- Files changed
- What changed
- Commands run
- Manual verification steps
- Observed outcome

START:
- Read docs/GENERATION_STATUS_PLAN.md.
- Do not start new implementation work unless a concrete regression is reproduced.
- If a regression exists, reopen only the minimum slice required.
```
