# LLM Connections — Master Plan

Last updated: 2026-03-06

Archive snapshots:
- `none`

Template usage:
- This is the cross-track execution plan for reworking CoLearni's LLM completion layer
  into a standardized, agentic-ready, best-practice architecture.
- It does not replace `docs/agentic/01_conductor_plan.md` or the existing architecture docs.
- All child plans are subordinate to this document.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s) ✅
2. current verification status ✅
3. ordered track list with stable IDs ✅
4. verification block template ✅
5. removal entry template ✅
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✅

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the child plan are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (see template below).
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. All LLM calls MUST continue to work with both OpenAI SDK and LiteLLM SDK providers.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

CoLearni's LLM integration currently uses a two-message format (system + user) for all LLM calls,
with chat history, RAG evidence, assessment context, and other metadata all crammed into the system
prompt. This is suboptimal for prompt caching, context window management, and agentic extensibility.

Earlier work landed the `PromptRegistry` file-based prompt asset system and a provider abstraction
layer (`OpenAIGraphLLMClient` / `LiteLLMGraphLLMClient` in `adapters/llm/providers.py`). Rate
limiting and JSON schema fallback chains are also in place.

This plan exists to:
1. Standardize all LLM calls to use the proper multi-message `messages[]` format following
   OpenAI/LiteLLM best practices.
2. Adopt LiteLLM's built-in reliability, prompt caching, token trimming, batching, reasoning
   content, JSON mode, tool/function calling, and web search features.
3. Fix message persistence so in-progress generations survive tab switches.
4. Add message regeneration support.
5. Build a tool/function-calling framework that makes CoLearni easily extensible toward agentic
   behavior.

## Inputs Used

This plan is based on:

- User requirements document (LLM Connections thoughts — March 2026)
- `docs/ARCHITECTURE.md` — current system architecture
- `docs/PRODUCT_SPEC.md` — product specification
- `docs/CODEX.md` — repo conventions
- `docs/GRAPH.md` — graph builder/gardener architecture
- `adapters/llm/providers.py` — current LLM client implementation
- `domain/chat/stream.py`, `session_memory.py`, `prompt_kit.py` — current chat flow
- `core/schemas/chat.py` — current event/message schemas
- LiteLLM SDK docs: completion input/output, prompt caching, reliable completions,
  batching, reasoning content, JSON mode, function calling, streaming, web search
- OpenAI API docs: chat completion, structured outputs, tool calling, prompt caching

## Executive Summary

What is already in good shape:
- Provider abstraction layer (OpenAI + LiteLLM dual-client)
- Rate limiting with retries (`core/rate_limiter.py`)
- JSON schema fallback chain (json_schema → json_object → prompt-only)
- File-based prompt asset system (`core/prompting/`)
- Streaming infrastructure (SSE with keepalive, phase tracking)
- Observability wiring (OpenTelemetry spans, token counting)
- Evidence-first architecture with grounding verification

What is critically broken or materially missing:
1. **Flat message format**: All LLM calls use only 2 messages (system + user). Chat history,
   RAG evidence, assessment context all stuffed into system prompt — prevents prompt caching
   and violates OpenAI/LiteLLM best practices.
2. **No message status tracking**: No `generating`/`complete`/`failed` status in DB. Messages
   disappear on tab switch because assistant messages are only persisted on stream completion.
3. **No regeneration**: No endpoint or UI for regenerating unsatisfactory responses.
4. **No tool/function calling**: All structured output uses JSON schemas in prompts instead of
   native tool calling. No foundation for agentic tool use.
5. **No prompt caching**: System prompts not structured for OpenAI/Anthropic prefix caching.
6. **No token trimming**: No `max_tokens` trimming on input messages — risk of context window
   overflow on long conversations.
7. **No batching**: Graph extraction processes chunks serially instead of using batch completion.
8. **No reasoning content handling**: Extended thinking / chain-of-thought tokens not captured
   or utilized.
9. **No web search**: No integration for web-based research queries.
10. **No reliability fallbacks**: No model fallbacks or context window fallback chains.

