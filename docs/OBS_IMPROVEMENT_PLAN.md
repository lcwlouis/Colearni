# Colearni — Observability Improvement Plan

Last updated: 2026-03-05

Parent plan: `docs/ARCHITECTURE.md` (Observability section)

Archive snapshots:
- none yet

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template (inherited from master)
5. removal entry template (inherited from master)
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (template in master plan).
5. If implementation uncovers a behavior change risk, STOP and update this plan and the master plan before widening scope.
6. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

Colearni uses OpenTelemetry with OpenInference semantic conventions to export traces to
Arize Phoenix. A thorough audit of the current implementation uncovered **seven categories
of issues** ranging from spec-non-compliant message formatting to broken span nesting in
the streaming path. These issues manifest as messy, hard-to-read Phoenix traces with
orphaned spans, missing parent-child relationships, and incomplete metadata.

This plan systematically fixes every identified issue in priority order. Each slice is
designed to be independently verifiable and produce a clean diff suitable for code review.

The root problems are:
1. **Broken span hierarchy in streaming** — `create_span()` doesn't set itself as OTel
   current context, so all child spans (retrieval, LLM) in the streaming path become
   orphaned root spans instead of nesting under `chat.stream`.
2. **Non-compliant message format** — LLM messages stored as a single JSON string instead
   of OpenInference's required flattened indexed attributes (`llm.input_messages.0.message.role`).
3. **Silent error swallowing** — Several domain spans catch exceptions without setting
   span ERROR status or recording exceptions, making failures invisible in Phoenix.
4. **Missing OpenInference attributes** — Token cache details, reasoning tokens, `llm.system`,
   `llm.provider`, and document-level attributes don't follow the spec.
5. **Documentation/code drift** — `_PREVIEW_CHARS` is 65536 but docs say 256.

## Inputs Used

