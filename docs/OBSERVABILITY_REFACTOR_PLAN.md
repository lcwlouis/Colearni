# Observability Refactor Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `docs/archive/OBSERVABILITY_REFACTOR_PLAN_2026-03-01_pre-overhaul.md`
- `docs/archive/OBSERVABILITY_REFACTOR_PLAN_2026-03-01_pre-phoenix-scope-update.md`

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

The first draft of this plan assumed the main gap was missing traces. That is no longer accurate.

Partial implementation has already landed:

- `emit_event()` now writes to the active span
- streaming LLM spans now exist
- prompt metadata helpers now exist
- coarse retrieval tracing now exists
- `http.request` spans were added in middleware

The latest Phoenix feedback shows a more precise problem:

- Phoenix is receiving low-value infrastructure spans that should stay in logs
- some exported spans still show `unknown` kind
- retrieval visibility is still too coarse to explain vector and graph-derived behavior
- prompt/token visibility is still inconsistent across surfaces

Phoenix should be an AI-debugging surface only. It should explain LLM calls, agent/orchestrator behavior, retriever/RAG behavior, and graph reasoning/maintenance. Generic request/CRUD/listing traffic should remain in logs and correlation metadata only.

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
- `docs/archive/OBSERVABILITY_REFACTOR_PLAN_2026-03-01_pre-phoenix-scope-update.md`
- current repository layout and verification status as of 2026-03-01

## Executive Summary

What is already in good shape:

- OTel export remains optional and env-gated.
- Non-streaming LLM calls already create child spans and capture provider usage when the SDK returns it.
- Streaming LLM calls now emit spans and `llm.usage_source`.
- Prompt assets already expose metadata via `PromptRegistry.render_with_meta()`.
- Coarse retrieval tracing now exists via `retrieval.hybrid`.
- Targeted backend observability tests already exist and are passing when the repo is run with `PYTHONPATH=.`

What is still materially missing:

1. Phoenix export scope is wrong.
   - Generic `http.request` spans now pollute the UI.
   - Non-AI routes such as list/read endpoints should not appear in Phoenix.
   - Request IDs and HTTP metadata belong in logs/context, not Phoenix rows.
2. Span taxonomy is incomplete.
   - Some exported spans still lack an explicit OpenInference kind and show up as `unknown`.
   - There is no test gate that fails when an AI span is exported without `LLM`, `CHAIN`, `AGENT`, `RETRIEVER`, `TOOL`, or `EMBEDDING`.
3. Retrieval transparency is still too coarse.
   - Phoenix can show a merged retrieval span, but not the distinct vector hits, FTS hits, hybrid fusion outcome, or graph-derived bias/context.
   - Retrieved content metadata is not rich enough to explain what the system actually used.
4. Token and prompt auditing are still incomplete.
   - Full prompt/response bodies are still truncated at 4096 chars.
   - Prompt metadata is not yet propagated consistently across all call sites.
   - There is still no explicit story for estimated token counts because estimation has not been implemented.

The remaining work should stay narrow: define the correct Phoenix scope, enforce a kind taxonomy, deepen RAG visibility, and then harden docs/tests so Phoenix becomes a reliable AI debugging tool rather than a noisy infrastructure trace dump.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. Keep FastAPI routes thin. Observability logic belongs in middleware, adapters, or domain helpers, not in routes.
2. Preserve provider-agnostic behavior. Phoenix must remain optional, and OpenAI / LiteLLM paths must share the same observability contract.
3. Phoenix should only receive AI-observability spans:
   - allowed categories: `LLM`, `AGENT`, `CHAIN`, `RETRIEVER`, `TOOL`, `EMBEDDING`
   - disallowed noise: generic request spans, health checks, auth/session CRUD, and other non-AI infrastructure paths
4. Every exported Phoenix span must have an explicit OpenInference kind. `unknown` kind is a verification failure unless a slice explicitly documents why it is temporary.
5. Full prompt/response capture must be explicitly gated by env and treated as dev-only / trusted-environment behavior by default.
6. Retrieval payload capture must be bounded:
   - IDs, scores, methods, and short previews by default
   - longer retrieved excerpts only behind the content gate