## Non-Negotiable Constraints

1. **Backward compatibility**: All existing tests must continue to pass after each slice.
2. **Dual-provider**: Every feature must work with both OpenAI SDK and LiteLLM SDK paths.
3. **<= 400 LOC net per PR**: Follow `docs/CODEX.md` small PR rule.
4. **Routes stay thin**: No business logic in FastAPI routes.
5. **Budget enforcement**: All LLM call loops must have hard limits.
6. **Evidence-first**: User-visible answers must include citations; strict mode must refuse
   when evidence is insufficient.
7. **No unbounded loops**: Every tool-calling agent loop must have a max iteration count.

## Completed Work (Do Not Reopen Unless Blocked)

- `core/prompting/` — PromptRegistry, asset loader, renderer
- `core/rate_limiter.py` — Concurrency-limited rate limiter
- `adapters/llm/providers.py` — OpenAI + LiteLLM dual clients (base architecture)
- `domain/chat/stream.py` — SSE streaming with phase tracking
- `core/schemas/chat.py` — Stream event types
- `core/observability.py` — OpenTelemetry instrumentation

## Remaining Track IDs

- `L1` Message Format Standardization — Rework all LLM calls to use proper multi-message format
- `L2` Message Persistence & Status — Fix generating/complete/failed status tracking in DB
- `L3` LLM Client Enhancement — Add prompt caching, token trimming, reliability, reasoning content
- `L4` Agentic Tool Framework — Tool/function calling foundation for extensible agents
- `L5` JSON Mode Standardization — Switch to native `response_format` for all structured output
- `L6` Message Regeneration — Add regeneration endpoint and UI support
- `L7` Graph Batch Completion — Use LiteLLM batch_completion for graph extraction
- `L8` Web Search Integration — Research/web search capability via tool calling

## Child Plan Map

| Track | Child Plan | Status |
|---|---|---|
| `L1` Message Format | `docs/llm/01_message_format_plan.md` | pending |
| `L2` Message Persistence | `docs/llm/02_message_persistence_plan.md` | pending |
| `L3` LLM Client Enhancement | `docs/llm/03_llm_client_enhancement_plan.md` | ✅ done |
| `L4` Agentic Tool Framework | `docs/llm/04_tool_framework_plan.md` | ✅ done |
| `L5` JSON Mode | `docs/llm/05_json_mode_plan.md` | ✅ done |
| `L6` Regeneration | `docs/llm/06_regeneration_plan.md` | ✅ done |
| `L7` Graph Batching | `docs/llm/07_graph_batching_plan.md` | ✅ done |
| `L8` Web Search | `docs/llm/08_web_search_plan.md` | ✅ done |

## Decision Log

1. **Multi-message format over single system prompt**: Chat history and RAG evidence will be
   separate messages in the `messages[]` array instead of concatenated into the system prompt.
   This enables prompt caching (stable system prefix) and follows OpenAI/LiteLLM best practices.

2. **RAG evidence as assistant-prefixed context messages**: Retrieved evidence will be formatted
   as assistant messages (or tool result messages in agentic mode) preceding the user's question,
   rather than appended to the system prompt. This allows the LLM to treat evidence as
   conversational context it "already knows" and cite naturally.

3. **Chat history as explicit message turns**: Instead of a `CONVERSATION HISTORY` text block
   in the system prompt, actual user/assistant message pairs will be included in the messages
   array. Older history can be summarized into a system message, but recent turns (e.g., last
   10) remain as discrete messages.

4. **Write-ahead placeholder for assistant messages**: To survive tab switches, a placeholder
   assistant message with `status=generating` will be inserted before LLM streaming begins.
   Updated to `status=complete` or `status=failed` on finish.

5. **LiteLLM as primary feature surface**: Features like prompt caching, token trimming,
   batching, and web search will use LiteLLM's abstractions when available, with OpenAI SDK
   equivalents for direct OpenAI clients.

