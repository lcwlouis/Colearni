# Observability Refactor Snapshot

Date: 2026-03-01

This snapshot records the current observability state before the Phoenix overhaul plan begins.

## Confirmed current behavior

- `core/observability.py` emits structured JSON logs via `emit_event()`, but it does not attach those events to the active trace span.
- `core/observability.py` creates spans via `start_span()`, but it does not set success/error status or record exceptions on the span.
- `core/observability.py` truncates recorded span content to 4096 chars, so full prompts/responses are not preserved even when content recording is enabled.
- `apps/api/middleware.py` propagates `request_id`, but it does not create the documented `http.request` root span.
- `adapters/llm/providers.py` creates non-streaming `llm.call` spans, but streaming tutor generation does not create an LLM span or emit LLM events.
- `domain/chat/stream.py` does not open a chat root span or observation context, so the streaming path is largely invisible to Phoenix.
- `domain/chat/retrieval_context.py` and the retriever implementations do not emit retriever spans, so Phoenix cannot show search-stage internals.
- `domain/learning/practice.py`, `domain/learning/quiz_flow.py`, `domain/graph/pipeline.py`, and `domain/graph/gardener.py` create chain spans but often omit useful input/output summaries, prompt IDs, and operation-specific metadata.
- `domain/ingestion/post_ingest.py` performs background summary generation without its own parent span, so those LLM calls are poorly grouped.
- `core/prompting/registry.py` already exposes `render_with_meta()`, but no runtime code uses it for observability metadata.

## Verification captured during investigation

- `pytest -q` from repo root fails during collection because the shell environment does not expose the repo packages on `PYTHONPATH`.
- `PYTHONPATH=. pytest -q tests/core/test_observability.py tests/adapters/test_graph_llm_observability.py` passed.
- `PYTHONPATH=. pytest -q tests/domain/test_graph_gardener.py tests/domain/test_graph_resolver.py` passed.
- `PYTHONPATH=. pytest -q tests/api/test_middleware.py tests/api/test_g3_stream.py tests/api/test_chat_respond.py` passed.

## Phoenix pain points this snapshot explains

- Many traces appear as root-level `CHAIN` spans with `UNSET` status because HTTP roots are missing and span status is never set.
- The Phoenix Events tab is empty because `emit_event()` only logs; it does not call `span.add_event(...)`.
- Root spans often show `0` cumulative tokens because some call paths never emit child LLM spans and some provider responses may still lack usage metadata.
- The UI is hard to navigate because most LLM spans are named `llm.call` and prompt metadata such as prompt ID, task family, and retry stage are not attached.
- Full prompt and response bodies cannot be audited in Phoenix today because recorded content is truncated to 4096 chars.
