# Observability Refactor Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `docs/archive/OBSERVABILITY_REFACTOR_PLAN_2026-03-01_pre-overhaul.md`

Template usage:
- This is a task-specific plan for the Phoenix / observability overhaul.
- It does not replace `docs/REFACTOR_PLAN.md`.
- This file is the execution source of truth for observability work only.

## Plan Completeness Checklist

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 observability slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` with:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps
   - Observed outcome
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. This is a maintainability / observability refactor plan. Do not mix in unrelated feature work.
8. This plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

This document is the active execution plan for the Phoenix / observability overhaul.

Earlier work already landed basic OTel wiring, `emit_event()`, and non-streaming `llm.call` spans.
That baseline is not enough for debugging real app behavior in Phoenix:

- HTTP roots are missing.
- many traces are flat and status-less
- streaming chat is barely traced
- structured events do not appear in Phoenix
- prompt metadata is not attached to spans
- many domain spans have empty-looking input/output columns
- full prompt/response capture is impossible because content is truncated

This new plan exists because the repo already has observability hooks, but they are currently too partial and inconsistent to explain how the system actually works.

## Inputs Used

This plan is based on:

- `docs/prompt_templates/refactor_plan.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/OBSERVABILITY.md`
- `docs/PLAN.md` (especially S45 prompt-context / Phoenix notes)
- `docs/archive/OBSERVABILITY_REFACTOR_PLAN_2026-03-01_pre-overhaul.md`
- current repository layout and verification status as of 2026-03-01

## Executive Summary

What is already in good shape:

- OTel export remains optional and env-gated.
- Non-streaming LLM calls already create child spans and capture provider usage when the SDK returns it.
- Prompt assets already expose metadata via `PromptRegistry.render_with_meta()`.
- Targeted backend observability tests already exist and are passing when the repo is run with `PYTHONPATH=.`

What is still materially missing:

1. Phoenix trace structure is incomplete.
   - No `http.request` root span.
   - Streaming chat lacks proper spans.
   - Retrieval and background tasks are mostly invisible.
2. Phoenix detail panes are missing the data needed for debugging.
   - `emit_event()` does not create span events.
   - spans stay `UNSET`
   - many chain spans have no input/output summary
   - prompt IDs, task families, retries, and section coverage are absent
3. Token and prompt auditing are not trustworthy enough.
   - some call paths never emit LLM spans
   - streaming token usage is not traced to Phoenix
   - full prompt/response bodies are truncated at 4096 chars
   - there is no explicit distinction between provider-reported and estimated token counts

The remaining work should stay narrow: fix the observability substrate, then normalize high-value paths, then update docs/tests so Phoenix becomes a reliable debugging tool rather than an optional log sink.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. Keep FastAPI routes thin. Observability logic belongs in middleware, adapters, or domain helpers, not in routes.
2. Preserve provider-agnostic behavior. Phoenix must remain optional, and OpenAI / LiteLLM paths must share the same observability contract.
3. Full prompt/response capture must be explicitly gated by env and treated as dev-only / trusted-environment behavior by default.
4. Do not silently invent token counts. If estimated usage is added, it must be labeled as estimated and distinguishable from provider-reported usage.
5. Preserve graph and agent budget semantics; observability must expose budget stops, not change them.
6. Tests are required for new behavior, especially for streaming, span events, and token accounting fallbacks.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `BASE-1` Optional OTLP export wiring and content-recording feature flag already exist.
- `BASE-2` Non-streaming LLM adapter spans already capture provider/model plus usage fields when the SDK returns them.
- `BASE-3` Prompt assets already expose typed metadata via `PromptRegistry.render_with_meta()`.
- `BASE-4` Targeted backend observability tests are present and currently passing with `PYTHONPATH=.`

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `OBS-1` Trace foundation: root spans, span status, and Phoenix-visible events
- `OBS-2` LLM tracing parity: streaming, token accounting, and content-capture policy
- `OBS-3` Prompt identity and call separation metadata
- `OBS-4` Domain span normalization for chat, practice, quizzes, retrieval, and ingestion
- `OBS-5` Graph deep tracing and budget-debug visibility
- `OBS-6` Docs, regression coverage, and Phoenix operator guidance

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. `emit_event()` should remain as the single app-facing API, but internally it must write both to logs and to the active span as a real trace event.
2. We will improve Phoenix navigation by making spans more informative, not by suppressing spans wholesale. The UI problem is low-signal spans, not merely span count.
3. Full prompt / response capture will remain env-gated. The default safe behavior stays metadata-first.
4. Prompt identity must come from the prompt asset system (`prompt_id`, `version`, `task_type`) instead of ad-hoc string tags.
5. Token accounting should prefer provider usage, optionally fall back to explicit estimates, and always expose the usage source.
6. Streaming chat must have observability parity with blocking chat; otherwise Phoenix will always under-report tutor traffic.

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, or observability helper without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged replacement over hard deletion:
   - add facade/helper -> migrate call sites -> delete old path
3. For removals larger than trivial dead code, capture:
   - prior import/call sites
   - replacement module path
   - tests or checks proving parity
4. If a public payload or env var changes, include a compatibility note and rollback path in the slice verification block.
5. Maintain a removal ledger in this file during the run.

## Removal Entry Template

Use this exact structure for every meaningful removal:

```text
Removal Entry - <slice-id>

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