6. **Tool framework uses OpenAI-compatible `tools` param**: The agentic tool framework will
   define tools using the OpenAI `tools` schema (supported by both LiteLLM and OpenAI SDK),
   not the deprecated `functions` param.

7. **Regeneration marks old messages as `superseded`**: Rather than deleting messages, the
   regeneration flow marks the old assistant message as `superseded` and creates a new one.
   History loading filters out superseded messages.

## Clarifications Requested (Already Answered)

1. **Should OpenAI SDK path also support all features?** → Yes, dual-provider support required.
   Features like prompt caching are automatic on OpenAI; LiteLLM handles translation.
2. **Should RAG evidence be `assistant` or `tool` role?** → Start with a dedicated context
   block approach (system or assistant depending on provider). Migrate to `tool` role when
   the agentic tool framework (L4) lands.
3. **Should compacted history still exist?** → Yes. For conversations > N turns, older messages
   are summarized into a system message. Recent turns remain as discrete messages.

## Deferred Follow-On Scope

- **Multi-agent orchestration**: Full conductor/router agent architecture (see
  `docs/agentic/01_conductor_plan.md`). This plan builds the foundation but does not
  implement the conductor.
- **MCP (Model Context Protocol)**: LiteLLM supports MCP tools natively. Deferred until
  the tool framework (L4) is stable.
- **Image/multimodal inputs**: Not needed for MVP. The message format supports it when ready.
- **Spaced repetition scheduling**: Product-level feature, not LLM layer concern.
- **LiteLLM Proxy Server**: This plan uses the LiteLLM Python SDK directly, not the proxy
  server deployment mode.

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in each child plan during the run.

## Removal Entry Template

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

- `pytest -q`: baseline (to be captured at run start)
- `ruff check .`: baseline (to be captured at run start)

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `adapters/llm/providers.py` | Central LLM client — every track touches this file |
| `domain/chat/stream.py` | Streaming orchestration — L1, L2, L3, L6 all modify this |
| `domain/chat/prompt_kit.py` | Prompt building — L1 fundamentally restructures this |
| `domain/chat/session_memory.py` | Message persistence — L2, L6 depend on this |
| `adapters/db/chat.py` | DB queries — L2 adds status column |
| `core/schemas/chat.py` | Shared schemas — multiple tracks add fields |

## Remaining Work Overview

### L1. Message Format Standardization

**The foundational track.** Currently all LLM calls use a flat 2-message format:
`[{"role": "system", "content": <everything>}, {"role": "user", "content": <query>}]`.
This track restructures every LLM call site to use the proper multi-message format:

- **System message**: Stable persona + rules + grounding mode (cacheable prefix)
- **Context messages**: Document summaries, graph context, assessment context as separate
  messages (using assistant or system role with clear delimiters)
- **Chat history**: Recent turns as explicit user/assistant message pairs
- **RAG evidence**: Retrieved chunks as an assistant context message with source citations
- **User query**: The actual user question as the final user message

This enables prompt caching (stable prefix), proper context window management, and makes the
message flow compatible with tool calling. All call sites must be updated:
`prompt_kit.py`, `tutor_agent.py`, `query_analyzer.py`, `response_service.py`, `stream.py`,
and the LLM client itself (to accept `messages[]` instead of `prompt + system_prompt`).

**Slices:**
- L1.1: Define `MessageBuilder` — typed message list builder with role validation
- L1.2: Refactor `PromptMessages` → `MessageList` in prompt_kit.py
- L1.3: Update LLM client methods to accept `messages[]` (add new methods, keep old as compat)
- L1.4: Migrate tutor response path (stream.py, tutor_agent.py, response_service.py)
- L1.5: Migrate query analyzer to multi-message format
- L1.6: Migrate graph extraction / disambiguation to multi-message format
- L1.7: Migrate quiz grading to multi-message format
- L1.8: Migrate session compaction (summary generation) to multi-message format
- L1.9: Deprecate old `prompt + system_prompt` client methods (keep as thin wrappers)

### L2. Message Persistence & Status Tracking