7. Do not silently invent token counts. If estimated usage is added, it must be labeled as estimated and distinguishable from provider-reported usage.
8. Preserve graph and agent budget semantics; observability must expose budget stops, not change them.
9. Tests are required for new behavior, especially for span filtering, kind coverage, streaming, retrieval transparency, and token accounting fallbacks.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `BASE-1` Optional OTLP export wiring and content-recording feature flag already exist.
- `BASE-2` Non-streaming LLM adapter spans already capture provider/model plus usage fields when the SDK returns them.
- `BASE-3` Prompt assets already expose typed metadata via `PromptRegistry.render_with_meta()`.
- `BASE-4` Streaming LLM spans and `llm.usage_source` support are now in place, though still not fully aligned with the final scope.
- `BASE-5` Targeted backend observability tests are present and currently passing with `PYTHONPATH=.`

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `OBS-1` Phoenix scope and span taxonomy foundation
- `OBS-2` LLM tracing parity: streaming, token accounting, and content-capture policy
- `OBS-3` Prompt identity and call separation metadata
- `OBS-4` RAG retrieval transparency: vector, FTS, hybrid, and graph-derived context
- `OBS-5` Domain and graph maintenance span normalization
- `OBS-6` Docs, regression coverage, and Phoenix operator guidance

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. `emit_event()` should remain as the single app-facing API, but internally it must write both to logs and to the active span as a real trace event.
2. We will improve Phoenix navigation by raising signal and by excluding non-AI noise. The UI problem is both low-signal spans and the wrong spans.
3. Generic HTTP request spans do not belong in Phoenix for this repo. Request IDs and HTTP metadata stay in structured logs and observation context only.
4. Full prompt / response capture will remain env-gated. The default safe behavior stays metadata-first.
5. Prompt identity must come from the prompt asset system (`prompt_id`, `version`, `task_type`) instead of ad-hoc string tags.
6. Token accounting should prefer provider usage, optionally fall back to explicit estimates, and always expose the usage source.
7. Streaming chat must have observability parity with blocking chat; otherwise Phoenix will always under-report tutor traffic.
8. Retrieval observability must be source-aware:
   - vector retrieval
   - FTS retrieval
   - hybrid fusion
   - graph-derived retrieval/bias/context

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
| `core/observability.py` | 426 | Owns span lifecycle, event emission, token extraction, redaction, truncation, and kind-setting helpers. |
| `apps/api/middleware.py` | 37 | Currently exports `http.request` spans that clutter Phoenix and show `unknown` kind. |
| `adapters/llm/providers.py` | 598 | All non-streaming and streaming provider observability behavior converges here. |
| `domain/chat/respond.py` | 336 | Blocking chat has a root span but is missing richer prompt/debug fields and final normalized summaries. |
| `domain/chat/stream.py` | 374 | Streaming chat now has a root span, but metadata parity and prompt identity still need completion. |
| `domain/chat/retrieval_context.py` | 128 | Retrieval is now traced coarsely, but vector/FTS/graph-derived details are still opaque. |
| `domain/retrieval/hybrid_retriever.py` | 86 | Fusion logic currently has no direct Phoenix visibility. |
| `domain/retrieval/vector_retriever.py` | 58 | Vector hit lists and score ordering are not separately exposed. |
| `domain/retrieval/fts_retriever.py` | 31 | FTS hit lists and ranks are not separately exposed. |
| `domain/learning/practice.py` | 744 | Practice generation spans are present but mostly empty-looking from the Phoenix list view. |
| `domain/learning/quiz_flow.py` | 672 | Grading emits events, but root spans still lack strong summaries. |
| `domain/graph/gardener.py` | 547 | Budget usage is visible, but trace detail still does not fully explain cluster decisions or hard stops. |
| `domain/graph/pipeline.py` | 170 | Resolver chunk spans exist, but at least one child span lacks explicit kind coverage and detailed summaries. |
| `domain/ingestion/post_ingest.py` | 190 | Background summary generation is not yet grouped and summarized at the right level. |
| `docs/OBSERVABILITY.md` | 248 | Documentation overstates current behavior and must be reconciled with the actual code. |

## Remaining Work Overview

### 1. Phoenix scope is polluted

Phoenix is currently showing infrastructure-level `http.request` spans that add almost no debugging value and crowd out the AI traces you actually care about.

### 2. Span taxonomy is not enforced