- `docs/OBSERVABILITY.md` (current observability documentation)
- `docs/ARCHITECTURE.md` (system architecture, observability section)
- `core/observability.py` (observability module — 600 lines)
- `adapters/llm/providers.py` (LLM adapter with tracing)
- `domain/chat/stream.py`, `domain/chat/respond.py` (chat orchestration)
- `domain/learning/quiz_flow.py`, `domain/learning/practice.py` (learning paths)
- `domain/graph/pipeline.py`, `domain/graph/gardener.py` (graph operations)
- `domain/retrieval/hybrid_retriever.py`, `vector_retriever.py`, `fts_retriever.py`
- `scripts/phoenix_trace_audit.py` (existing audit tooling)
- OpenInference Semantic Conventions spec (https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md)
- Phoenix Manual Instrumentation docs (https://docs.arize.com/phoenix/tracing/how-to-tracing/setup-tracing/instrument)
- OpenInference Traces spec (https://github.com/Arize-ai/openinference/blob/main/spec/traces.md)

## Executive Summary

What works today:
- All span kinds (LLM, CHAIN, RETRIEVER) are correctly assigned and exported to Phoenix
- `_AIOnlySpanExporter` correctly filters non-AI spans from Phoenix
- Token usage extraction handles OpenAI/Anthropic/LiteLLM provider variance
- Content recording toggle (`APP_OBSERVABILITY_RECORD_CONTENT`) works correctly
- Event emission via `emit_event()` attaches domain events to active spans
- Non-streaming chat path (`chat.respond`) has correct span nesting via `start_span()`
- Retrieval pipeline spans are excellently implemented (reference quality)
- Graph resolver/gardener spans have rich output summaries
- Structured event emission for budget tracking, grading, and LLM calls
- Privacy-aware content capture with preview/length always available

What this track fixes:
1. **OBS.1** — Fix streaming span nesting (create_span → set current context for children)
2. **OBS.2** — Fix error handling gaps (respond.py, quiz_flow.py, practice.py)
3. **OBS.3** — Adopt OpenInference flattened message format for LLM spans
4. **OBS.4** — Add missing OpenInference attributes (llm.system, llm.provider, cache_read, reasoning tokens)
5. **OBS.5** — Fix _PREVIEW_CHARS / documentation drift and content_preview behavior
6. **OBS.6** — Remove debug print statements, add missing nested span for gardener disambiguate
7. **OBS.7** — Update docs/OBSERVABILITY.md and phoenix_trace_audit.py for all changes

## Non-Negotiable Constraints

1. All changes must be backward-compatible — observability is opt-in, app must work identically with `APP_OBSERVABILITY_ENABLED=false`
2. No new dependencies unless strictly required (prefer manual implementation over adding `openinference-semantic-conventions` package)
3. `_AIOnlySpanExporter` filter must continue to prevent non-AI spans from reaching Phoenix
4. Thread-safety of `create_span()` for generators must be preserved — do NOT switch streaming to `start_as_current_span()`
5. Content recording gate (`record_content_enabled()`) must remain honored for all message content
6. Existing test suite must continue to pass after each slice
7. Each slice ≤ 400 LOC net diff

## Completed Work (Do Not Reopen Unless Blocked)

- Baseline observability module (`core/observability.py`) with span management
- `_AIOnlySpanExporter` filtering
- Token usage extraction with provider variance handling
- Content recording toggle
- Retrieval pipeline tracing (vector, FTS, hybrid, graph bias)
- Graph resolver/gardener tracing with output summaries
- Phoenix audit script (`scripts/phoenix_trace_audit.py`)
- `docs/OBSERVABILITY.md` initial version

## Remaining Slice IDs

- `OBS.1` Fix streaming span nesting
- `OBS.2` Fix error handling gaps in domain spans
- `OBS.3` Adopt OpenInference flattened message format
- `OBS.4` Add missing OpenInference semantic attributes
- `OBS.5` Fix _PREVIEW_CHARS and content_preview behavior
- `OBS.6` Code quality: debug prints + gardener nested span
- `OBS.7` Update documentation and audit script

## Decision Log

1. **Do NOT add `openinference-semantic-conventions` package** — The project already manually defines the attribute keys. Adding the package would create a mixed approach. Instead, update the manual definitions to match the spec exactly.
2. **Use `trace.set_span_in_context()` for streaming parent propagation** — Rather than switching to `start_as_current_span()` (which breaks generators), explicitly set the created span in context for the synchronous portion where child spans are created, then clean up. This preserves thread-safety while fixing nesting.
3. **Flatten messages inline** — Implement a `_set_flattened_messages()` helper in `core/observability.py` that converts the message list to indexed flattened attributes per the OpenInference spec.
4. **Keep `_PREVIEW_CHARS` at 256** — The 65536 value effectively disables preview truncation. Restore to 256 as documented, which aligns with Phoenix UI column width and the original intent.

## Current Verification Status

- `pytest tests/core/test_observability.py -q`: not yet run for this plan
- `pytest tests/ -q`: not yet run for this plan

Hotspots:

| File | Why it matters |
|---|---|
| `core/observability.py` | Central module — touched by OBS.1, OBS.3, OBS.4, OBS.5 |
| `adapters/llm/providers.py` | LLM tracing — touched by OBS.3, OBS.4 |
| `domain/chat/stream.py` | Streaming root — touched by OBS.1 |
| `domain/chat/respond.py` | Error handling — touched by OBS.2 |
| `domain/learning/quiz_flow.py` | Error handling — touched by OBS.2 |
| `domain/learning/practice.py` | Error handling — touched by OBS.2 |
| `domain/graph/gardener.py` | Missing nested span — touched by OBS.6 |

## Implementation Sequencing

Each slice should end with green tests before the next slice starts.

### OBS.1. Slice 1: Fix Streaming Span Nesting

Purpose:
- Fix the root cause of orphaned spans in Phoenix streaming traces
- Ensure `chat.stream` root span properly parents all child spans (retrieval, LLM)

Root problem:
- `create_span()` calls `tracer.start_span()` which creates a span as child of current context but does NOT set itself as current
- When `domain/chat/stream.py` creates the `chat.stream` root span via `create_span()`, subsequent child operations (retrieval, LLM) don't auto-parent under it
- Result: Phoenix shows separate disconnected root spans instead of a nested trace tree

Files involved:
- `core/observability.py` — add `create_span_as_current()` or modify `create_span()` to accept a `set_current=True` option
- `domain/chat/stream.py` — use the new mechanism to set the stream span as current during child-span-creating operations

Implementation steps:
1. In `core/observability.py`, add a new function `create_span_context(span)` that returns a `trace.set_span_in_context()` context, or add a `set_current` parameter to `create_span()` that uses OTel's `context` API to make the span current for a scoped block
2. The key insight: the synchronous setup portion of `stream.py` (retrieval, evidence planning) runs before the generator yields. Use OTel `Context` to set the span as current during this setup phase
3. For the async generator portion, the span is already created and child spans from `_call_with_observability` or `_stream_with_usage` will use their own `create_span()` — these should capture the parent from the context set in step 2
4. Test with `tests/core/test_observability.py` to verify parent-child linkage

What stays the same:
- `create_span()` API remains available for backward compatibility
- `start_span()` context manager behavior unchanged
- All existing span names and kinds unchanged
- Thread-safety of generator span lifecycle preserved

Verification:
- `pytest tests/core/test_observability.py -q`
- Manual: trigger streaming chat → Phoenix shows `chat.stream` as parent with retrieval and LLM as children

Exit criteria:
- `create_span()` spans can optionally propagate as parent context
- `chat.stream` trace shows proper nesting in Phoenix
- No `ValueError: Token was created in a different Context` errors

### OBS.2. Slice 2: Fix Error Handling Gaps in Domain Spans

Purpose:
- Ensure all domain spans properly set ERROR status and record exceptions on failure
- Make failures visible in Phoenix trace UI (red error markers)

Root problem:
- `domain/chat/respond.py`: No try/except around the main span body — errors propagate but span status stays UNSET
- `domain/learning/quiz_flow.py`: Exceptions caught and re-wrapped but span not updated with ERROR status
- `domain/learning/practice.py`: No error handling around LLM generation — span not marked ERROR on failure

Files involved:
- `domain/chat/respond.py`
- `domain/learning/quiz_flow.py`
- `domain/learning/practice.py`

Implementation steps:
1. **respond.py**: The `start_span` context manager already handles error→ERROR status automatically (lines 208-213 in observability.py). Verify that the `with start_span(...) as span:` block in respond.py actually wraps ALL the code that could fail. If exceptions are caught and re-raised as domain errors OUTSIDE the span block, move the span to encompass the full operation.
2. **quiz_flow.py**: In the grading flow, after catching exceptions (lines ~315-325), add `span.set_status(trace.StatusCode.ERROR, str(exc))` and `span.record_exception(exc)` BEFORE re-raising.
3. **practice.py**: Wrap the LLM generation call in a try/except that records the error on the span. Since `start_span` auto-handles this, ensure the span context manager encompasses the generation code.

What stays the same:
- Span names and kinds unchanged
- Exception types and domain error wrapping unchanged
- All existing attributes and summaries preserved

Verification:
- `pytest tests/ -q` — all existing tests pass
- Manual: trigger a quiz grading failure → Phoenix shows ERROR status on grading span

Exit criteria:
- All domain spans that catch exceptions also record them on the span
- Phoenix error filter shows failures in respond, grading, and practice paths
- No silent error swallowing in traced code paths

### OBS.3. Slice 3: Adopt OpenInference Flattened Message Format

Purpose:
- Comply with OpenInference semantic conventions for LLM message attributes
- Enable Phoenix to render messages with rich per-message UI (role icons, expandable content)

Root problem:
- Currently stores `llm.input_messages` as a single JSON string: `'[{"role": "system", "content": "..."}]'`
- OpenInference spec requires flattened indexed attributes:
  - `llm.input_messages.0.message.role` = "system"
  - `llm.input_messages.0.message.content` = "You are..."
  - `llm.output_messages.0.message.role` = "assistant"
  - `llm.output_messages.0.message.content` = "Hello!"
- Phoenix may parse the JSON string gracefully in some versions, but this is non-standard and fragile

Files involved:
- `core/observability.py` — refactor `set_llm_span_attributes()` to use flattened format
- `tests/core/test_observability.py` — update assertions for new attribute format
- `scripts/phoenix_trace_audit.py` — update `_parse_messages()` to handle flattened format

Implementation steps:
1. Add a helper `_set_flattened_messages(span, messages, prefix)` that iterates over messages and sets indexed attributes:
   ```python
   for i, msg in enumerate(messages):
       span.set_attribute(f"{prefix}.{i}.message.role", msg.get("role", ""))
       content = msg.get("content", "")
       if record_content_enabled():
           span.set_attribute(f"{prefix}.{i}.message.content", content)
   ```
2. Refactor `set_llm_span_attributes()` to use this helper instead of `json.dumps()`
3. Keep the `llm.input_messages.length` and `llm.input_messages.preview` attributes (these are custom but useful)
4. Update output messages similarly: `llm.output_messages.0.message.role` = "assistant", etc.
5. Update `scripts/phoenix_trace_audit.py` `_parse_messages()` to read from flattened attributes
6. Update tests to assert on flattened attribute names

What stays the same:
- `set_input_output()` for `input.value`/`output.value` unchanged
- Content recording gate still honored
- All other span attribute logic unchanged

Verification:
- `pytest tests/core/test_observability.py -q`
- `python scripts/phoenix_trace_audit.py --last-n 5` — no regressions
- Manual: Phoenix LLM span shows individual messages with roles in the Messages tab

Exit criteria:
- All LLM spans use flattened indexed message attributes
- Phoenix renders messages correctly with role labels
- Audit script handles both old (JSON string) and new (flattened) formats for backward compat

### OBS.4. Slice 4: Add Missing OpenInference Semantic Attributes

Purpose:
- Bring span attributes into full compliance with OpenInference semantic conventions
- Add attributes that enable richer Phoenix filtering and cost analysis

Root problem:
- Missing `llm.system` attribute (should be "openai", "anthropic", etc.)
- Missing `llm.provider` attribute for hosting provider
- Token cache stored as `llm.token_count.cached` but spec uses `llm.token_count.prompt_details.cache_read`
- Reasoning tokens extracted but not set on spans as `llm.token_count.completion_details.reasoning`
- Retrieval documents use custom format instead of OpenInference `document.content`/`document.id`/`document.score`
- Missing `session.id` on retrieval spans for cross-span correlation

Files involved:
- `core/observability.py` — add new attribute constants, update `set_llm_span_attributes()`
- `adapters/llm/providers.py` — pass `llm.system` based on provider config
- `domain/retrieval/vector_retriever.py`, `fts_retriever.py`, `hybrid_retriever.py` — use OpenInference document format

Implementation steps:
1. Add attribute constants: `LLM_SYSTEM`, `LLM_PROVIDER`, `LLM_TOKEN_COUNT_CACHE_READ`, `LLM_TOKEN_COUNT_REASONING`
2. In `set_llm_span_attributes()`, set `llm.token_count.prompt_details.cache_read` from `token_cached` (keep old `llm.token_count.cached` for backward compat)
3. In `set_llm_span_attributes()`, accept and set `llm.system` and `llm.provider`
4. In `adapters/llm/providers.py`, pass the provider name as `llm.system` and `llm.provider` (map internal names to spec values)
5. Add reasoning token setting: `llm.token_count.completion_details.reasoning`
6. Update retrieval document summaries to include `document.content`, `document.id`, `document.score` per spec (in addition to existing custom attributes)

What stays the same:
- All existing custom attributes preserved (additive changes only)
- Existing retrieval span structure unchanged (new attributes added alongside)
- Token extraction logic unchanged

Verification:
- `pytest tests/core/test_observability.py -q`
- Manual: Phoenix LLM span shows `llm.system`, token cache details, reasoning tokens

Exit criteria:
- All LLM spans have `llm.system` and `llm.provider`
- Cache tokens use spec-compliant attribute name
- Reasoning tokens visible on spans that use reasoning models

### OBS.5. Slice 5: Fix _PREVIEW_CHARS and content_preview Behavior

Purpose:
- Restore `_PREVIEW_CHARS` to its intended value (256 chars)
- Fix the documentation/code drift
- Ensure preview attributes are actually concise previews, not full content

Root problem:
- `_PREVIEW_CHARS = _MAX_VALUE_CHARS` (65536) — effectively disables preview truncation
- `docs/OBSERVABILITY.md` says "Preview (first 256 chars)" but code uses 65536
- The `content_preview()` function becomes a no-op for most content under 65KB
- This means preview attributes contain full content, defeating the purpose of the safe-mode distinction

Files involved:
- `core/observability.py` — fix `_PREVIEW_CHARS` value
- `docs/OBSERVABILITY.md` — verify documentation matches
- `tests/core/test_observability.py` — add test for preview truncation

Implementation steps:
1. Change `_PREVIEW_CHARS = _MAX_VALUE_CHARS` to `_PREVIEW_CHARS = 256`
2. Verify `content_preview()` now truncates at 256 chars with `"... (len=N)"` suffix
3. Add a test case that verifies truncation behavior at the 256-char boundary
4. Verify `docs/OBSERVABILITY.md` content capture policy table is accurate

What stays the same:
- `_MAX_VALUE_CHARS` (65536) for full attribute value truncation unchanged
- Content recording gate unchanged
- All other preview/summary logic unchanged

Verification:
- `pytest tests/core/test_observability.py -q`
- Manual: LLM span previews show truncated content (256 chars max)

Exit criteria:
- `_PREVIEW_CHARS` is 256
- `content_preview()` truncates correctly
- Documentation matches code

### OBS.6. Slice 6: Code Quality — Debug Prints + Gardener Nested Span

Purpose:
- Remove `print()` debug statements that pollute stdout
- Add missing nested span for gardener batch disambiguation
- Minor code quality improvements

Root problem:
- `domain/chat/stream.py` and `domain/graph/pipeline.py` have bare `print()` statements
- `domain/graph/gardener.py` has `observation_context(operation="graph.disambiguate_batch")` without a matching `start_span()`, creating context without a traceable span

Files involved:
- `domain/chat/stream.py` — remove/replace print() with logging
- `domain/graph/pipeline.py` — remove/replace print() with logging
- `domain/graph/gardener.py` — add `start_span()` around batch disambiguation

Implementation steps:
1. Find and replace all bare `print()` calls in domain/chat/stream.py with `_LOGGER.debug()`
2. Find and replace all bare `print()` calls in domain/graph/pipeline.py with `_LOGGER.debug()`
3. In gardener.py, wrap the batch disambiguation block with `start_span("graph.gardener.disambiguate_batch", kind=SPAN_KIND_CHAIN)`
4. Ensure the new gardener span has appropriate input/output summaries

What stays the same:
- Gardener overall span structure unchanged
- All existing span names unchanged
- Log content unchanged (just using proper logging)

Verification:
- `pytest tests/ -q`
- `grep -rn "print(" domain/ --include="*.py"` — no bare prints remaining in domain layer
- Manual: gardener trace shows disambiguate_batch as a child span

Exit criteria:
- No `print()` statements in domain layer code
- Gardener batch disambiguation has a visible span in Phoenix
- All tests pass

### OBS.7. Slice 7: Update Documentation and Audit Script

Purpose:
- Update `docs/OBSERVABILITY.md` to reflect all changes from OBS.1-6
- Update `scripts/phoenix_trace_audit.py` to validate new attribute formats
- Add verification checklist items for new behavior

Files involved:
- `docs/OBSERVABILITY.md`
- `scripts/phoenix_trace_audit.py`

Implementation steps:
1. Update OBSERVABILITY.md span hierarchy diagram to show correct streaming nesting
2. Update LLM attributes table with new `llm.system`, `llm.provider`, cache_read, reasoning attributes
3. Update content capture policy to reflect correct 256-char preview
4. Add section on OpenInference compliance and message format
5. Update phoenix_trace_audit.py:
   - `_parse_messages()` should read flattened attributes (OBS.3)
   - Add checks for `llm.system` presence
   - Add checks for proper span nesting (parent_id not null for child spans)
6. Update verification checklist with new items

What stays the same:
- Quick start instructions unchanged
- Environment variables unchanged
- Phoenix operator guide structure unchanged

Verification:
- `python scripts/phoenix_trace_audit.py --last-n 10` — passes with new checks
- Manual review of docs/OBSERVABILITY.md for accuracy

Exit criteria:
- Documentation accurately reflects all code changes
- Audit script validates new attribute formats
- No stale documentation remaining

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the master plan's Self-Audit Convergence Protocol may reopen slices in this child plan. The audit uses a **Fresh-Eyes** approach: the auditor treats each slice as if it has NOT been implemented, independently analyzes what should exist, then compares against actual code.

When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. The auditor's fresh-eyes analysis is recorded in the Audit Workspace below
4. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
5. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
6. The reopened slice is **re-implemented from scratch** — do not just patch the previous attempt. Re-read the slice definition, think about what needs to happen, implement it properly, then verify.
7. Only the specific issue identified in the Audit Report is addressed — do not widen scope

**IMPORTANT**: Tests passing is necessary but NOT sufficient for marking a reopened slice as done. The auditor must confirm the logic is correct through code review, not just test results.

## Audit Workspace

This section is initially empty. During the Self-Audit Convergence Protocol, the auditor writes their fresh-eyes analysis here. For each slice being audited:

1. **Before looking at any code**, write down what SHOULD exist based on the slice definition
2. **Then** open the code and compare against the independent analysis
3. Document gaps, verdict, and reasoning

```text
(Audit entries will be appended here during the audit convergence loop)
```

## Execution Order (Update After Each Run)

1. `OBS.1` Fix streaming span nesting — **done** (commit e7fb31e)
2. `OBS.2` Fix error handling gaps — **done** (commit 395ca08)
3. `OBS.3` Adopt OpenInference flattened message format — **done** (commit aa44dfb)
4. `OBS.4` Add missing OpenInference semantic attributes — **done** (commit deaf835)
5. `OBS.5` Fix _PREVIEW_CHARS and content_preview — **done** (commit 86b14ae)
6. `OBS.6` Code quality: debug prints + gardener span — **done** (commit 15538f9)
7. `OBS.7` Update documentation and audit script — **done** (commit 15538f9)

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest tests/core/test_observability.py -q
pytest tests/ -q
ruff check core/observability.py adapters/llm/providers.py domain/
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read docs/ARCHITECTURE.md (observability section), then read docs/OBS_IMPROVEMENT_PLAN.md.
Begin with the next incomplete OBS slice exactly as described.

Execution loop for this child plan:

1. Work on one OBS slice at a time.
2. Each slice must stay ≤ 400 LOC net diff. No business logic in routes. Tests required.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed OBS slices OR if context is compacted/summarized, re-open docs/ARCHITECTURE.md and docs/OBS_IMPROVEMENT_PLAN.md and restate which OBS slices remain.
6. Continue to the next incomplete OBS slice once the previous slice is verified.
7. When all OBS slices are complete, update the execution order section and stop.

Key technical context:

- `core/observability.py` is the central module (600 lines). All tracing flows through it.
- `create_span()` creates spans WITHOUT setting them as OTel current context (for thread-safety in generators).
- `start_span()` creates spans WITH context management (sets span as current, auto-parents children).
- The streaming path (`domain/chat/stream.py`) uses `create_span()` for the root span, causing child spans to be orphaned.
- OpenInference spec requires flattened indexed attributes for messages: `llm.input_messages.0.message.role`, NOT a JSON string.
- `_AIOnlySpanExporter` filters spans without `openinference.span.kind` — every exported span MUST have this attribute.
- `_PREVIEW_CHARS` is currently 65536 (effectively disabled) — should be 256 per docs.
- The non-streaming path (`domain/chat/respond.py`) uses `start_span()` and nests correctly — use it as reference.

Do NOT stop just because one OBS slice is complete. OBS completion is only a checkpoint.

If this child plan is being revisited during an audit cycle:
- Treat every reopened slice as if it has NOT been implemented.
- In the Audit Workspace, write what SHOULD exist BEFORE looking at code.
- Then compare against actual implementation.
- Re-implement from scratch if gaps are found — do not just patch.
- Tests passing is NOT sufficient — confirm logic correctness through code review.
- Only work on slices marked as "reopened". Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/ARCHITECTURE.md (observability section).
Read docs/OBS_IMPROVEMENT_PLAN.md.
Begin with the current OBS slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When all OBS slices are complete, update the execution order and stop.
```