**Critical UX fix.** Currently, assistant messages are only persisted after stream completion.
If the user switches tabs/conversations during generation, the message disappears and requires
a page refresh after generation completes to see both user and assistant messages.

This track adds:
- A `status` column to `chat_messages` (`generating` | `complete` | `failed` | `superseded`)
- Write-ahead insertion: placeholder assistant message with `status=generating` before
  LLM streaming begins
- Status update to `complete` or `failed` after stream finishes
- Frontend handling: display `generating` messages with a loading indicator
- Cleanup: on app startup or session load, mark stale `generating` messages as `failed`

**Slices:**
- L2.1: Add `status` column to `chat_messages` (migration + schema update)
- L2.2: Implement write-ahead placeholder in `persist_user_message()` / `persist_turn()`
- L2.3: Add `finalize_assistant_message()` and `fail_assistant_message()` DB helpers
- L2.4: Update `generate_chat_response_stream()` to use write-ahead + finalize pattern
- L2.5: Update message loading to handle `generating`/`failed`/`superseded` statuses
- L2.6: Add stale message cleanup (mark old `generating` → `failed` on startup)

### L3. LLM Client Enhancement

Adopt LiteLLM's built-in features for reliability, performance, and observability:

- **Prompt caching**: Structure system messages for OpenAI automatic prefix caching
  (1024+ token stable prefix). For Anthropic, add `cache_control` annotations. Use
  LiteLLM's `prompt_cache_key` and `prompt_cache_retention` params.
- **Token trimming**: Use `litellm.get_max_tokens()` + `litellm.token_counter()` to
  validate message length before sending. Trim oldest history messages first if over limit.
  Implement `trim_messages()` utility.
- **Reliability**: Add `num_retries`, `fallbacks`, and `context_window_fallback_dict` to
  all LiteLLM completion calls. For OpenAI SDK, implement equivalent retry/fallback logic.
- **Reasoning content**: Extract `reasoning_content` from responses (supported by Anthropic
  Claude 3.7+, DeepSeek, etc.). Pass `reasoning_effort` param. Surface reasoning in
  `GenerationTrace`.
- **Async streaming**: Migrate from `litellm.completion(stream=True)` to
  `litellm.acompletion(stream=True)` for true async streaming. Use
  `async for chunk in response` pattern.

**Slices:**
- L3.1: Implement `trim_messages()` utility using `litellm.token_counter()`
- L3.2: Structure system prompts for prompt caching (stable prefix ≥1024 tokens)
- L3.3: Add `num_retries` + `fallbacks` + `context_window_fallback_dict` to completion calls
- L3.4: Extract and surface `reasoning_content` from LLM responses
- L3.5: Migrate streaming to async (`acompletion` / `acreate`)
- L3.6: Add `cached_tokens` to `GenerationTrace` for observability

### L4. Agentic Tool Framework

Build a tool/function-calling foundation that makes CoLearni extensible toward agentic behavior.
This follows the OpenAI `tools` parameter format (supported by both LiteLLM and OpenAI SDK).

- **Tool registry**: A `ToolRegistry` that registers available tools with their JSON schemas,
  execution functions, and access policies.
- **Tool executor**: Handles tool call responses from the LLM, dispatches to registered
  handlers, and formats results back into the message chain.
- **Agent loop**: A bounded agent loop that allows the LLM to make multiple tool calls per
  turn (with a max iteration budget from `docs/CODEX.md` budget rules).
- **Built-in tools**: Initial tools for retrieval search, concept lookup, mastery check,
  and quiz generation.
- **LiteLLM integration**: Use `tools` param in `litellm.completion()` with
  `tool_choice="auto"`. Handle `tool_calls` in response.

**Slices:**
- L4.1: Define `Tool` protocol and `ToolRegistry` with schema generation from Pydantic models
- L4.2: Implement `ToolExecutor` — dispatches tool calls, formats results as tool messages
- L4.3: Implement bounded `AgentLoop` — LLM call → tool execution → repeat (max N iterations)
- L4.4: Add `tools` parameter support to LLM client methods (both providers)
- L4.5: Implement initial built-in tools: `search_knowledge_base`, `lookup_concept`, `check_mastery`
- L4.6: Wire tool framework into tutor agent (optional tool-augmented mode)

