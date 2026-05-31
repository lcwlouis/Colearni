# Agent Prompt: Consolidation Item 3 — Phase 11 LLM Tool Calling Loop

## Context

Read `docs/CONSOLIDATION_PLAN.md` Item 3 before proceeding.

Phase 11 registered three retrieval tool definitions and built service functions for them.
The tutor's chat loop only invokes one tool today (`get_tutor_instructions` via a
compatibility adapter). The retrieval tools (`search_sources`, `get_concept_sources`,
`get_graph_neighbourhood`) are registered but never called. This item wires them in through
a bounded, parallel tool-call loop and adds a fourth tool: `read_document_section`.

Item 2 must be complete before running this item — `read_document_section` reads from
`SourceRevision.raw_text` (populated by the parser), and `search_sources` dispatches to
`search_sources_by_text` (returns `ChunkSearchResult` objects with line navigation metadata).

---

## Mandatory reads before writing any code

- `docs/AGENTS.md` — repo rules, git policy, constraints.
- `docs/CODEX.md` — code standards.
- `docs/CONSOLIDATION_PLAN.md` Item 3 — full scope, dual-retrieval architecture, acceptance criteria.
- `backend/app/services/conversations.py` — full file; understand `TutorContext`, existing
  tool turn pattern, how the current instruction tool is invoked.
- `backend/app/agents/provider_tools.py` — `NormalizedStreamEvent`, `NormalizedToolCall`,
  `NormalizedToolResult`, `AnthropicStreamState`, `ProviderToolDefinition`.
- `backend/app/agents/retrieval_tools.py` — existing three `ProviderToolDefinition` objects.
- `backend/app/agents/llm_client.py` — `chat_stream_tagged`, `chat_tool_stream` (or equivalent
  streaming interface); understand how tool calls surface from the stream.
- `backend/app/services/retrieval.py` — `search_sources_by_text`, `get_concept_sources_for_tutor`,
  `get_graph_neighbourhood` (after Item 2 changes).
- `backend/app/models/source.py` — `SourceRevision` (has `raw_text`), `SourceChunk`.
- `backend/app/models/conversation.py` — `ConversationTurn` (kind, role fields).
- `backend/app/api/concepts.py` or wherever the chat SSE endpoint lives.
- `backend/tests/test_conversations.py` or nearest existing conversation test.
- `docs/CURRENT_VARIANT.md` — deferred items list to update when complete.

---

## Exact changes required

### 1. Add `READ_DOCUMENT_SECTION_TOOL` — `backend/app/agents/retrieval_tools.py`

Add a fourth `ProviderToolDefinition`:

```python
READ_DOCUMENT_SECTION_TOOL = ProviderToolDefinition(
    name="read_document_section",
    description=(
        "Read a window of lines from a source document starting at a given line number. "
        "Use the line_start value returned by search_sources to navigate to a relevant "
        "section. Returns markdown-formatted text from that location in the document. "
        "Never returns raw file content, object keys, or hashes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_revision_id": {
                "type": "string",
                "description": "UUID of the source revision to read from.",
            },
            "line_start": {
                "type": "integer",
                "description": "1-indexed line number to start reading from.",
            },
            "window_lines": {
                "type": "integer",
                "description": "Number of lines to read (default 50, max 200).",
            },
        },
        "required": ["source_revision_id", "line_start"],
        "additionalProperties": False,
    },
    public_argument_fields=("source_revision_id", "line_start", "window_lines"),
)
```

Update `RETRIEVAL_TOOLS` to include all four:

```python
RETRIEVAL_TOOLS = [
    GET_CONCEPT_SOURCES_TOOL,
    GET_GRAPH_NEIGHBOURHOOD_TOOL,
    SEARCH_SOURCES_TOOL,
    READ_DOCUMENT_SECTION_TOOL,
]
```

Also update `SEARCH_SOURCES_TOOL` description to reflect that it now searches chunk text
(not just titles) and returns line navigation metadata:

```python
SEARCH_SOURCES_TOOL = ProviderToolDefinition(
    name="search_sources",
    description=(
        "Search source document chunks by keyword within the current workspace. "
        "Returns chunk metadata including section_heading, line_start, and line_end "
        "so you can call read_document_section for fuller context. "
        "Optionally scoped to a concept. Returns metadata only — never raw content."
    ),
    parameters={...},  # same as before
    ...
)
```

