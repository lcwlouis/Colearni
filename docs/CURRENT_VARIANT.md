# Current Implementation Variant

## Purpose

This file records the current local-ready tutor/quiz implementation details that have moved ahead of the original phase wording.

Read this after `docs/REBUILD_PLAN.md` before changing tutor, quiz, or adjacent planning docs.

If this file conflicts with an older phase description, follow this file and update the stale doc in the same change.

## Tutor Runtime

- Tutor answer budget is controlled by `LLM_TUTOR_MAX_TOKENS`, separate from provider reasoning budgets and headroom.
- The tutor streams public SSE events for `status`, `thinking`, `tool_call`, `tool_result`, `mode`, `token`, `done`, and `error`.
- `mode` is guaranteed before visible `token` events, but gated-mode `status` and `tool_*` events may appear first.
- `tool_call` and `tool_result` describe the internal instruction-tool step; the later `mode` event is the final visible tutor mode.
- Public `tool_result` payloads are sanitized previews only. Raw internal tutor instructions must not be exposed.
- Hidden tool-call/tool-result turns are persisted for prompt replay, but the public conversation history still returns only visible user/assistant messages.
- Assistant turns persist both full `reasoning` text and ordered public `reasoning_parts`.
- `get_tutor_instructions` is wrapped by the normalized provider-tool schema internally, while the tutor still emits/persists the existing tagged compatibility representation for public SSE and replay stability.
- If a reasoning-enabled call ends with no visible answer, the tutor retries once with `thinking=False` and emits `retrying_without_thinking` before failing.
- Automatic conversation summarization is still deferred. Prompt context currently uses the latest 10 visible turns plus any tool turns within that same retained window.

## Tutor UI

- The tutor remains concept-scoped inside the concept side panel. Do not treat `AssistantModal` as the current MVP surface.
- The frontend uses `@assistant-ui/react` with a custom `LocalRuntime` adapter.
- Reopened chats rehydrate from `reasoning_parts` first and only fall back to flattened `reasoning` when structured parts are absent.
- The learner-facing reasoning UI defaults to a compact summary. Full trace is opt-in via the `Reasoning` toggle.
- The reasoning view preference is stored in `localStorage` as `colearni.reasoningView`.
- Current public reasoning part kinds are `status`, `thinking`, `tool_call`, and `tool_result`.
- True per-message source/citation parts and quote rendering are still deferred. The current tutor header only shows concept-level source chips.

## Quiz Variant

- Quiz cards are backend-owned and persisted in `quiz_drafts`, keyed by `(concept_id, quiz_type)`.
- Reopening an ungraded level-up or practice quiz returns the existing draft across devices/sessions.
- Clients can request a fresh card with `force_new: true`. The current UI uses this for explicit level-up retry.
- Quiz questions are mixed-format: `multiple_choice`, `short_answer`, and `long_answer`.
- Questions also carry `difficulty`: `light`, `standard`, or `challenge`.
- `multiple_choice` questions include 3-4 options. `short_answer` and `long_answer` omit `options`.
- Older persisted `explain` / `apply` / `compare` question snapshots are normalized to `long_answer` on read.
- Grading clears the matching backend draft after the attempt is stored.

## Duplicate-Request Protection

- The frontend `QuizPanel` dedupes in-flight generation requests so StrictMode/dev effect replay does not create duplicate generation calls.
- The backend is the real safety boundary: PostgreSQL `pg_advisory_xact_lock` serializes draft creation per `(concept_id, quiz_type)`.
- If duplicate inserts still race, the service rolls back, reloads the existing draft, and returns it.

## Migration Rule

- Alembic revision ids must fit `alembic_version.version_num` (`VARCHAR(32)`).
- Current example:
  - file: `backend/alembic/versions/0007_conversation_reasoning_parts.py`
  - revision: `0007_reasoning_parts`

## Deferred Work

- Full provider-native LLM-invoked retrieval tool execution. Retrieval service functions (get_concept_sources_for_tutor, get_graph_neighbourhood, search_sources_by_title) and ProviderToolDefinition schemas (retrieval_tools.py) are implemented; the LLM multi-turn tool calling loop remains deferred.
- open_source_chunk: deferred until source parsing and chunk records exist.
- Full-text and vector search: deferred until the parser pipeline produces chunks and embeddings.
- Automatic conversation summarization.
- True per-message citation/source parts and quotes.
- Global cross-Trail assistant surfaces.

## Update Rule

When implementation changes any item above, update this file and the affected contract docs in the same change.