### L5. JSON Mode Standardization

Switch all structured output paths to use LiteLLM's native `response_format` parameter
instead of custom JSON parsing and prompt-based schema injection.

- Use `response_format=PydanticModel` where supported (LiteLLM auto-validates)
- Use `response_format={"type": "json_schema", "json_schema": ...}` for strict schemas
- Enable `litellm.enable_json_schema_validation = True` for client-side validation fallback
- Use `litellm.supports_response_schema()` to check model support at runtime
- Remove manual JSON extraction/parsing where native mode is available

**Slices:**
- L5.1: Audit all `_chat_json()` call sites and define Pydantic models for each schema
- L5.2: Update `_chat_json()` to use `response_format=PydanticModel` with fallback chain
- L5.3: Enable `litellm.enable_json_schema_validation` for client-side validation
- L5.4: Remove manual JSON parsing in graph extraction, disambiguation, quiz grading
- L5.5: Add runtime model support checks via `supports_response_schema()`

### L6. Message Regeneration

Add a regeneration endpoint and flow so users can re-generate an unsatisfactory response.

- **API**: `POST /workspaces/{ws_id}/chat/sessions/{session_id}/messages/{msg_id}/regenerate`
- **Flow**: Mark old assistant message as `superseded`, run a new generation using the same
  user query and current context, persist new assistant message.
- **Frontend**: Add a "Regenerate" button on assistant messages. Show the new response
  in-place, with option to view superseded version.

**Slices:**
- L6.1: Add `regenerate` endpoint in `apps/api/routes/chat.py`
- L6.2: Implement `regenerate_response()` in `domain/chat/` — marks old as superseded,
         generates new
- L6.3: Update history loading to exclude `superseded` messages from LLM context
- L6.4: Frontend regeneration button + state management (if frontend is in scope)

### L7. Graph Batch Completion

Use LiteLLM's `batch_completion()` for graph extraction to process multiple chunks in parallel.

- Replace serial `extract_raw_graph()` calls with batched requests
- Respect budget limits from `docs/GRAPH.md` (max LLM disambiguations per doc: 50)
- Handle partial failures gracefully (process successful results, retry or skip failures)

**Slices:**
- L7.1: Create `batch_extract_raw_graph()` using `litellm.batch_completion()`
- L7.2: Wire batch extraction into ingestion pipeline with budget enforcement
- L7.3: Add equivalent parallel processing for OpenAI SDK path (using `asyncio.gather`)

### L8. Web Search Integration

Add web search / research capability using LiteLLM's web search interception or explicit
tool-based search.

- Register a `web_search` tool in the ToolRegistry (from L4)
- Configure search provider (Tavily, Perplexity, or similar)
- Enable for research-type queries detected by the query analyzer
- Budget: max N web searches per chat turn

**Slices:**
- L8.1: Register `litellm_web_search` tool definition in ToolRegistry
- L8.2: Configure search provider (Tavily as default, env-based selection)
- L8.3: Wire web search into query analyzer routing (research intent → enable web search tool)
- L8.4: Add search result formatting as evidence items with `source_type=web`

## Cross-Track Execution Order

Tracks should be executed in this order. Each track's child plan defines its internal slice order.

1. `L1` Message Format Standardization — foundation for all other tracks
2. `L2` Message Persistence & Status — independent of L1 internals, can start in parallel
3. `L3` LLM Client Enhancement — depends on L1 (needs multi-message format for caching)
4. `L5` JSON Mode Standardization — depends on L1 (message format), independent of L3
5. `L4` Agentic Tool Framework — depends on L1 (message format), can parallel with L3/L5
6. `L6` Regeneration — depends on L2 (message status tracking)
7. `L7` Graph Batching — depends on L1 (message format), independent of L4
8. `L8` Web Search — depends on L4 (tool framework)