### 2. Add `read_document_section` service function — `backend/app/services/retrieval.py`

```python
async def read_document_section(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    source_revision_id: uuid.UUID,
    line_start: int,
    window_lines: int = 50,
) -> str:
    """Read a window of lines from SourceRevision.raw_text.

    Returns the markdown text of lines [line_start, line_start + window_lines).
    Line numbers are 1-indexed.

    Raises LookupError if the revision does not exist or belongs to a different workspace.
    Raises ValueError if line_start < 1 or window_lines < 1.
    """
    _WINDOW_MAX = 200
    if line_start < 1:
        raise ValueError("line_start must be >= 1")
    if window_lines < 1 or window_lines > _WINDOW_MAX:
        window_lines = min(max(window_lines, 1), _WINDOW_MAX)

    revision = await session.scalar(
        select(SourceRevision).where(
            SourceRevision.id == source_revision_id,
            SourceRevision.workspace_id == workspace_id,
        )
    )
    if revision is None:
        raise LookupError(f"Source revision {source_revision_id} not found")

    raw_text = revision.raw_text or ""
    lines = raw_text.splitlines()
    start_idx = line_start - 1  # convert to 0-indexed
    end_idx = start_idx + window_lines
    window = lines[start_idx:end_idx]
    return "\n".join(window)
```

Import `SourceRevision` from `backend.app.models.source`.

### 3. Tool executor — new function in `backend/app/services/conversations.py`

Add a `execute_retrieval_tool` async function that dispatches `NormalizedToolCall` objects
to the correct service function and returns a `NormalizedToolResult`:

```python
async def execute_retrieval_tool(
    tool_call: NormalizedToolCall,
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> NormalizedToolResult:
    """Dispatch a retrieval tool call and return a normalized result.

    Enforces workspace scope on all calls. Returns an error result on
    any exception — does not re-raise (the loop continues safely).
    """
    try:
        if not tool_call.is_valid:
            raise ValueError(f"Invalid tool arguments: {tool_call.validation_error}")

        if tool_call.name == "search_sources":
            query = tool_call.arguments["query"]
            cid = tool_call.arguments.get("concept_id")
            results = await search_sources_by_text(
                query=query,
                workspace_id=workspace_id,
                session=session,
            )
            content = _format_chunk_results(results)

        elif tool_call.name == "get_concept_sources":
            cid = uuid.UUID(tool_call.arguments["concept_id"])
            sources = await get_concept_sources_for_tutor(
                session=session,
                workspace_id=workspace_id,
                concept_id=cid,
            )
            content = _format_source_list(sources)

        elif tool_call.name == "get_graph_neighbourhood":
            # graph neighbourhood is pre-loaded in context — no DB call needed
            # caller must pass context; for now call the service directly
            cid = uuid.UUID(tool_call.arguments["concept_id"])
            content = await _get_neighbourhood_for_concept(session, workspace_id, cid)

        elif tool_call.name == "read_document_section":
            rev_id = uuid.UUID(tool_call.arguments["source_revision_id"])
            line_start = int(tool_call.arguments["line_start"])
            window_lines = int(tool_call.arguments.get("window_lines", 50))
            content = await read_document_section(
                session=session,
                workspace_id=workspace_id,
                source_revision_id=rev_id,
                line_start=line_start,
                window_lines=window_lines,
            )

        else:
            content = f"Unknown tool: {tool_call.name}"

    except Exception as exc:
        return NormalizedToolResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            content=f"Tool error: {exc}",
            is_error=True,
            public_preview={"error": str(exc)},
        )

    # Truncate oversized results
    content = _truncate_tool_result(content)

    return NormalizedToolResult(
        call_id=tool_call.call_id,
        name=tool_call.name,
        content=content,
        public_preview={"preview": content[:200]},
    )
```

Constants:
```python
_MAX_TOOL_RESULT_CHARS = 2000
_TOOL_CALL_BUDGET = 3

def _truncate_tool_result(content: str) -> str:
    if len(content) <= _MAX_TOOL_RESULT_CHARS:
        return content
    return content[:_MAX_TOOL_RESULT_CHARS] + " ... [truncated]"
```

