"""Tests for core.tools — Tool protocol, ToolRegistry, and ToolExecutor."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from core.tools import Tool, ToolExecutor, ToolRegistry


# ---------------------------------------------------------------------------
# Helpers — concrete tool implementations for testing
# ---------------------------------------------------------------------------


class _SearchParams(BaseModel):
    query: str
    top_k: int = 5


class _SearchTool:
    """Concrete tool for testing."""

    name = "search"
    description = "Search the knowledge base"
    parameters_model = _SearchParams

    async def execute(self, *, query: str, top_k: int = 5) -> str:
        return json.dumps({"results": [f"result for '{query}'"], "count": top_k})


class _EmptyParams(BaseModel):
    pass


class _GreetTool:
    """Tool with no parameters."""

    name = "greet"
    description = "Say hello"
    parameters_model = _EmptyParams

    async def execute(self) -> str:
        return "Hello!"


class _FailingTool:
    """Tool that always raises."""

    name = "fail"
    description = "Always fails"
    parameters_model = _EmptyParams

    async def execute(self) -> str:
        raise RuntimeError("Intentional failure")


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = _SearchTool()
        registry.register(tool)
        assert registry.get("search") is tool
        assert len(registry) == 1
        assert "search" in registry

    def test_get_unknown_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_duplicate_name_raises(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_SearchTool())

    def test_list_tools(self):
        registry = ToolRegistry()
        s = _SearchTool()
        g = _GreetTool()
        registry.register(s)
        registry.register(g)
        assert registry.list_tools() == [s, g]

    def test_contains(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        assert "search" in registry
        assert "missing" not in registry

    def test_to_openai_tools_format(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        tools = registry.to_openai_tools()

        assert len(tools) == 1
        tool_spec = tools[0]
        assert tool_spec["type"] == "function"
        func = tool_spec["function"]
        assert func["name"] == "search"
        assert func["description"] == "Search the knowledge base"

        params = func["parameters"]
        assert "properties" in params
        assert "query" in params["properties"]
        assert "top_k" in params["properties"]
        # Pydantic "title" should be stripped
        assert "title" not in params

    def test_to_openai_tools_multiple(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        registry.register(_GreetTool())
        tools = registry.to_openai_tools()
        assert len(tools) == 2
        names = [t["function"]["name"] for t in tools]
        assert names == ["search", "greet"]

    def test_to_openai_tools_empty_registry(self):
        registry = ToolRegistry()
        assert registry.to_openai_tools() == []

    def test_tool_protocol_check(self):
        assert isinstance(_SearchTool(), Tool)


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------


class TestToolExecutor:
    def _make_tool_call(
        self, *, tool_id: str = "call_1", name: str, arguments: str,
    ) -> dict:
        return {
            "id": tool_id,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }

    @pytest.mark.anyio
    async def test_execute_valid_tool_call(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        executor = ToolExecutor(registry)

        calls = [self._make_tool_call(
            name="search", arguments='{"query": "python", "top_k": 3}',
        )]
        results = await executor.execute_tool_calls(calls)

        assert len(results) == 1
        msg = results[0]
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_1"
        parsed = json.loads(msg["content"])
        assert parsed["results"] == ["result for 'python'"]
        assert parsed["count"] == 3

    @pytest.mark.anyio
    async def test_execute_tool_with_defaults(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        executor = ToolExecutor(registry)

        calls = [self._make_tool_call(
            name="search", arguments='{"query": "test"}',
        )]
        results = await executor.execute_tool_calls(calls)
        parsed = json.loads(results[0]["content"])
        assert parsed["count"] == 5  # default top_k

    @pytest.mark.anyio
    async def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        calls = [self._make_tool_call(name="missing", arguments="{}")]
        results = await executor.execute_tool_calls(calls)

        assert len(results) == 1
        parsed = json.loads(results[0]["content"])
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    @pytest.mark.anyio
    async def test_execute_invalid_json(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        executor = ToolExecutor(registry)

        calls = [self._make_tool_call(name="search", arguments="not json")]
        results = await executor.execute_tool_calls(calls)

        parsed = json.loads(results[0]["content"])
        assert "error" in parsed
        assert "Invalid arguments JSON" in parsed["error"]

    @pytest.mark.anyio
    async def test_execute_invalid_arguments(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        executor = ToolExecutor(registry)

        # Missing required 'query' field
        calls = [self._make_tool_call(name="search", arguments='{"top_k": 3}')]
        results = await executor.execute_tool_calls(calls)

        parsed = json.loads(results[0]["content"])
        assert "error" in parsed
        assert "Invalid arguments" in parsed["error"]

    @pytest.mark.anyio
    async def test_execute_failing_tool(self):
        registry = ToolRegistry()
        registry.register(_FailingTool())
        executor = ToolExecutor(registry)

        calls = [self._make_tool_call(name="fail", arguments="{}")]
        results = await executor.execute_tool_calls(calls)

        parsed = json.loads(results[0]["content"])
        assert "error" in parsed
        assert "execution failed" in parsed["error"]

    @pytest.mark.anyio
    async def test_execute_multiple_tool_calls(self):
        registry = ToolRegistry()
        registry.register(_SearchTool())
        registry.register(_GreetTool())
        executor = ToolExecutor(registry)

        calls = [
            self._make_tool_call(
                tool_id="c1", name="search", arguments='{"query": "a"}',
            ),
            self._make_tool_call(
                tool_id="c2", name="greet", arguments="{}",
            ),
        ]
        results = await executor.execute_tool_calls(calls)

        assert len(results) == 2
        assert results[0]["tool_call_id"] == "c1"
        assert results[1]["tool_call_id"] == "c2"
        assert results[1]["content"] == "Hello!"

    @pytest.mark.anyio
    async def test_execute_empty_arguments(self):
        registry = ToolRegistry()
        registry.register(_GreetTool())
        executor = ToolExecutor(registry)

        calls = [self._make_tool_call(name="greet", arguments="")]
        results = await executor.execute_tool_calls(calls)
        assert results[0]["content"] == "Hello!"
