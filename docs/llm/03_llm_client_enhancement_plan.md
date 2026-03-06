# L3 — LLM Client Enhancement

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Track ID: `L3`
Status: ✅ complete

## Purpose

Adopt LiteLLM's built-in features for reliability, performance, and observability:
token trimming, prompt caching structure, retry/fallback logic, reasoning content
extraction, async streaming, and cached token observability.

## Current State

- Streaming: sync generators only (no async)
- Retry: rate limiter exists, but no `num_retries` / `max_retries` on completion calls
- Fallback: JSON format fallback chain exists, but no model fallback dict
- Token counting: full support including `cached_tokens` in `GenerationTrace`
- Token trimming: none — no `trim_messages()` or `get_max_tokens()`
- Reasoning: token count extracted, but not reasoning content text
- Prompt caching: system prompts not structured for stable prefix caching

## Slice Status

| Slice | Description | Status |
|-------|-------------|--------|
| L3.1 | Implement `trim_messages()` utility | ✅ done |
| L3.2 | Structure system prompts for prompt caching | ✅ done |
| L3.3 | Add retries + fallbacks to completion calls | ✅ done |
| L3.4 | Extract and surface `reasoning_content` from responses | ✅ done |
| L3.5 | Add async completion methods | ✅ done |
| L3.6 | Add `cached_tokens` to `GenerationTrace` | ✅ done (pre-existing) |

## Slice Definitions

### L3.1 — Implement `trim_messages()` utility

**Purpose**: Prevent context window overflow by trimming oldest history messages.

**Implementation Steps**:
1. Create `core/llm_trimming.py` with:
   - `trim_messages(messages, model, max_fraction=0.8)` → trimmed `list[Message]`
   - Uses `litellm.token_counter(model, messages)` for counting
   - Uses `litellm.get_max_tokens(model)` for model limits
   - Trims oldest non-system messages first (preserve system prefix + last user message)
   - Returns messages unchanged if within limit
2. Add tests covering: within limit (no-op), over limit (trims history), preserves system and last user

**Exit Criteria**:
- `trim_messages()` exists and correctly trims history
- System messages are never trimmed
- Last user message is never trimmed
- Tests pass

### L3.2 — Structure system prompts for prompt caching

**Purpose**: Ensure system prompts have a stable prefix ≥1024 tokens for OpenAI automatic prefix caching.

**Implementation Steps**:
1. In `prompt_kit.py`, ensure `build_tutor_messages()` puts the stable persona/rules as the FIRST system message (already done in L1.2)
2. Verify the first system message is ≥1024 tokens (pad if needed with detailed instructions)
3. Variable context goes in subsequent system messages (already done in L1.2)
4. Add `cache_control` annotation support for Anthropic models (optional metadata on first system message)
5. Add a test verifying the first system message is stable across calls

**Exit Criteria**:
- First system message is stable (same content for same persona)
- First system message has sufficient content for caching
- Variable context is in separate messages after the stable prefix

### L3.3 — Add retries + fallbacks to completion calls

**Purpose**: Add reliability parameters to LLM completion calls.

**Implementation Steps**:
1. Add `num_retries` (default 2) to LiteLLM completion calls in `_sdk_call()` and `_sdk_streaming_call()`
2. Add `context_window_fallback_dict` config (e.g., `gpt-4o → gpt-4o-mini`) via settings
3. For OpenAI SDK path, add `max_retries` to the client constructor
4. Add fallback model config to settings
5. Tests: verify retry params are passed through

**Exit Criteria**:
- LiteLLM calls include `num_retries`
- OpenAI client uses `max_retries`
- Context window fallback configured
- Tests pass

### L3.4 — Extract and surface `reasoning_content` from responses

**Purpose**: Capture reasoning/thinking text from LLM responses.

**Implementation Steps**:
1. In response parsing, extract `choices[0].message.reasoning_content` (Anthropic/DeepSeek)
2. Add `reasoning_content: str | None` to `GenerationTrace`
3. Pass reasoning content to observability spans
4. Tests with mock responses containing reasoning content

**Exit Criteria**:
- `reasoning_content` extracted from responses that include it
- Stored in `GenerationTrace`
- Tests cover presence and absence of reasoning content

### L3.5 — Migrate streaming to async

**Purpose**: Use `acompletion` for true async streaming.