Some exported spans still show `unknown` kind because the plan does not yet require kind coverage as a first-class correctness condition.

### 3. Retrieval visibility is too shallow

The current retrieval span can show a merged result list, but it cannot explain which vector hits existed, which keyword hits existed, how hybrid fusion ranked them, or what graph-derived signals changed the final context.

### 4. Token and prompt visibility are still partial

Provider usage is better than before, but full content is still truncated, metadata is not fully propagated, and there is still no explicit story for estimated token counts.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green targeted tests before the next slice starts.

### OBS-1. Slice 1: Phoenix scope and span taxonomy foundation

Purpose:

- Make Phoenix show only AI-relevant traces, and ensure every exported span has a non-unknown OpenInference kind.

Root problem:

- Phoenix is currently polluted by `http.request` spans.
- Some exported spans still lack explicit kind coverage and appear as `unknown`.
- The current plan has no allowlist defining what belongs in Phoenix versus logs.

Files involved:

- `core/observability.py`
- `apps/api/middleware.py`
- `domain/graph/pipeline.py`
- `tests/core/test_observability.py`
- `tests/api/test_middleware.py`

Implementation steps:

1. Define an explicit Phoenix export policy:
   - export only AI spans
   - keep request IDs and HTTP metadata in logs/context only
2. Remove generic `http.request` span export from middleware while preserving request logging and correlation IDs.
3. Introduce or standardize a helper/facade so exported spans receive their OpenInference kind at creation time rather than relying on follow-up calls.
4. Audit current exported spans and eliminate `unknown` kinds on AI paths.
5. Preserve current log emission behavior so existing log-based workflows keep working.

What stays the same:

- Observability remains env-gated.
- `emit_event()` remains the public helper used by domain code.
- Middleware still propagates `request_id` for logs and correlation.

Verification:

- `PYTHONPATH=. pytest -q tests/core/test_observability.py`
- `PYTHONPATH=. pytest -q tests/api/test_middleware.py`

Exit criteria:

- Non-AI endpoints such as health/session listing do not create Phoenix spans.
- Exported AI spans no longer show `unknown` kind.

### OBS-2. Slice 2: LLM tracing parity

Purpose:

- Ensure every real LLM API call, including streaming tutor calls, produces one rich child LLM span with token accounting.

Root problem:

- Non-streaming and streaming observability are closer now, but metadata parity is still incomplete.
- Some traces still show zero cumulative tokens when usage is missing and no estimation path exists.
- Full prompt/response capture still truncates at 4096 chars with no fallback story.

Files involved:

- `adapters/llm/providers.py`
- `core/observability.py`
- `core/contracts.py`
- `tests/adapters/test_graph_llm_observability.py`
- `tests/adapters/test_g2_streaming.py`
- `tests/domain/test_g5_trace.py`

Implementation steps:

1. Introduce a single helper path for sync + streaming LLM span creation.
2. Make prompt/token metadata parity identical across blocking and streaming paths.
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

- Most LLM spans are still hard to distinguish at a glance.
- Prompt IDs and versions exist in the repo but are not emitted consistently on all important paths.

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
4. Propagate prompt metadata to streaming paths as well as blocking paths.
5. Emit retry attempt metadata for regenerated prompts.

What stays the same:

- Prompt assets and task contracts do not change.
- The repo stays provider-agnostic and prompt rendering stays deterministic.

Verification:

- `PYTHONPATH=. pytest -q tests/domain/test_practice_prompts.py`
- targeted prompt-family tests for updated `render_with_meta()` call sites

Exit criteria:

- Phoenix list view clearly separates tutor, grading, practice, graph, and document LLM calls without relying on manual trace inspection.

### OBS-4. Slice 4: RAG retrieval transparency

Purpose:

- Make Phoenix explain what the RAG stack actually retrieved from vector, keyword, hybrid, and graph-derived sources.

Root problem:

- Current retrieval visibility is too coarse.
- There is no separate Phoenix view of:
  - vector top-k hits
  - FTS hits
  - hybrid fusion decisions
  - graph-derived/provenance-based bias or context
- Retrieved content metadata is too sparse to explain why the final evidence set looks the way it does.

Files involved:

- `domain/chat/retrieval_context.py`
- `domain/retrieval/hybrid_retriever.py`
- `domain/retrieval/vector_retriever.py`
- `domain/retrieval/fts_retriever.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- new or updated retrieval observability tests

Implementation steps:

1. Split retrieval into distinct `RETRIEVER` spans/events:
   - `retrieval.vector.search`
   - `retrieval.fts.search`
   - `retrieval.hybrid.fuse`
   - `retrieval.graph.bias` or equivalent graph-derived context span
2. Attach bounded retrieval metadata for each stage:
   - `document_id`
   - `chunk_id`
   - score/rank
   - retrieval source/method
   - short content preview when the content gate allows it
3. Surface graph-derived retrieval/context signals:
   - active concept used for biasing
   - linked chunk IDs from provenance
   - adjacency/graph context injected into downstream prompts
   - applied boost or selection reason
4. Keep `retrieval.documents` lightweight enough for Phoenix while still useful for debugging.
5. Ensure final evidence selection can be traced back to the source retriever stages.

What stays the same:

- Retrieval ranking behavior and business logic stay unchanged.
- Routes remain thin.

Verification:

- `PYTHONPATH=. pytest -q tests/api/test_chat_respond.py tests/api/test_g3_stream.py`
- targeted retrieval observability tests covering vector, FTS, hybrid, and graph-derived spans

Exit criteria:

- Phoenix shows what vector retrieval returned, what keyword retrieval returned, how hybrid fusion ranked them, and what graph-derived context changed the final set.
- Retrieval traces are useful without opening application logs.

### OBS-5. Slice 5: Domain and graph maintenance span normalization

Purpose:

- Make non-LLM, non-retrieval AI spans useful in Phoenix instead of empty-looking placeholders, especially for graph maintenance and grading flows.

Root problem:

- Root chain spans often omit meaningful input/output summaries and correlated IDs.
- Graph traces are too coarse.
- Budget usage and hard stops are emitted only as logs.
- The gardener trace detail does not explain why a run did or did not call the LLM.

Files involved:

- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `domain/learning/practice.py`
- `domain/learning/quiz_flow.py`
- `domain/ingestion/post_ingest.py`
- `domain/graph/pipeline.py`
- `domain/graph/resolver.py`
- `domain/graph/resolver_decision.py`
- `domain/graph/gardener.py`
- `tests/domain/test_graph_resolver.py`
- `tests/domain/test_graph_gardener.py`

Implementation steps:

1. Add consistent correlation fields to domain root spans where available:
   - `workspace_id`
   - `session.id`
   - `user.id`
   - `concept_id`
   - `quiz_id`
   - `document_id`
2. Normalize chain span inputs/outputs so Phoenix list columns are populated with compact summaries rather than `--`.
3. Add chunk-level child spans or span events for extraction, candidate generation, and disambiguation.
4. Emit cluster-level summary events for gardener runs:
   - cluster size
   - candidate IDs
   - decision taken
   - confidence
   - skip reason
5. Surface budget hard-stop reasons as Phoenix events and root-span summary attributes.
6. Add output summaries on graph root spans:
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
- targeted practice / grading span tests

Exit criteria:

- Practice, grading, ingest, and graph-maintenance spans are readable from the Phoenix list view without opening every trace.
- A Phoenix gardener trace explains whether LLM work happened, what the budgets were, and why any cluster was skipped or stopped.

### OBS-6. Slice 6: Docs and regression hardening

Purpose:

- Align docs with reality and lock the new observability contract in tests.

Root problem:

- `docs/OBSERVABILITY.md` currently promises behavior the code does not yet provide.
- There is no operator-focused Phoenix checklist for navigating the new AI-only span surface.

Files involved:

- `docs/OBSERVABILITY.md`
- `docs/PLAN.md` (only if overlap with S45 needs consolidation)
- updated test files from earlier slices

Implementation steps:

1. Rewrite `docs/OBSERVABILITY.md` to match the implemented span taxonomy, export scope, event model, env flags, and token accounting rules.
2. Add Phoenix operator guidance:
   - which routes should never appear
   - what each major span name means
   - how to distinguish provider usage vs estimated usage
   - how to read retrieval.vector / retrieval.fts / retrieval.hybrid / retrieval.graph.*
   - what content is intentionally omitted in safe mode
3. Add or extend tests that lock:
   - non-AI endpoint exclusion
   - no exported AI spans with `unknown` kind
   - streaming LLM span presence
   - prompt metadata emission
   - retrieval stage visibility
   - graph budget stop visibility

What stays the same:

- Phoenix remains optional and dev-friendly.
- User-facing assistant responses do not start exposing raw prompt bodies by default.

Verification:

- `PYTHONPATH=. pytest -q tests/core/test_observability.py tests/adapters/test_graph_llm_observability.py tests/domain/test_graph_gardener.py tests/domain/test_graph_resolver.py tests/api/test_middleware.py tests/api/test_g3_stream.py tests/api/test_chat_respond.py`

Exit criteria:

- Docs match the implemented behavior.
- Regressions in trace scope, kind coverage, retrieval transparency, and token accounting are covered by tests.

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `OBS-1` Phoenix scope and span taxonomy foundation
2. `OBS-2` LLM tracing parity
3. `OBS-3` Prompt identity and call separation
4. `OBS-4` RAG retrieval transparency
5. `OBS-5` Domain and graph maintenance span normalization
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
  - exported AI spans have no `unknown` kind
- `OBS-2`
  - `PYTHONPATH=. pytest -q tests/adapters/test_graph_llm_observability.py`
  - `PYTHONPATH=. pytest -q tests/adapters/test_g2_streaming.py tests/domain/test_g5_trace.py`
- `OBS-3`
  - prompt-family unit tests for every migrated `render_with_meta()` call site
- `OBS-4`
  - `PYTHONPATH=. pytest -q tests/api/test_chat_respond.py tests/api/test_g3_stream.py`
  - targeted retrieval observability tests
- `OBS-5`
  - `PYTHONPATH=. pytest -q tests/domain/test_graph_resolver.py tests/domain/test_graph_gardener.py`
- `OBS-6`
  - rerun the targeted observability matrix plus docs review

Manual smoke checklist:

1. Start Phoenix locally and confirm generic routes such as `/healthz` or `/chat/sessions` do not create Phoenix rows.
2. Trigger blocking chat, streaming chat, practice generation, quiz grading, and a gardener run; verify each surface shows meaningful AI traces only.
3. Open a retrieval trace and confirm vector hits, keyword hits, hybrid fusion, and graph-derived bias/context are all inspectable.
4. Open a gardener trace and confirm the Events tab explains budget usage and any hard-stop reason.
5. Open a streaming tutor trace and confirm tokens, prompt metadata, and non-unknown kinds appear in Phoenix.
6. Confirm safe mode still omits full content when the full-content env gate is off.

## What Not To Do

Do not do the following during the remaining refactor:

- do not move business logic into routes to make tracing easier
- do not stuff arbitrarily large raw payloads into standard span attributes without a size / storage policy
- do not report estimated tokens as if they were provider-authoritative
- do not remove existing log emission until Phoenix-visible events fully replace the debugging value
- do not export generic HTTP / CRUD spans to Phoenix just to create a fake root tree
- do not mix unrelated prompt, UI, or product changes into these slices

## Removal Ledger

Append removal entries here during implementation.

```text
Removal Entry - OBS-1

Removed artifact
- http.request span creation in apps/api/middleware.py (start_span("http.request", ...))
- opentelemetry trace import in middleware
- test_http_request_root_span_created in tests/api/test_middleware.py
- test_http_request_span_carries_request_id in tests/api/test_middleware.py

Reason for removal
- Generic HTTP request spans pollute Phoenix with non-AI infrastructure noise.
  Health checks, session listings, and other CRUD routes were appearing as
  Phoenix trace rows, crowding out the AI-debugging traces that matter.

Replacement
- Middleware still propagates request_id via observation_context and logs.
- Domain spans (chat.respond, chat.stream, retrieval.hybrid, etc.) serve as
  trace roots for AI-relevant paths.
- New test_no_http_request_span_exported asserts spans are NOT created.

Reverse path
- git revert the OBS-1 commit to restore http.request spans
- or re-add start_span("http.request", ...) block in middleware dispatch()

Compatibility impact
- internal only; no public API or env var changes
- Phoenix users will no longer see http.request as trace root; AI spans
  become their own roots

Verification
- PYTHONPATH=. pytest -q tests/api/test_middleware.py → 6 passed
- PYTHONPATH=. pytest -q → 521 passed (1 pre-existing failure)
```

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