Dependencies between tracks:

- `L2` is independent and can run in parallel with `L1`
- `L3` depends on `L1` because prompt caching requires the new multi-message format
- `L4` depends on `L1` because tool calling requires proper `messages[]` format
- `L5` depends on `L1` because JSON mode uses the new client methods
- `L6` depends on `L2` because regeneration requires message status tracking
- `L7` depends on `L1` because batch extraction uses the new message builder
- `L8` depends on `L4` because web search is implemented as a tool

## Master Status Ledger

| Track | Status | Last note |
|---|---|---|
| `L1` Message Format | ✅ done | All 9 slices complete |
| `L2` Message Persistence | ✅ done | All 6 slices complete |
| `L3` LLM Client Enhancement | ✅ done | All 6 slices complete |
| `L4` Agentic Tool Framework | ✅ done | All 6 slices complete |
| `L5` JSON Mode | ✅ done | All 5 slices complete |
| `L6` Regeneration | ✅ done | All 3 slices complete |
| `L7` Graph Batching | ✅ done | All 3 slices complete |
| `L8` Web Search | ✅ done | All 4 slices complete |

## Verification Block Template

For every completed slice, include this exact structure in the child plan:

```text
Verification Block - <slice-id>

Root cause
- <what made this area insufficient?>

Files changed
- <file list>

What changed
- <short description of the changes>

Commands run
- <tests / typecheck / lint commands>

Logic review
- <For each changed file: describe what the code actually does, not just
  what you intended. Trace the data flow. Confirm edge cases are handled.
  "Tests pass" is not sufficient — explain WHY the logic is correct.>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
ruff check .
```

## What Not To Do

Do not do the following during this project:

- Do not rewrite the entire `adapters/llm/providers.py` in one PR. Refactor incrementally.
- Do not remove the OpenAI SDK path. Both providers must remain functional.
- Do not add LiteLLM Proxy Server deployment — use the SDK directly.
- Do not implement a full multi-agent conductor (deferred to `docs/agentic/`).
- Do not add new LLM providers beyond OpenAI + LiteLLM.
- Do not modify the graph extraction schema format (GRAPH.md contract).
- Do not touch frontend code unless the track explicitly requires it (L6.4 only).
- Do not remove or weaken evidence-first grounding verification.
- Do not create unbounded agent loops — every loop needs a hard budget.

## Self-Audit Convergence Protocol

After all implementation tracks reach "done" in the Master Status Ledger, the run enters a self-audit convergence loop. The agent does NOT stop — it automatically audits its own work.

### Why This Exists

Agents working top-to-bottom through a plan commonly miss edge cases, leave subtle regressions, or make assumptions that don't hold once later slices land. **Passing tests do NOT prove correctness.** Tests only check what they were written to check — they miss logic errors, silent data drops, dead code paths, and integration mismatches. This protocol forces a fresh-eyes review that catches what tests cannot.

### Fresh-Eyes Audit Principle

**The auditor must treat every slice as if it has NOT been implemented.** Do not skim Verification Blocks or trust prior claims. Instead:

1. Read the slice requirements (purpose, implementation steps, exit criteria) as if seeing them for the first time.
2. **Before looking at any code**, independently write down in the Audit Workspace:
   - What files should have been created or changed
   - What logic should exist in each file
   - What edge cases and error paths should be handled
   - What the tests should actually verify (not just "tests pass")
3. **Only then** open the actual code and compare against your independent analysis.
4. For every point in your "should-exist" list, verify it truly exists and is correct.
5. **Do not trust test names.** Open each test, read the body, and confirm it actually tests the claimed behavior with meaningful assertions — not just "no exception thrown."

### Convergence Loop

