# Colearni Refinement — LLM Completion Standardization Plan

Last updated: 2026-03-04

Parent plan: `docs/CREF_MASTER_PLAN.md`

Archive snapshots:
- `docs/archive/cref/01_llm_completion_plan_v0.md`

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

This track reworks the entire LLM completion layer to use LiteLLM's standardized OpenAI-compatible message format and enables a suite of LiteLLM features that improve reliability, performance, and capability.

Currently, the system stuffs RAG results and chat history into a single system message as concatenated text. This is non-standard, makes prompt caching ineffective, prevents proper token counting/trimming, and blocks features like vision and function calling that require structured message content.

After this track, all LLM calls will use the standard `messages` array format: system instructions in `system` role, chat history as `user`/`assistant` alternation, RAG evidence as `assistant` messages, and user queries as `user` messages. LiteLLM features (prompt caching, reliability, JSON mode, function calling, batch completion, reasoning content, max token trimming) will be enabled through the adapter layer.

## Inputs Used

- `docs/CREF_MASTER_PLAN.md` (parent plan)
- `adapters/llm/providers.py` — current LLM client abstraction
- `adapters/llm/factory.py` — LLM client factory
- `domain/chat/response_service.py` — tutor prompt assembly
- `domain/chat/session_memory.py` — chat history management
- `core/prompting/` — prompt asset system
- LiteLLM docs: completion/input, completion/output, prompt_caching, reliable_completions, json_mode, function_call, batching, reasoning_content, stream

## Executive Summary

What works today:
- LLM calls go through `adapters/llm/providers.py` with basic system + user message pairs
- `PromptRegistry` loads versioned prompt assets
- Token counting exists but is basic
- Streaming works but is not fully async

What this track fixes or adds:
1. Standardize all LLM calls to OpenAI message format via LiteLLM
2. Move RAG evidence from system message to assistant messages
3. Move chat history from system message to proper message chain
4. Enable prompt caching (stable system message prefix)
5. Add reliability features (retries, fallbacks, context window fallback)
6. Switch JSON responses to `response_format` parameter
7. Enable function calling via `tools` parameter
8. Use batch completion for graph generation
9. Handle reasoning/thinking content from models
10. Implement max token trimming for input messages
11. Support async streaming via `acompletion(stream=True)`
12. Ensure OpenAI SDK compatibility is maintained through LiteLLM's translation

## Non-Negotiable Constraints

1. All LLM calls must go through `adapters/llm/` — no direct `litellm` imports in `domain/` or `apps/`
2. Existing tests must continue to pass after each slice
3. Prompt caching requires stable system message prefix — do not change system message structure per-request
4. Function calling tools must be defined as Pydantic models in `core/schemas/`
5. No unbounded retries — max 3 retries per call

## Completed Work (Do Not Reopen Unless Blocked)

- `adapters/llm/providers.py` basic LLM client with streaming
- `adapters/llm/factory.py` client factory
- `core/prompting/` prompt asset system
- `domain/chat/response_service.py` tutor prompt assembly (will be refactored, not removed)

## Remaining Slice IDs

- `CREF1.1` Message Format Standardization
- `CREF1.2` Chat History in Message Chain
- `CREF1.3` RAG Evidence as Messages
- `CREF1.4` Max Token Trimming
- `CREF1.5` Prompt Caching
- `CREF1.6` Reliability Features
- `CREF1.7` JSON Mode
- `CREF1.8` Function Calling / Tools
- `CREF1.9` Batch Completion for Graph
- `CREF1.10` Reasoning Content Handling
- `CREF1.11` Async Streaming

## Decision Log

1. Use `litellm.completion()` / `litellm.acompletion()` directly in `adapters/llm/providers.py`, not the LiteLLM proxy server.
2. RAG evidence formatted as assistant messages with structured text: `"[Evidence from {source}]: {content}"`.
3. Chat history loaded from DB as `user`/`assistant` message pairs, not as a text summary in system prompt.
4. System message structure: `[static instructions] + [dynamic context (topic, mastery)]`. Static prefix enables prompt caching.
5. For JSON mode: use `response_format={"type": "json_schema", "json_schema": ...}` with Pydantic models where supported.
6. For function calling: define tools as Pydantic schemas, use `tools` parameter, handle `tool_calls` in response.
7. Batch completion for graph: use `litellm.batch_completion()` for parallel concept extraction.
8. Max token trimming: use `litellm.utils.trim_messages()` or implement custom trimming with `litellm.token_counter()`.

