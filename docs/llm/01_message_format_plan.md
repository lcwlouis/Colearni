# L1 — Message Format Standardization

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Track ID: `L1`
Status: 🔄 in-progress

## Purpose

Rework all LLM calls to use proper multi-message `messages[]` format instead of the
current flat 2-message format (system + user). This enables prompt caching, proper
context window management, and compatibility with tool calling.

## Current State

All LLM calls use:
```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": prompt},
]
```

Chat history, RAG evidence, assessment context, document summaries, graph context,
flashcard progress, and learner profile are all concatenated into the system prompt
string. This prevents prompt caching (system prefix changes every turn) and violates
OpenAI/LiteLLM best practices.

## Target State

```python
messages = [
    {"role": "system", "content": stable_persona_and_rules},      # cacheable prefix
    {"role": "system", "content": context_block},                  # doc summaries, graph, assessment
    {"role": "assistant", "content": compacted_history_summary},   # if exists
    {"role": "user", "content": old_user_msg_1},                   # recent history
    {"role": "assistant", "content": old_assistant_msg_1},         # recent history
    ...
    {"role": "user", "content": evidence_block + user_query},      # current turn
]
```

## Slice Status

| Slice | Description | Status |
|-------|-------------|--------|
| L1.1 | Define `MessageBuilder` — typed message list builder | 🔄 pending |
| L1.2 | Refactor `PromptMessages` → use `MessageBuilder` in prompt_kit.py | 🔄 pending |
| L1.3 | Update LLM client methods to accept `messages[]` | 🔄 pending |
| L1.4 | Migrate tutor response path (stream.py, tutor_agent.py, response_service.py) | 🔄 pending |
| L1.5 | Migrate query analyzer to multi-message format | 🔄 pending |
| L1.6 | Migrate graph extraction / disambiguation to multi-message format | 🔄 pending |
| L1.7 | Migrate quiz grading to multi-message format | 🔄 pending |
| L1.8 | Migrate session compaction (summary generation) to multi-message format | 🔄 pending |
| L1.9 | Deprecate old `prompt + system_prompt` client methods (keep as thin wrappers) | 🔄 pending |

## Slice Definitions

### L1.1 — Define `MessageBuilder`

**Purpose**: Create a typed, validated message list builder that replaces raw
`list[dict[str, str]]` construction throughout the codebase.

**Implementation Steps**:
1. Create `core/llm_messages.py` with:
   - `MessageRole` — Literal type for valid roles
   - `Message` — TypedDict with `role`, `content`, optional `name`, `tool_call_id`
   - `MessageBuilder` — fluent builder class:
     - `.system(content)` → add system message
     - `.user(content)` → add user message
     - `.assistant(content)` → add assistant message
     - `.tool(content, tool_call_id=)` → add tool message
     - `.context(content, label=)` → add context block (system role with delimiter)
     - `.history(turns)` → add user/assistant turn pairs from chat history
     - `.build()` → validate and return `list[Message]`
     - Validation: non-empty, system messages first, last message user or tool
2. Create `tests/core/test_llm_messages.py` with comprehensive tests

**Exit Criteria**:
- `core/llm_messages.py` exists with `MessageBuilder` class
- All builder methods return `self` for chaining
- `.build()` validates message ordering and raises `ValueError` on violations
- Tests cover: happy path, chaining, validation errors, empty builder, tool messages
- `pytest tests/core/test_llm_messages.py -q` passes
- `ruff check core/llm_messages.py tests/core/test_llm_messages.py` passes
- No existing tests broken: `pytest -q` passes

### L1.2 — Refactor `PromptMessages` → use `MessageBuilder`

**Purpose**: Update `prompt_kit.py` to return a `MessageBuilder` (or `list[Message]`)
instead of `PromptMessages(system=, user=)` dataclass. Keep `PromptMessages` as a
compatibility shim initially.

**Implementation Steps**:
1. Add `build_tutor_messages()` function in `prompt_kit.py` that returns `MessageBuilder`
2. Separate the system prompt into stable prefix + variable context blocks
3. Add evidence as a separate context block instead of cramming into user message
4. Keep `build_full_tutor_prompt_with_meta()` as a compat wrapper that calls the new function
5. Update tests

**Exit Criteria**:
- `build_tutor_messages()` exists and returns a `MessageBuilder`
- System prompt is split: stable persona/rules prefix + variable context
- Evidence is a separate message (not concatenated into user message)
- Old `build_full_tutor_prompt_with_meta()` still works (compat wrapper)
- All existing tests pass

### L1.3 — Update LLM client methods to accept `messages[]`

**Purpose**: Add new methods to `_BaseGraphLLMClient` that accept `list[Message]` directly,
while keeping old methods as compatibility wrappers.