**Implementation Steps**:
1. Add `async_stream_messages()` method using `litellm.acompletion(stream=True)`
2. Add `async_complete_messages()` method using `litellm.acompletion()`
3. For OpenAI SDK: use `await client.chat.completions.create()` (async client)
4. Keep sync methods as-is for backward compat
5. Wire async streaming into `generate_chat_response_stream()` if the event loop supports it

**Exit Criteria**:
- Async methods exist alongside sync methods
- Async streaming produces same output format
- Sync methods still work
- Tests pass

### L3.6 — Add `cached_tokens` to `GenerationTrace`

**Pre-existing**: `GenerationTrace` already has `cached_tokens: int | None` (line 282 of `core/schemas/assistant.py`). `extract_token_usage()` in `core/observability.py` already parses `usage.prompt_tokens_details.cached_tokens`. This slice is complete.

## Verification Blocks

### Verification Block - L3.1
Files changed: `core/llm_trimming.py` (new), `tests/core/test_llm_trimming.py` (new)
What changed: `trim_messages()` trims oldest non-system history using `litellm.token_counter()` and `litellm.get_max_tokens()`. System prefix and last user message are always preserved. Gracefully handles litellm unavailability.
Tests: 9 tests passing — under limit no-op, over limit trimming, system preserved, last user preserved, litellm unavailable fallbacks, empty input.
Observed outcome: 1044+ tests pass, no regressions.

### Verification Block - L3.2
Files changed: `domain/chat/prompt_kit.py` (enriched persona prefix), `adapters/llm/providers.py` (cache_control annotation)
What changed: `_build_persona_prefix()` now loads stable sections from versioned prompt templates. `_apply_cache_control()` annotates first system message with `cache_control: {"type": "ephemeral"}` for Anthropic models. `_prepare_messages()` called at both SDK call sites.
Tests: 26 new tests — prefix determinism, variable context separation, Anthropic model detection, cache_control annotation.
Observed outcome: All tests pass, no regressions.

### Verification Block - L3.3
Files changed: `adapters/llm/providers.py` (retry params), `core/settings.py` (new settings), `adapters/llm/factory.py` (wiring)
What changed: OpenAI `max_retries=2` on client constructor. LiteLLM `num_retries=2` + `context_window_fallback_dict` on completion calls. Settings: `llm_sdk_max_retries`, `llm_context_window_fallbacks`.
Tests: 12 new tests — retry params passed through for both providers.
Observed outcome: All tests pass, no regressions.

### Verification Block - L3.4
Files changed: `adapters/llm/providers.py` (reasoning extraction), `core/schemas/assistant.py` (field), `core/contracts.py` (type)
What changed: `_extract_reasoning_content()` handles both `message.reasoning_content` (Anthropic/DeepSeek) and `type:"thinking"` content blocks (Claude native). Wired into both streaming and non-streaming paths. `GenerationTrace.reasoning_content: str | None` added. `llm.reasoning_content` span attribute set.
Tests: 10 new tests — reasoning content extraction from both formats, span attributes, absence handling.
Observed outcome: All tests pass, no regressions.

### Verification Block - L3.5
Files changed: `adapters/llm/providers.py` (async methods), `core/contracts.py` (protocol update)
What changed: `async_complete_messages()` and `async_complete_messages_json()` added to base class. OpenAI uses `AsyncOpenAI` client, LiteLLM uses `litellm.acompletion()`. Sync methods unchanged. `_async_sdk_call()` and `_async_sdk_stream_call()` as overridable concrete methods with NotImplementedError defaults.
Tests: 7 new tests — async completion for both providers, JSON parsing, coroutine verification.
Observed outcome: 1051 tests pass, no regressions.

### Verification Block - L3.6

Root cause
- N/A — feature was already implemented before this plan was created.

Files changed
- None (pre-existing)

What changed
- `GenerationTrace.cached_tokens` field exists in `core/schemas/assistant.py:282`
- `extract_token_usage()` in `core/observability.py` parses `cached_tokens`
- `LLM_TOKEN_COUNT_CACHE_READ` span attribute wired in observability

Commands run
- Verified by code inspection

Logic review
- `cached_tokens` is parsed from `usage.prompt_tokens_details.cached_tokens` with None fallback
- Correctly handles providers that don't return cache info

Manual verification steps
- N/A (pre-existing)

Observed outcome
- Feature already working

## Removal Ledger

(Populated as code is removed/replaced)

## Audit Workspace

(Populated during self-audit phase)

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/llm/03_llm_client_enhancement_plan.md. Begin with the current incomplete slice.
Follow the execution loop in docs/llm/LLM_MASTER_PLAN.md.
```