```text
AUDIT_CYCLE = 0
MAX_AUDIT_CYCLES = 3

while AUDIT_CYCLE < MAX_AUDIT_CYCLES:
    AUDIT_CYCLE += 1

    1. Re-read docs/llm/LLM_MASTER_PLAN.md and every child plan in order.
    2. For each completed slice, perform the FRESH-EYES AUDIT:
       a. Read the slice definition (purpose, steps, exit criteria).
       b. In the child plan's Audit Workspace, write your independent
          analysis of what SHOULD exist — before looking at any code.
       c. Now open every file listed in the Verification Block.
          Compare actual code against your independent analysis.
       d. For each implementation step in the slice:
          - Is the logic actually correct, or does it just not crash?
          - Are edge cases handled (empty inputs, nulls, boundaries)?
          - Is error handling meaningful (not swallowed or generic)?
          - Does the code do what the slice SAYS it does, or something
            subtly different?
       e. For each test:
          - Read the test body. Does it assert the RIGHT thing?
          - Does it test edge cases, not just the happy path?
          - Could the test pass even if the implementation is wrong?
            (e.g., mocking too much, asserting only status codes)
       f. BEHAVIORAL AUDIT (DO NOT SKIP): For each feature-facing slice,
          trace the full code path from user action → API route
          → domain logic → response. Verify:
          - The API schema accepts all required fields
          - Route handlers forward ALL fields to domain layer
          - Domain logic actually uses the forwarded fields
          - The response includes expected data
       g. PROMPT AUDIT (for any LLM-facing slice): Open the prompt template
          and verify:
          - System vs user vs assistant role assignment is correct
          - Template variables are actually populated
          - The prompt produces the expected output format
       h. OBSERVABILITY AUDIT: For any slice that touches tracing, verify
          traces show correct data in the expected panels.
       i. Cross-slice integration: does this slice's output still work
          with what later slices built on top of it?
       j. No TODO/FIXME/HACK comments left in changed files.
       k. No dead imports, unused variables, or orphaned test stubs.
    3. Run the full Verification Matrix (all test suites, typecheck, lint).
    4. Produce an Audit Report in the Audit Workspace (template below).
    5. If CONVERGED (0 issues): update Master Status Ledger with
       "✅ audit-passed" and exit the loop.
    6. If NEEDS_REPASS:
       a. Reopen affected slices (set status back to pending in the
          child plan, add "Audit Cycle N" note)
       b. Re-implement the reopened slices from scratch
       c. Continue to next audit cycle
```

### Audit Workspace

Each child plan MUST contain an `## Audit Workspace` section (initially empty). During the audit, the agent writes its fresh-eyes analysis here:

```text
--- Audit Cycle {N} - {slice-id} ---

What SHOULD exist (written BEFORE reading code):
- Files: <expected file changes>
- Logic: <expected logic in each file>
- Edge cases: <expected edge case handling>
- Tests: <what tests should verify>

What ACTUALLY exists (written AFTER reading code):
- Files: <actual file changes — match/mismatch?>
- Logic: <actual logic — correct/incorrect/missing?>
- Edge cases: <handled/missing?>
- Tests: <meaningful assertions or shallow?>

Gaps found:
- <gap 1>
- <gap 2>
- <none if clean>

Verdict: PASS / REOPEN
Reason: <if reopened, explain exactly what's wrong>
```

### Audit Cycle Budget

- **Maximum 3 audit cycles** to prevent unbounded loops.
- If cycle 3 still finds issues, produce a final Audit Report listing all remaining items and mark them as "deferred to manual review".
- The agent MUST NOT enter cycle 4.

### Audit Report Template

```text
Audit Report — Cycle {N}

Slices re-examined: {count}
Full verification matrix: {PASS / FAIL with details}

Fresh-eyes analysis completed: {yes/no for each slice}

Issues found:
1. [{severity}] {slice-id}: {description}
   - File(s): {paths}
   - Expected (from fresh analysis): {what should be true}
   - Actual (from code review): {what was found}
   - Why tests didn't catch it: {explanation}
   - Action: {reopen slice / cosmetic fix / defer}

Verdict: {CONVERGED | NEEDS_REPASS}
Slices reopened: {list or "none"}
```

### What the Audit Checks