**Implementation Steps**:
1. Add `stream_messages()` method — accepts `messages: list[Message]`, returns `TutorTextStream`
2. Add `complete_messages()` method — accepts `messages: list[Message]`, returns traced result
3. Add `complete_messages_json()` method — accepts `messages: list[Message]` + schema
4. Implement in both `OpenAIGraphLLMClient` and `LiteLLMGraphLLMClient`
5. Keep old `generate_tutor_text_stream()`, `_chat_json()`, `_chat_text_traced()` as wrappers

**Exit Criteria**:
- New `*_messages()` methods exist on both provider implementations
- Old methods still work (they internally build a 2-message list and delegate)
- Both OpenAI and LiteLLM paths tested
- All existing tests pass

### L1.4 — Migrate tutor response path

**Purpose**: Update `stream.py`, `tutor_agent.py`, and `response_service.py` to use
`MessageBuilder` and the new `stream_messages()` client method.

**Implementation Steps**:
1. Update `stream.py` → `generate_chat_response_stream()` to use `build_tutor_messages()`
   and `stream_messages()` instead of `generate_tutor_text_stream(prompt=, system_prompt=)`
2. Update `response_service.py` → `generate_tutor_text()` similarly
3. Update `tutor_agent.py` → `build_tutor_response_text()` to use `MessageBuilder`
4. Verify streaming, phase tracking, observability all still work

**Exit Criteria**:
- Tutor chat path uses `MessageBuilder` end-to-end
- Streaming still works with deltas, phases, trace events
- Evidence is in a separate message in the messages list
- All existing chat tests pass

### L1.5 — Migrate query analyzer

**Purpose**: Update `query_analyzer.py` to use `MessageBuilder` and `complete_messages_json()`.

**Implementation Steps**:
1. Update `build_query_analysis_prompt()` to return `MessageBuilder`
2. Update `run_query_analysis()` to use `complete_messages_json()`
3. Keep JSON schema fallback chain working

**Exit Criteria**:
- Query analyzer uses `MessageBuilder`
- JSON parsing and fallback chain still work
- All query analyzer tests pass

### L1.6 — Migrate graph extraction / disambiguation

**Purpose**: Update `extract_raw_graph()` and `disambiguate()` in providers.py to use
`MessageBuilder` internally.

**Implementation Steps**:
1. Refactor `extract_raw_graph()` to use `MessageBuilder` for message construction
2. Refactor `disambiguate()` and `disambiguate_batch()` similarly
3. Preserve existing JSON schema and budget enforcement

**Exit Criteria**:
- Graph extraction uses `MessageBuilder` internally
- Disambiguation uses `MessageBuilder` internally
- Budget limits preserved (max disambiguations per chunk/doc)
- All graph extraction tests pass

### L1.7 — Migrate quiz grading

**Purpose**: Update quiz grading LLM calls to use `MessageBuilder`.

**Implementation Steps**:
1. Update `domain/learning/quiz_grading.py` prompt building
2. Update `domain/learning/quiz_flow.py` LLM call to use `complete_messages()`
3. Preserve grading JSON schema and fallback

**Exit Criteria**:
- Quiz grading uses `MessageBuilder`
- Grading JSON parsing still works
- All quiz/assessment tests pass

### L1.8 — Migrate session compaction

**Purpose**: Update `maybe_compact_session_context()` to use `MessageBuilder`.

**Implementation Steps**:
1. Update compaction prompt building to use `MessageBuilder`
2. Update LLM call to use `complete_messages()` instead of `generate_tutor_text()`
3. Preserve compaction threshold and summary format

**Exit Criteria**:
- Session compaction uses `MessageBuilder`
- Compaction still triggers at threshold (40 messages)
- Summary format unchanged
- All session memory tests pass

### L1.9 — Deprecate old client methods

**Purpose**: Mark old `prompt + system_prompt` methods as deprecated thin wrappers.

**Implementation Steps**:
1. Add deprecation warnings to old methods
2. Ensure all call sites have been migrated (no direct callers remain)
3. Document migration path in docstrings
4. Keep methods functional (they wrap the new `*_messages()` methods)

**Exit Criteria**:
- Old methods have deprecation warnings
- No direct callers of old methods (all use `*_messages()`)
- All tests pass
- `ruff check .` passes

## Verification Blocks

(Populated as slices are completed)

## Removal Ledger

(Populated as code is removed/replaced)

## Audit Workspace

(Populated during self-audit phase)

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/llm/01_message_format_plan.md. Begin with the current incomplete slice.
Follow the execution loop in docs/llm/LLM_MASTER_PLAN.md.
```