Current repo verification status:

- `pytest -q`: fails during collection from repo root because package imports are unresolved without `PYTHONPATH=.`
- `PYTHONPATH=. pytest -q tests/core/test_observability.py tests/adapters/test_graph_llm_observability.py`: passing
- `PYTHONPATH=. pytest -q tests/domain/test_graph_gardener.py tests/domain/test_graph_resolver.py`: passing
- `PYTHONPATH=. pytest -q tests/api/test_middleware.py tests/api/test_g3_stream.py tests/api/test_chat_respond.py`: passing
- `npm --prefix apps/web test`: not run during this investigation
- `npm --prefix apps/web run typecheck`: not run during this investigation

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `core/observability.py` | 426 | Owns span lifecycle, event emission, token extraction, redaction, and content truncation. |
| `apps/api/middleware.py` | 37 | Missing documented HTTP root span; today it only propagates `request_id`. |
| `adapters/llm/providers.py` | 598 | All non-streaming and streaming provider observability behavior converges here. |
| `domain/chat/respond.py` | 336 | Blocking chat has a root span but is missing session/user metadata and richer prompt/debug fields. |
| `domain/chat/stream.py` | 374 | Streaming chat currently lacks root spans and true Phoenix trace parity. |
| `domain/chat/retrieval_context.py` | 128 | Retrieval stage is invisible in Phoenix despite being core to grounded answers. |
| `domain/learning/practice.py` | 744 | Practice generation spans are present but mostly empty-looking from the Phoenix list view. |
| `domain/learning/quiz_flow.py` | 672 | Grading emits events, but they are not visible in Phoenix and root spans lack strong summaries. |
| `domain/graph/gardener.py` | 547 | Budget usage is logged only; Phoenix trace detail does not explain cluster decisions or hard stops. |
| `domain/graph/pipeline.py` | 170 | Resolver root span is too coarse to explain per-chunk extraction / merge behavior. |
| `domain/ingestion/post_ingest.py` | 190 | Background summary generation is not grouped under a parent span. |
| `docs/OBSERVABILITY.md` | 248 | Documentation overstates current behavior and must be reconciled with the actual code. |

## Remaining Work Overview

### 1. Trace structure is incomplete and misleading

Phoenix cannot show a trustworthy tree when requests do not start with an HTTP root, streaming chat lacks spans, and background work is only partially grouped.

### 2. Span payloads are too sparse for debugging

Many chain spans only show a name and a few scalar attributes. Phoenix list view becomes a wall of empty-looking calls because inputs, outputs, prompt identity, and decision summaries are not consistently attached.

### 3. Token and prompt visibility are partial

Provider usage is only captured on some paths. Streaming is not represented in Phoenix, full prompt/response bodies are truncated, and there is no standard metadata explaining whether token counts are actual, estimated, or absent.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green targeted tests before the next slice starts.

### OBS-1. Slice 1: Trace foundation

Purpose:

- Make Phoenix show real request trees, real status, and real events.

Root problem:

- `emit_event()` only logs.
- `start_span()` never marks success/failure.
- middleware does not create the documented HTTP root span.

Files involved:

- `core/observability.py`
- `apps/api/middleware.py`
- `tests/core/test_observability.py`
- `tests/api/test_middleware.py`

Implementation steps:

1. Extend `start_span()` to record exceptions and set OTel span status on both success and failure.
2. Make `emit_event()` also attach the sanitized payload to the active span via `span.add_event(...)`.
3. Add `http.request` root spans in middleware with request method, path, request ID, and response status.
4. Preserve current log emission behavior so existing log-based workflows keep working.

What stays the same:

- Observability remains env-gated.
- `emit_event()` remains the public helper used by domain code.

Verification:

- `PYTHONPATH=. pytest -q tests/core/test_observability.py`
- `PYTHONPATH=. pytest -q tests/api/test_middleware.py`

Exit criteria:

- Phoenix Events tab shows domain events for traced operations.
- Root request spans are visible and no longer show `UNSET` on normal success paths.

### OBS-2. Slice 2: LLM tracing parity

Purpose:

- Ensure every real LLM API call, including streaming tutor calls, produces one rich child LLM span with token accounting.

Root problem:

- Non-streaming and streaming observability are inconsistent.
- Some traces show zero cumulative tokens because the LLM call is missing from the trace tree.
- Full prompt/response capture currently truncates at 4096 chars with no fallback story.

Files involved:

- `adapters/llm/providers.py`
- `core/observability.py`
- `core/contracts.py`
- `tests/adapters/test_graph_llm_observability.py`
- `tests/adapters/test_g2_streaming.py`
- `tests/domain/test_g5_trace.py`

Implementation steps:

1. Introduce a single helper path for sync + streaming LLM span creation.
2. Add real LLM spans and events for `generate_tutor_text_stream()`.
3. Attach usage-source metadata: `provider_reported`, `estimated`, or `missing`.
4. Define a content-capture policy for long prompts/responses:
   - span preview/hash/length always
   - full body only when the dedicated env gate allows it
   - if Phoenix attribute size is too small, attach chunked span events or a linked storage reference
5. Preserve `GenerationTrace` for API responses while aligning it with Phoenix span behavior.

What stays the same:

- Provider adapters remain the only place that knows SDK-specific usage response shapes.
- Public chat response payloads keep using the existing `GenerationTrace` model unless a separately planned contract change is approved.

Verification:

- `PYTHONPATH=. pytest -q tests/adapters/test_graph_llm_observability.py`
- `PYTHONPATH=. pytest -q tests/adapters/test_g2_streaming.py`
- `PYTHONPATH=. pytest -q tests/domain/test_g5_trace.py`

Exit criteria:

- Streaming tutor generations produce Phoenix-visible `LLM` child spans.
- Phoenix token counts are non-zero whenever usage is reported or explicitly estimated.

### OBS-3. Slice 3: Prompt identity and call separation

Purpose:

- Make Phoenix navigation intelligible by separating calls by task, prompt, retry, and purpose.

Root problem:

- Most LLM spans are just named `llm.call`.
- Prompt IDs and versions exist in the repo but are not emitted.

Files involved:

- `core/prompting/registry.py`
- `domain/chat/prompt_kit.py`
- `domain/chat/query_analyzer.py`
- `domain/learning/quiz_flow.py`
- `domain/learning/practice.py`
- `domain/ingestion/post_ingest.py`
- `adapters/llm/providers.py`

Implementation steps:

1. Switch prompt call sites from `render(...)` to `render_with_meta(...)` where practical.
2. Emit prompt metadata on spans:
   - `prompt.id`
   - `prompt.version`
   - `prompt.task_type`
   - rendered prompt length
3. Replace generic span names where useful with stable operation names such as:
   - `llm.chat.respond`
   - `llm.chat.social`
   - `llm.practice.quiz.generate`
   - `llm.grading.level_up`
   - `llm.graph.extract`
   - `llm.graph.disambiguate`
4. Emit retry attempt metadata for regenerated prompts.

What stays the same:

- Prompt assets and task contracts do not change.
- The repo stays provider-agnostic and prompt rendering stays deterministic.

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_practice_prompts.py`
- targeted tests for updated prompt call sites

Exit criteria:

- Phoenix list view clearly separates tutor, grading, practice, graph, and document LLM calls without relying on manual trace inspection.

### OBS-4. Slice 4: Domain span normalization

Purpose:

- Make non-LLM spans useful in Phoenix instead of empty-looking placeholders.

Root problem:

- Root chain spans often omit session/user/concept/document identifiers and meaningful input/output summaries.
- Retrieval is not traced at all.

Files involved:

- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/chat/retrieval_context.py`
- `domain/retrieval/hybrid_retriever.py`
- `domain/retrieval/vector_retriever.py`
- `domain/retrieval/fts_retriever.py`
- `domain/learning/practice.py`
- `domain/learning/quiz_flow.py`
- `domain/ingestion/post_ingest.py`

Implementation steps:

1. Add consistent correlation fields to root spans where available:
   - `request_id`
   - `workspace_id`
   - `session.id`
   - `user.id`
   - `concept_id`
   - `quiz_id`
   - `document_id`
2. Normalize chain span inputs/outputs so Phoenix list columns are populated with compact summaries rather than `--`.
3. Add retrieval spans with `RETRIEVER` kind and lightweight `retrieval.documents` metadata.
4. Add a root span for streaming chat that mirrors blocking chat.
5. Add a parent post-ingest span so document summary and graph extraction group under one trace.

What stays the same:

- Retrieval ranking behavior and business logic stay unchanged.
- Routes remain thin.

Verification:

- `PYTHONPATH=. pytest -q tests/api/test_chat_respond.py tests/api/test_g3_stream.py`
- targeted retrieval / practice tests

Exit criteria:

- Chat traces show search, retrieval, respond, and persist stages with correlated IDs.
- Practice and grading root spans are readable from the Phoenix list view without opening every trace.

### OBS-5. Slice 5: Graph deep tracing

Purpose:

- Make resolver and gardener traces explainable enough to debug budget usage, clustering, and merge decisions.

Root problem:

- Graph traces are too coarse.
- Budget usage and hard stops are emitted only as logs.
- The gardener trace detail does not explain why a run did or did not call the LLM.

Files involved:

- `domain/graph/pipeline.py`
- `domain/graph/resolver.py`
- `domain/graph/resolver_decision.py`
- `domain/graph/gardener.py`
- `tests/domain/test_graph_resolver.py`
- `tests/domain/test_graph_gardener.py`

Implementation steps:

1. Add chunk-level child spans or span events for extraction, candidate generation, and disambiguation.
2. Emit cluster-level summary events for gardener runs:
   - cluster size
   - candidate IDs
   - decision taken
   - confidence
   - skip reason
3. Surface budget hard-stop reasons as Phoenix events and root-span summary attributes.
4. Add output summaries on graph root spans:
   - chunks processed
   - llm calls
   - canonical merges created/applied
   - budget stop flags

What stays the same:

- Resolver and gardener budget rules remain the same.
- No unbounded scans or loops are introduced.

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_graph_resolver.py`
- `PYTHONPATH=. pytest -q tests/domain/test_graph_gardener.py`

Exit criteria:

- A Phoenix gardener trace explains whether LLM work happened, what the budgets were, and why any cluster was skipped or stopped.

### OBS-6. Slice 6: Docs and regression hardening

Purpose:

- Align docs with reality and lock the new observability contract in tests.

Root problem:

- `docs/OBSERVABILITY.md` currently promises behavior the code does not yet provide.
- There is no operator-focused Phoenix checklist for navigating the new spans.

Files involved:

- `docs/OBSERVABILITY.md`
- `docs/PLAN.md` (only if the overlap with S45 needs consolidation)
- updated test files from earlier slices

Implementation steps:

1. Rewrite `docs/OBSERVABILITY.md` to match the implemented span tree, event model, env flags, and token accounting rules.
2. Add Phoenix operator guidance:
   - suggested filters
   - what each major span name means
   - how to distinguish provider usage vs estimated usage
   - what content is intentionally omitted in safe mode
3. Add or extend tests that lock:
   - HTTP root span presence
   - streaming LLM span presence
   - span event emission
   - prompt metadata emission
   - graph budget stop visibility

What stays the same:

- Phoenix remains optional and dev-friendly.
- User-facing assistant responses do not start exposing raw prompt bodies by default.

Verification:

- `PYTHONPATH=. pytest -q tests/core/test_observability.py tests/adapters/test_graph_llm_observability.py tests/domain/test_graph_gardener.py tests/domain/test_graph_resolver.py tests/api/test_middleware.py tests/api/test_g3_stream.py tests/api/test_chat_respond.py`

Exit criteria:

- Docs match the implemented behavior.
- Regressions in trace structure and token accounting are covered by tests.

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `OBS-1` Trace foundation
2. `OBS-2` LLM tracing parity
3. `OBS-3` Prompt identity and call separation
4. `OBS-4` Domain span normalization
5. `OBS-5` Graph deep tracing
6. `OBS-6` Docs and regression hardening

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Block Template

For every completed slice, include this exact structure in the working report or PR note:

```text
Verification Block - <slice-id>

Root cause
- <what made this area hard to maintain?>

Files changed
- <file list>

What changed
- <short description of the refactor moves>

Commands run
- <tests / typecheck / lint commands>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
PYTHONPATH=. pytest -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
```

Run these additionally when relevant:

```bash
ruff check .
```

Slice-specific emphasis:

- `OBS-1`
  - `PYTHONPATH=. pytest -q tests/core/test_observability.py`
  - `PYTHONPATH=. pytest -q tests/api/test_middleware.py`
- `OBS-2`
  - `PYTHONPATH=. pytest -q tests/adapters/test_graph_llm_observability.py`
  - `PYTHONPATH=. pytest -q tests/adapters/test_g2_streaming.py tests/domain/test_g5_trace.py`
- `OBS-3`
  - prompt-family unit tests for every migrated `render_with_meta()` call site
- `OBS-4`
  - `PYTHONPATH=. pytest -q tests/api/test_chat_respond.py tests/api/test_g3_stream.py`
- `OBS-5`
  - `PYTHONPATH=. pytest -q tests/domain/test_graph_resolver.py tests/domain/test_graph_gardener.py`
- `OBS-6`
  - rerun the targeted observability matrix plus docs review

Manual smoke checklist:

1. Start Phoenix locally and confirm traces now root under `http.request`.
2. Trigger blocking chat, streaming chat, practice generation, quiz grading, and a gardener run; verify each surface shows meaningful input/output summaries plus child LLM spans.
3. Open a gardener trace and confirm the Events tab explains budget usage and any hard-stop reason.
4. Open a streaming tutor trace and confirm tokens and prompt metadata appear in Phoenix.
5. Confirm safe mode still omits full content when the full-content env gate is off.

## What Not To Do

Do not do the following during the remaining refactor:

- do not move business logic into routes to make tracing easier
- do not stuff arbitrarily large raw payloads into standard span attributes without a size / storage policy
- do not report estimated tokens as if they were provider-authoritative
- do not remove existing log emission until Phoenix-visible events fully replace the debugging value
- do not mix unrelated prompt, UI, or product changes into these slices

## Removal Ledger

Append removal entries here during implementation.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If a generated refactor plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the remaining implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/OBSERVABILITY_REFACTOR_PLAN.md now. This file is the source of truth.
You MUST implement observability slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, helper, env var, docs surface, or compatibility shim, you MUST document the removal in docs/OBSERVABILITY_REFACTOR_PLAN.md using the Removal Entry Template.
For every removal, include:
Removed artifact
Reason for removal
Replacement
Reverse path
Compatibility impact
Verification

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade/shim instead of deleting immediately.
- Do not delete public contracts without a compatibility note and rollback path.
- Do not claim the removal is complete until the replacement behavior is verified.

After every 2 slices OR if your context is compacted/summarized, re-open docs/OBSERVABILITY_REFACTOR_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/OBSERVABILITY_REFACTOR_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/OBSERVABILITY_REFACTOR_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/OBSERVABILITY_REFACTOR_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