Helper formatters:
```python
def _format_chunk_results(results: list[ChunkSearchResult]) -> str:
    """Format ChunkSearchResult list for LLM context. Includes line navigation hints."""
    if not results:
        return "No matching chunks found."
    parts = []
    for r in results:
        heading = f" (section: {r.section_heading})" if r.section_heading else ""
        parts.append(
            f"Source: {r.source_title}{heading}\n"
            f"Lines {r.line_start}–{r.line_end} | revision: {r.source_revision_id}\n"
            f"{r.chunk_text[:500]}"
        )
    return "\n\n---\n\n".join(parts)

def _format_source_list(sources: list[TutorSourceMetadata]) -> str:
    if not sources:
        return "No sources linked to this concept."
    return "\n".join(
        f"- {s.title} [{s.relation}] ({s.origin}, {s.access})"
        for s in sources
    )
```

Import `search_sources_by_text`, `get_concept_sources_for_tutor`, `get_graph_neighbourhood`,
`read_document_section` from `backend.app.services.retrieval`.
Import `ChunkSearchResult` from `backend.app.services.reranker`.
Import `NormalizedToolCall`, `NormalizedToolResult` from `backend.app.agents.provider_tools`.

### 4. Parallel tool-call loop — in the tutor streaming function

Find where the tutor streaming response is generated in `backend/app/services/conversations.py`
(or the agent module it delegates to). After the initial instruction-tool turn, add the
bounded retrieval loop before streaming the final visible response.

The loop collects all `NormalizedStreamEvent` objects from one LLM call, checks for tool
calls, executes them in parallel, and feeds results back. It exits when:
- No tool calls in a response (LLM is done — stream text to client).
- Budget is exhausted (cap reached — proceed to final response without more tool turns).

```python
async def _run_retrieval_loop(
    messages: list[dict],
    tools: list[ProviderToolDefinition],
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    llm_client: LLMClient,
) -> tuple[list[dict], list[NormalizedToolResult]]:
    """Run the bounded retrieval tool loop.

    Returns (updated_messages, all_tool_results_emitted) after the loop exits.
    Callers use all_tool_results for SSE emission and persistence.
    """
    budget = _TOOL_CALL_BUDGET
    all_results: list[NormalizedToolResult] = []
    dedup_cache: dict[tuple[str, str], NormalizedToolResult] = {}

    while budget > 0:
        events: list[NormalizedStreamEvent] = []
        async for event in llm_client.chat_tool_stream(messages, tools=tools):
            events.append(event)

        tool_calls = [e.tool_call for e in events if e.kind == "tool_call" and e.tool_call]
        if not tool_calls:
            break  # LLM returned text — exit loop; caller streams final response

        # Deduplicate: same name + same args → return cached result
        unique_calls: list[NormalizedToolCall] = []
        for tc in tool_calls:
            cache_key = (tc.name, json.dumps(tc.arguments, sort_keys=True))
            if cache_key in dedup_cache:
                all_results.append(dedup_cache[cache_key])
            else:
                unique_calls.append(tc)

        # Cap to remaining budget
        unique_calls = unique_calls[:budget]
        budget -= len(unique_calls)

        # Execute all calls concurrently
        new_results = await asyncio.gather(*[
            execute_retrieval_tool(tc, session=session,
                                   workspace_id=workspace_id, concept_id=concept_id)
            for tc in unique_calls
        ])

        for tc, result in zip(unique_calls, new_results):
            cache_key = (tc.name, json.dumps(tc.arguments, sort_keys=True))
            dedup_cache[cache_key] = result
            all_results.append(result)

        # Append tool round to messages
        messages = _append_tool_round(messages, unique_calls, list(new_results))

    return messages, all_results
```

`_append_tool_round` builds the provider-specific message structure for a tool round
(assistant message with tool_calls + tool result messages). Follow the existing pattern
used for the instruction tool turn.

The tool offer condition: only pass `RETRIEVAL_TOOLS` when `len(context.sources) > 0`.
When sources is empty, pass an empty tools list (or omit the parameter).

### 5. SSE event emission

For each tool result in `all_results`, emit:
1. A `tool_call` SSE event before execution (sanitized: tool name + public argument fields).
2. A `tool_result` SSE event after execution (sanitized preview — never raw content).