| Check | What it catches |
|---|---|
| Fresh-eyes independent analysis | Assumptions baked in from implementation bias |
| Code logic review (not just test results) | Bugs that tests don't cover, dead code, wrong logic |
| Test body inspection | Shallow tests that pass but don't verify behavior |
| Verification Block accuracy | Slice claims that are no longer true |
| Exit criteria still met | Regressions from later slices |
| TODO/FIXME scan | Unfinished work left behind |
| Dead code scan | Imports, variables, stubs that serve no purpose |
| Behavioral trace | Dropped fields, missing kwargs, stubs |
| Prompt review | Bad role assignment, empty variables |
| Observability review | Traces that don't surface in expected panels |

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the implementation phase:

```text
Read docs/llm/LLM_MASTER_PLAN.md.
Select the first child plan in execution order that still has incomplete slices.
Read that child plan and begin with its current incomplete slice exactly as described.

Execution loop:

1. Work on exactly one sub-slice at a time and keep the change set PR-sized.
2. Preserve all constraints in docs/llm/LLM_MASTER_PLAN.md and the active child plan.
3. Run the slice verification steps before claiming completion.
4. When a slice is complete, update:
   - the active child plan with a Verification Block
   - the active child plan with any Removal Entries added during that slice
   - docs/llm/LLM_MASTER_PLAN.md with the updated status ledger / remaining status note
5. After every 2 completed slices OR if your context is compacted/summarized, re-open docs/llm/LLM_MASTER_PLAN.md and the active child plan and restate which slices remain.
6. If the active child plan still has incomplete slices, continue to the next slice.
7. If the active child plan is complete, go back to docs/llm/LLM_MASTER_PLAN.md, pick the next incomplete child plan in order, and continue.

Stop only if:

- verification fails
- the current repo behavior does not match plan assumptions and the plan must be updated first
- a blocker requires user input or approval
- completing the next slice would force a risky scope expansion

Do NOT stop because one child plan is complete.
Do NOT stop because you updated the session plan, todo list, or status ledger.
The run is only complete when docs/llm/LLM_MASTER_PLAN.md shows no remaining incomplete tracks.

Additional constraints:
- All LLM calls must work with both OpenAI SDK and LiteLLM SDK providers.
- Follow docs/CODEX.md rules: <= 400 LOC net per PR, thin routes, tests required.
- No unbounded loops in agent/tool execution (hard budget limits).
- Evidence-first: grounding verification must be preserved.

START:

Read docs/llm/LLM_MASTER_PLAN.md.
Pick the first incomplete child plan in execution order.
Begin with the current slice in that child plan exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/llm/LLM_MASTER_PLAN.md before every move to the next child plan. It can be dynamically updated. Check the latest version and continue.

--- SELF-AUDIT PHASE ---

When docs/llm/LLM_MASTER_PLAN.md shows all tracks complete (no remaining incomplete tracks),
do NOT stop. Enter the self-audit convergence loop:

Audit loop (max 3 cycles):

1. Re-read docs/llm/LLM_MASTER_PLAN.md and every child plan.
2. For each completed slice, verify the Verification Block still holds:
   - Files exist and contain the described changes
   - Tests pass (run full Verification Matrix)
   - Exit criteria are still met (no regressions from later slices)
   - No TODO/FIXME/HACK comments left in changed files
3. Check cross-slice integration:
   - Does each slice's output still work with what later slices built?
   - Are there dead imports, unused code, or orphaned tests?
4. Produce an Audit Report (use template from Self-Audit Convergence Protocol section).
5. If CONVERGED (0 issues found): mark all tracks as "audit-passed" in the
   Master Status Ledger. The run is now complete.
6. If NEEDS_REPASS: reopen affected slices, re-implement them with full
   verification, then start the next audit cycle.
7. If this is cycle 3 and issues remain: produce a final handoff report
   listing all remaining items for manual review. The run is complete.

The run is ONLY complete when:
- All tracks show "audit-passed" in the Master Status Ledger, OR
- 3 audit cycles have been exhausted and a handoff report is produced
```