## Current Verification Status

- `pytest -q`: baseline to be recorded
- `ruff check .`: baseline to be recorded

Hotspots:

| File | Why it matters |
|---|---|
| `adapters/llm/providers.py` | Core LLM client — every slice touches this |
| `domain/chat/response_service.py` | Tutor prompt assembly — must adopt new format |
| `domain/chat/session_memory.py` | History loading — CREF1.2 target |
| `domain/graph/` | Graph extraction — CREF1.9 batch target |

## Implementation Sequencing

Each slice should end with green tests before the next slice starts.

### CREF1.1. Slice 1: Message Format Standardization

Purpose:
- Refactor the LLM adapter to accept and send messages in the standard OpenAI format: `[{"role": "system", "content": [...]}, {"role": "user", "content": [...]}, ...]`

Root problem:
- Messages are currently constructed as simple `{"role": "system/user", "content": "string"}` pairs with all context concatenated into the system message content string.

Files involved:
- `adapters/llm/providers.py`
- `adapters/llm/factory.py`
- `domain/chat/response_service.py`
- `core/prompting/renderer.py` (if prompt rendering needs adjustment)

Implementation steps:
1. Define a `StandardMessage` type (or use LiteLLM's `ChatCompletionMessageParam` type) in `core/schemas/`
2. Update `adapters/llm/providers.py` to accept `messages: list[StandardMessage]` instead of separate system/user strings
3. Update `generate_tutor_text()` in `response_service.py` to build messages as a proper array
4. Ensure system message content uses the list-of-content-blocks format: `[{"type": "text", "text": "..."}]`
5. Update tests

What stays the same:
- Prompt asset loading via `PromptRegistry`
- Observability span attributes
- Response parsing

Verification:
- `pytest -q tests/` — all existing tests pass
- Manual check: send a chat message, verify tutor responds correctly
- Verify Phoenix traces show correct `llm.input_messages` format

Exit criteria:
- All LLM calls use the `messages` array format
- No string concatenation for system message content
- Tests pass

### CREF1.2. Slice 2: Chat History in Message Chain

Purpose:
- Move chat history from a text blob in the system message to proper `user`/`assistant` message alternation in the messages array.

Root problem:
- `session_memory.py` loads history and formats it as a text string that gets embedded in the system prompt, wasting tokens and preventing prompt caching of the static system prefix.

Files involved:
- `domain/chat/session_memory.py`
- `domain/chat/response_service.py`
- `adapters/db/chat.py` (if history loading format changes)

Implementation steps:
1. Add a `load_history_as_messages()` method to `session_memory.py` that returns `list[StandardMessage]`
2. Each stored message becomes `{"role": "user"|"assistant", "content": payload_text}`
3. Update `response_service.py` to insert history messages between system and current user message
4. Keep the compaction logic (summarize old messages) but output the summary as a system message addendum, not inline
5. Update tests

What stays the same:
- Message storage format in DB
- Compaction threshold (40 messages)
- The system message content (instructions)

Verification:
- `pytest -q tests/`
- Manual check: multi-turn conversation maintains context
- Verify token count is similar or lower than before

Exit criteria:
- Chat history appears as discrete user/assistant messages in the LLM call
- System message only contains instructions + dynamic context, not history
- Compaction still works

### CREF1.3. Slice 3: RAG Evidence as Messages

Purpose:
- Format retrieved evidence items as assistant messages in the conversation chain instead of embedding them in the system message.

Root problem:
- RAG evidence is currently stuffed into the system prompt, making it part of the "instruction" prefix. This prevents prompt caching of the static system prefix and conflates instructions with context.

Files involved:
- `domain/chat/response_service.py`
- `adapters/retrieval/` (if evidence formatting changes)
- `core/schemas/` (EvidenceItem formatting)

Implementation steps:
1. After retrieval, format each `EvidenceItem` as an assistant message: `{"role": "assistant", "content": "[Evidence from {source_title}, chunk {chunk_id}]: {content_text}"}`
2. Insert evidence messages after history and before the current user message
3. Add a system instruction line explaining that assistant evidence messages contain retrieved context
4. Remove evidence from the system message body
5. Update tests

What stays the same:
- Retrieval logic (hybrid vector + FTS)
- EvidenceItem schema
- Citation generation

Verification:
- `pytest -q tests/`
- Manual check: tutor response still cites sources correctly
- Verify Phoenix traces show evidence as separate messages
- Check that evidence is no longer in the system message

Exit criteria:
- Evidence items appear as assistant messages in the LLM call
- System message is free of evidence content
- Citation quality is maintained

### CREF1.4. Slice 4: Max Token Trimming

Purpose:
- Implement input message trimming to stay within model context windows using LiteLLM's token counting.

Root problem:
- No guardrail prevents the messages array from exceeding the model's context window, which can cause API errors or silent truncation.

Files involved:
- `adapters/llm/providers.py`
- New: `adapters/llm/token_utils.py`

Implementation steps:
1. Create `adapters/llm/token_utils.py` with a `trim_messages()` function
2. Use `litellm.token_counter(model, messages)` to count tokens
3. If total exceeds `max_input_tokens` (model-specific, from `litellm.get_model_info()`), trim oldest history messages first, then evidence messages
4. Always preserve: system message, current user message, at least 2 most recent history turns
5. Call `trim_messages()` in the LLM adapter before sending
6. Log trimming events to observability
7. Add tests

What stays the same:
- Message format from CREF1.1–1.3
- LLM call parameters

Verification:
- `pytest -q tests/`
- Unit test: messages exceeding token limit are trimmed correctly
- Unit test: system message and current user message are never trimmed

Exit criteria:
- All LLM calls have token-safe input
- Trimming preserves most recent context
- Trimming events are logged

### CREF1.5. Slice 5: Prompt Caching

Purpose:
- Structure system messages to maximize LiteLLM/OpenAI prefix caching and log cache hit rates.

Root problem:
- With history and evidence now in separate messages (CREF1.2, CREF1.3), the system message is stable — but the system needs to be structured to keep the static prefix >= 1024 tokens for OpenAI caching eligibility.

Files involved:
- `adapters/llm/providers.py`
- `domain/chat/response_service.py`
- `core/observability.py` (log cached_tokens)

Implementation steps:
1. Structure system message: `[{"type": "text", "text": "<static instructions (~1024+ tokens)>"}]` — pad with detailed role description if needed
2. Dynamic context (topic name, mastery status) goes in a second content block or a separate system message
3. Pass `prompt_cache_key` (e.g., `"tutor-{workspace_id}"`) if using OpenAI
4. Log `response.usage.prompt_tokens_details.cached_tokens` in observability spans
5. Add `cached_tokens` to generation trace metadata
6. Update tests

What stays the same:
- Message order: system → history → evidence → user
- Prompt content

Verification:
- `pytest -q tests/`
- Manual check: second identical request shows `cached_tokens > 0` in traces
- Verify generation trace includes `cached_tokens`

Exit criteria:
- System message is structured for prefix caching
- `cached_tokens` is logged in observability
- Cache hits are observable in Phoenix

### CREF1.6. Slice 6: Reliability Features

Purpose:
- Add retries, fallback models, and context window fallback to all LLM calls via LiteLLM's built-in reliability features.

Root problem:
- LLM calls can fail due to transient errors, rate limits, or context window overflow with no automated recovery.

Files involved:
- `adapters/llm/providers.py`
- `adapters/llm/factory.py`
- Settings/config (for fallback model definitions)

Implementation steps:
1. Add `num_retries=3` to all `litellm.completion()` / `litellm.acompletion()` calls
2. Define `context_window_fallback_dict` mapping models to their larger equivalents (e.g., `gpt-4.1-nano → gpt-4.1-mini`)
3. Define `fallbacks` list in factory config for each LLM client type (tutor, graph, quiz)
4. Add `timeout` parameter (default 60s for tutor, 120s for graph generation)
5. Log fallback events to observability
6. Update tests

What stays the same:
- Primary model selection logic
- All other LLM call parameters

Verification:
- `pytest -q tests/`
- Unit test: simulated API error triggers retry
- Unit test: context window overflow triggers fallback model

Exit criteria:
- All LLM calls have retries and fallbacks configured
- Fallback events are logged

### CREF1.7. Slice 7: JSON Mode

Purpose:
- Switch all structured JSON responses to use LiteLLM's `response_format` parameter instead of manual JSON parsing/validation.

Root problem:
- Currently, JSON responses are requested via prompt instructions and parsed manually, which is fragile and model-dependent.

Files involved:
- `adapters/llm/providers.py`
- `domain/chat/query_analyzer.py` (returns JSON)
- `domain/graph/` extraction modules (return JSON)
- `domain/learning/` quiz generation (returns JSON)
- `core/schemas/` (Pydantic models for response schemas)

Implementation steps:
1. For each LLM call that expects JSON output, add `response_format={"type": "json_schema", "json_schema": {...}}` using the existing Pydantic model's `.model_json_schema()`
2. Where `json_schema` is not supported by the model, fall back to `response_format={"type": "json_object"}`
3. Enable `litellm.enable_json_schema_validation = True` for client-side validation
4. Remove manual JSON extraction regexes where `response_format` handles it
5. Update tests

What stays the same:
- Pydantic model definitions
- Business logic after parsing

Verification:
- `pytest -q tests/`
- Unit test: structured response matches Pydantic schema
- Manual check: query analysis returns valid JSON

Exit criteria:
- All JSON-expecting LLM calls use `response_format`
- No manual JSON regex extraction for calls that support `response_format`
- Client-side validation enabled

### CREF1.8. Slice 8: Function Calling / Tools

Purpose:
- Define LLM tools using LiteLLM's `tools` parameter for capabilities that benefit from structured function calling (e.g., topic suggestion, quiz generation trigger, graph exploration).

Root problem:
- Currently, tool-like behaviors are handled through prompt engineering and manual parsing. Function calling provides structured, reliable tool invocation.

Files involved:
- `adapters/llm/providers.py` (accept `tools` parameter)
- `core/schemas/tools.py` (new — tool definitions)
- `domain/chat/response_service.py` (handle tool_calls in response)
- `domain/chat/` conductor logic

Implementation steps:
1. Create `core/schemas/tools.py` with Pydantic-based tool definitions:
   - `suggest_topic_change(concept_id, reason)`
   - `generate_quiz(concept_id, quiz_type)`
   - `search_knowledge_base(query)`
2. Convert tool definitions to OpenAI `tools` format
3. Update LLM adapter to pass `tools` and `tool_choice` parameters
4. Handle `tool_calls` in response: execute tool, append tool result, re-call LLM
5. Add tool execution loop with budget (max 3 tool calls per turn)
6. Update tests

What stays the same:
- Existing domain functions that tools will call
- Response format for non-tool responses

Verification:
- `pytest -q tests/`
- Unit test: LLM response with tool_call triggers correct function
- Manual check: tutor can suggest topic change via function call

Exit criteria:
- At least 3 tools defined and functional
- Tool execution loop has a budget
- Tool calls are logged in observability

### CREF1.9. Slice 9: Batch Completion for Graph

Purpose:
- Use `litellm.batch_completion()` for parallel concept/edge extraction during document ingestion.

Root problem:
- Graph extraction processes chunks sequentially, making ingestion slow for large documents.

Files involved:
- `domain/graph/` extraction modules
- `adapters/llm/providers.py` (add batch method)

Implementation steps:
1. Add `batch_complete()` method to the LLM adapter that wraps `litellm.batch_completion()`
2. In graph extraction, batch chunks into groups of N (e.g., 5) and call `batch_complete()`
3. Parse results in order, maintaining chunk-to-result mapping
4. Handle partial failures (some batch items fail, others succeed)
5. Add tests

What stays the same:
- Extraction prompt templates
- Canonical graph resolution logic
- Gardener logic

Verification:
- `pytest -q tests/`
- Unit test: batch of 5 chunks returns 5 results
- Performance check: ingestion of multi-chunk document is faster

Exit criteria:
- Graph extraction uses batch completion
- Partial failures are handled gracefully
- Ingestion speed improves for multi-chunk documents

### CREF1.10. Slice 10: Reasoning Content Handling

Purpose:
- Handle `reasoning_content` / thinking tokens in LLM responses from models that support extended thinking (e.g., Claude 3.7+, o1).

Root problem:
- Models with reasoning capabilities return thinking content alongside the main response. The system currently ignores this, potentially losing useful debugging info and miscounting tokens.

Files involved:
- `adapters/llm/providers.py`
- `core/observability.py`
- `domain/chat/response_service.py`

Implementation steps:
1. After LLM response, check for `response.choices[0].message.reasoning_content`
2. If present, log it to observability as a span attribute (`llm.reasoning_content`)
3. Include `reasoning_tokens` in token count logging
4. Pass `reasoning_effort` parameter when configured (low/medium/high)
5. Do not expose reasoning content to the user — it's internal
6. Update tests

What stays the same:
- User-facing response content
- All other response handling

Verification:
- `pytest -q tests/`
- Unit test: reasoning content is extracted and logged
- Verify Phoenix traces include reasoning tokens

Exit criteria:
- Reasoning content is captured in observability
- Reasoning tokens are counted
- No user-visible change

### CREF1.11. Slice 11: Async Streaming

Purpose:
- Migrate streaming to use `litellm.acompletion(stream=True)` for proper async streaming support.

Root problem:
- Current streaming may use synchronous patterns that block the event loop or don't integrate well with FastAPI's async endpoints.

Files involved:
- `adapters/llm/providers.py`
- `domain/chat/response_service.py` (or `domain/chat/respond.py`)
- `apps/api/` streaming endpoints

Implementation steps:
1. Update LLM adapter to use `await litellm.acompletion(model, messages, stream=True)`
2. Return an async generator that yields `ModelResponse` chunks
3. Update the streaming endpoint to use `StreamingResponse` with the async generator
4. Handle stream completion detection (`finish_reason == "stop"`)
5. Log streaming token usage from the final chunk (if `stream_options={"include_usage": True}`)
6. Update tests

What stays the same:
- SSE format to frontend
- Frontend streaming consumption logic

Verification:
- `pytest -q tests/`
- Manual check: chat response streams correctly
- Verify no event loop blocking warnings

Exit criteria:
- All streaming uses `acompletion(stream=True)`
- Token usage is captured from streaming
- No synchronous blocking in async endpoints

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

1. `CREF1.1` Message Format Standardization
2. `CREF1.2` Chat History in Message Chain
3. `CREF1.3` RAG Evidence as Messages
4. `CREF1.4` Max Token Trimming
5. `CREF1.5` Prompt Caching
6. `CREF1.6` Reliability Features
7. `CREF1.7` JSON Mode
8. `CREF1.8` Function Calling / Tools
9. `CREF1.9` Batch Completion for Graph
10. `CREF1.10` Reasoning Content Handling
11. `CREF1.11` Async Streaming

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
ruff check .
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read docs/CREF_MASTER_PLAN.md, then read docs/cref/01_llm_completion_plan.md.
Begin with the next incomplete CREF1 slice exactly as described.

Execution loop for this child plan:

1. Work on one CREF1 slice at a time.
2. PRs <= 400 LOC net. No business logic in routes. All LLM calls through adapters/llm/. Tests required.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed CREF1 slices OR if context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and docs/cref/01_llm_completion_plan.md and restate which CREF1 slices remain.
6. Continue to the next incomplete CREF1 slice once the previous slice is verified.
7. When all CREF1 slices are complete, immediately re-open docs/CREF_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because CREF1 is complete. CREF1 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle:
- Treat every reopened slice as if it has NOT been implemented.
- In the Audit Workspace, write what SHOULD exist BEFORE looking at code.
- Then compare against actual implementation.
- Re-implement from scratch if gaps are found — do not just patch.
- Tests passing is NOT sufficient — confirm logic correctness through code review.
- Only work on slices marked as "reopened". Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/CREF_MASTER_PLAN.md.
Read docs/cref/01_llm_completion_plan.md.
Begin with the current CREF1 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When CREF1 is complete, immediately return to docs/CREF_MASTER_PLAN.md and continue with the next incomplete child plan.
```