Follow the exact same SSE event structure used for the existing instruction tool calls.

### 6. Persistence of tool turns

For each tool round in the loop, persist two `ConversationTurn` rows:
1. `role="assistant"`, `kind="tool_call"` — the LLM's tool call request.
2. `role="tool"`, `kind="tool_result"` — the result returned to the LLM.

Both rows must be `visible=False` (hidden from the learner-facing conversation history but
included in prompt replay). Follow the exact same persistence pattern used for the
instruction tool turns.

### 7. Update `docs/CURRENT_VARIANT.md`

Find the deferred item for the LLM tool calling loop and mark it complete. Add a note
that `read_document_section` (line-based) is the fourth retrieval tool.

---

## Tests

Add to `backend/tests/test_conversations.py` (or create `backend/tests/test_tool_loop.py`):

### Test: two tool calls in one response → both executed, budget decremented by 2

```python
async def test_tool_loop_parallel_calls(fake_llm_two_tool_calls):
    # fake provider emits two search_sources calls in one response
    # assert both execute_retrieval_tool calls are made
    # assert budget after = TOOL_CALL_BUDGET - 2
```

### Test: budget exhaustion caps calls

```python
async def test_tool_loop_budget_cap():
    # provider returns 4 tool calls; TOOL_CALL_BUDGET=3
    # assert only 3 calls are executed; 4th is dropped
```

### Test: duplicate call returns cached result

```python
async def test_tool_loop_dedup():
    # provider returns same tool+args twice
    # assert execute_retrieval_tool called once, not twice
    # assert second result matches first (from cache)
```

### Test: no tool call exits loop immediately

```python
async def test_tool_loop_no_calls():
    # provider returns only text event
    # assert loop exits immediately (budget unused)
```

### Test: malformed tool arguments → error result, loop continues

```python
async def test_tool_loop_bad_args():
    # provider returns tool call with invalid args
    # assert NormalizedToolResult.is_error == True
    # assert loop does not raise; subsequent calls proceed
```

### Test: tools NOT offered when sources empty

```python
async def test_tool_offer_condition_empty_sources(monkeypatch):
    # context.sources = []
    # assert RETRIEVAL_TOOLS are not passed to llm_client
```

### Test: `read_document_section` returns correct lines

```python
async def test_read_document_section_lines(db_session):
    # insert SourceRevision with raw_text = "line1\nline2\nline3\nline4\nline5"
    # read_document_section(line_start=2, window_lines=3) → "line2\nline3\nline4"
```

### Test: `read_document_section` rejects wrong workspace

```python
async def test_read_document_section_wrong_workspace(db_session):
    # revision belongs to workspace A; request with workspace B → LookupError
```

---

## Verification

```bash
# Backend tests
python -m pytest backend/tests/ -q

# Ruff lint
python -m ruff check backend/app/

# Frontend is unchanged
```

All 349+ existing backend tests must still pass. The lint run should show no new errors
beyond the 7 known pre-existing ones.

---

## Constraints

- Do **not** commit or push. Stop after implementing and verifying. The user will review.
- FastAPI routes must stay thin. The tool loop lives in the service layer, not the route.
- `TOOL_CALL_BUDGET = 3` counts individual tool executions, not loop iterations.
- Each tool result must be truncated to `MAX_TOOL_RESULT_CHARS = 2000` before entering context.
- `read_document_section` must reject cross-workspace access (raise LookupError).
- Parallel execution uses `asyncio.gather` — do NOT call tools sequentially.
- The existing instruction-tool turn (mode selection) is NOT inside the retrieval loop —
  the loop runs after mode selection.
- Do not modify frontend files.
- Do not modify the Trail Pack export path.
- The tool loop must handle a missing or empty `raw_text` gracefully (return empty string,
  not an error, from `read_document_section`).
- The loop must never raise an unhandled exception due to a single bad tool call — degrade
  safely and continue.

---

## Deliverable

When done, report:

1. Which files were changed or created, with a one-line summary of each.
2. Backend test count (must be 349+, higher after new tests).
3. Ruff output (pre-existing errors fine; no new errors).
4. A description of how the dual-retrieval pattern works end-to-end (search → line_start → read).
5. Any scope that was not completed and why.

The user will review before any commit is made.
