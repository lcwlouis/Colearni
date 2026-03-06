# L4 — Agentic Tool Framework

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Dependencies: L1 ✅ (MessageBuilder with tool role support)

## Goal

Build a tool/function-calling foundation that makes CoLearni extensible toward
agentic behavior. Follows the OpenAI `tools` parameter format (supported by
both LiteLLM and OpenAI SDK). Includes a bounded agent loop with hard budget
limits per docs/CODEX.md.

## Slice Status

| Slice | Description | Status |
|-------|-------------|--------|
| L4.1 | Define `Tool` protocol and `ToolRegistry` with schema generation | ✅ done |
| L4.2 | Implement `ToolExecutor` — dispatch tool calls, format results | ✅ done |
| L4.3 | Implement bounded `AgentLoop` — LLM → tool → repeat (max N) | ✅ done |
| L4.4 | Add `tools` parameter support to LLM client methods | ✅ done |
| L4.5 | Implement built-in tools: search, lookup_concept, check_mastery | ✅ done |
| L4.6 | Wire tool framework into tutor agent (optional tool mode) | ✅ done — `tool_augmented.py` + `response_service.py` integration, feature-flagged |

---

## L4.1 — Tool Protocol and ToolRegistry

**File**: `core/tools.py`

Define the `Tool` protocol and `ToolRegistry`:

```python
class Tool(Protocol):
    name: str
    description: str
    parameters_schema: type[BaseModel]  # Pydantic model for JSON schema
    
    async def execute(self, **kwargs) -> str: ...

class ToolRegistry:
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool | None: ...
    def to_openai_tools(self) -> list[dict]: ...  # OpenAI tools format
```

- Schema generation uses `model.model_json_schema()` (Pydantic v2)
- `to_openai_tools()` produces the `[{"type": "function", "function": {...}}]` format
- Registry is immutable after construction (thread-safe reads)

**Tests**: `tests/core/test_tools.py`
- Register tools, generate schemas, retrieve by name
- Verify OpenAI tools format output

**Exit criteria**: `ToolRegistry.to_openai_tools()` produces valid OpenAI-compatible tool specs.

---

## L4.2 — ToolExecutor

**File**: `core/tools.py` (extend)

```python
class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None: ...
    
    async def execute_tool_calls(
        self,
        tool_calls: list[dict],
    ) -> list[Message]:
        """Execute each tool call and return tool-result messages."""
```

- Parses `tool_calls[].function.arguments` (JSON string → dict)
- Validates against Pydantic parameters schema
- Calls `tool.execute(**validated_args)`
- Returns `Message(role="tool", content=result, tool_call_id=id)`
- On tool execution error: returns error message (does not raise)

**Tests**: `tests/core/test_tools.py`
- Execute valid tool calls → correct messages
- Invalid arguments → error message returned
- Unknown tool name → error message returned

**Exit criteria**: `ToolExecutor` correctly dispatches and formats results.

---

## L4.3 — Bounded AgentLoop

**File**: `core/agent_loop.py`

```python
class AgentLoop:
    def __init__(
        self,
        llm_client: _BaseGraphLLMClient,
        tool_executor: ToolExecutor,
        max_iterations: int = 5,  # budget from CODEX.md
    ) -> None: ...
    
    async def run(
        self,
        messages: list[Message],
        tools: list[dict],
        **llm_kwargs,
    ) -> tuple[str, list[Message], GenerationTrace]:
        """Run LLM → tool → LLM loop until final text or budget exhausted."""
```

- Each iteration: call LLM → if tool_calls in response, execute them, append
  tool results to messages, repeat
- If response has no tool_calls, return the text content
- Hard stop at `max_iterations` — return whatever partial response exists
- Tracks total token usage across iterations in GenerationTrace

**Tests**: `tests/core/test_agent_loop.py`
- Mock LLM that returns tool calls then text → loop terminates correctly
- Budget exhaustion → stops at max_iterations
- No tool calls on first response → single iteration

**Exit criteria**: AgentLoop respects max_iterations budget and terminates.

---

## L4.4 — Tools Parameter in LLM Client

**File**: `adapters/llm/providers.py`

Add `tools` and `tool_choice` parameters to:
- `_sdk_call()` / `_async_sdk_call()`
- `complete_messages()`
- `stream_messages()`

Both OpenAI SDK and LiteLLM SDK support the same `tools` format natively.
Pass through to the SDK call. Return `tool_calls` from response message when
present.

**Tests**: `tests/adapters/test_graph_llm_provider.py`
- Verify `tools` param is passed through to SDK
- Verify `tool_calls` extracted from response

**Exit criteria**: Both providers accept and pass through `tools` parameter.

---

## L4.5 — Built-in Tools

**File**: `domain/tools/` (new package)
- `domain/tools/__init__.py`
- `domain/tools/search_knowledge.py` — `search_knowledge_base` tool
- `domain/tools/lookup_concept.py` — `lookup_concept` tool
- `domain/tools/check_mastery.py` — `check_mastery` tool

Each tool:
- Has a Pydantic model for parameters
- Has an async `execute()` method
- Returns a string result (formatted for LLM consumption)
- Delegates to existing domain services (retrieval, graph, learner profile)

**Tests**: `tests/domain/test_tools.py`
- Each tool with mocked dependencies
- Parameter validation
- Error handling

**Exit criteria**: 3 built-in tools registered and tested.

---

## L4.6 — Wire into Tutor Agent

**File**: `domain/chat/tutor_agent.py`

Add optional tool-augmented mode:
- When tools are available, pass them to `complete_messages()`
- Use AgentLoop for multi-turn tool calling
- Feature-flagged: only activate when `settings.enable_tool_calling` is True

**Tests**: `tests/domain/test_tutor_agent.py`
- Tool-augmented mode produces tool calls
- Non-tool mode unchanged (regression check)

**Exit criteria**: Tutor agent can optionally use tools with bounded loop.

---

## Removal Entries

(To be filled as slices complete)

## Verification Blocks

(To be filled as slices complete)
