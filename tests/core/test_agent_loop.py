"""Tests for core.agent_loop — bounded agent loop."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from core.agent_loop import AgentLoop, AgentLoopResult
from core.llm_messages import Message
from core.tools import ToolExecutor, ToolRegistry


# ---------------------------------------------------------------------------
# Test tools
# ---------------------------------------------------------------------------


class _LookupParams(BaseModel):
    term: str


class _LookupTool:
    name = "lookup"
    description = "Look up a term"
    parameters_model = _LookupParams

    async def execute(self, *, term: str) -> str:
        return f"Definition of {term}: a test concept."


# ---------------------------------------------------------------------------
# Mock LLM callable
# ---------------------------------------------------------------------------


def _make_response(
    content: str = "",
    tool_calls: list[dict] | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> dict[str, Any]:
    """Build a mock LLM response dict."""
    msg: dict[str, Any] = {"content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "choices": [{"message": msg}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def _tool_call(
    name: str, arguments: dict, call_id: str = "call_1",
) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentLoop:
    def _make_loop(self, max_iter: int = 5) -> tuple[AgentLoop, ToolExecutor]:
        registry = ToolRegistry()
        registry.register(_LookupTool())
        executor = ToolExecutor(registry)
        loop = AgentLoop(tool_executor=executor, max_iterations=max_iter)
        return loop, executor

    @pytest.mark.anyio
    async def test_single_text_response(self):
        """LLM returns text immediately — 1 iteration, no tool calls."""
        loop, _ = self._make_loop()
        responses = [_make_response(content="Hello world")]
        call_count = 0

        async def mock_llm(msgs: list, tools: list) -> dict:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        result = await loop.run(
            llm_call=mock_llm,
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )
        assert result.text == "Hello world"
        assert result.iterations == 1
        assert result.tool_calls_made == 0
        assert not result.budget_exhausted

    @pytest.mark.anyio
    async def test_tool_then_text(self):
        """LLM calls a tool, gets result, then produces text."""
        loop, _ = self._make_loop()
        responses = [
            _make_response(
                tool_calls=[_tool_call("lookup", {"term": "python"})],
            ),
            _make_response(content="Python is a programming language."),
        ]
        call_count = 0

        async def mock_llm(msgs: list, tools: list) -> dict:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        result = await loop.run(
            llm_call=mock_llm,
            messages=[{"role": "user", "content": "What is Python?"}],
            tools=[{"type": "function", "function": {"name": "lookup"}}],
        )
        assert result.text == "Python is a programming language."
        assert result.iterations == 2
        assert result.tool_calls_made == 1
        assert not result.budget_exhausted
        # Messages should contain user, assistant+tool_call, tool_result, assistant
        roles = [m["role"] for m in result.messages]
        assert roles == ["user", "assistant", "tool", "assistant"]

    @pytest.mark.anyio
    async def test_budget_exhaustion(self):
        """Loop stops at max_iterations even if LLM keeps calling tools."""
        loop, _ = self._make_loop(max_iter=2)
        tool_response = _make_response(
            tool_calls=[_tool_call("lookup", {"term": "x"})],
        )

        async def mock_llm(msgs: list, tools: list) -> dict:
            return tool_response

        result = await loop.run(
            llm_call=mock_llm,
            messages=[{"role": "user", "content": "loop forever"}],
            tools=[],
        )
        assert result.budget_exhausted
        assert result.iterations == 2
        assert result.tool_calls_made == 2

    @pytest.mark.anyio
    async def test_multiple_tool_calls_per_turn(self):
        """LLM requests 2 tools in one turn."""
        loop, _ = self._make_loop()
        responses = [
            _make_response(tool_calls=[
                _tool_call("lookup", {"term": "a"}, call_id="c1"),
                _tool_call("lookup", {"term": "b"}, call_id="c2"),
            ]),
            _make_response(content="Done!"),
        ]
        call_count = 0

        async def mock_llm(msgs: list, tools: list) -> dict:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        result = await loop.run(
            llm_call=mock_llm,
            messages=[{"role": "user", "content": "look up a and b"}],
            tools=[],
        )
        assert result.text == "Done!"
        assert result.tool_calls_made == 2
        assert result.iterations == 2
        # Should have 2 tool result messages
        tool_msgs = [m for m in result.messages if m["role"] == "tool"]
        assert len(tool_msgs) == 2

    @pytest.mark.anyio
    async def test_token_usage_accumulation(self):
        """Token usage is summed across iterations."""
        loop, _ = self._make_loop()
        responses = [
            _make_response(
                tool_calls=[_tool_call("lookup", {"term": "x"})],
                prompt_tokens=100, completion_tokens=20,
            ),
            _make_response(
                content="final",
                prompt_tokens=150, completion_tokens=30,
            ),
        ]
        call_count = 0

        async def mock_llm(msgs: list, tools: list) -> dict:
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        result = await loop.run(
            llm_call=mock_llm,
            messages=[{"role": "user", "content": "test"}],
            tools=[],
        )
        assert result.total_prompt_tokens == 250
        assert result.total_completion_tokens == 50

    @pytest.mark.anyio
    async def test_empty_choices(self):
        """Empty choices list returns empty text."""
        loop, _ = self._make_loop()

        async def mock_llm(msgs: list, tools: list) -> dict:
            return {"choices": [], "usage": {}}

        result = await loop.run(
            llm_call=mock_llm,
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
        )
        assert result.text == ""
        assert result.iterations == 1

    @pytest.mark.anyio
    async def test_does_not_mutate_input(self):
        """Input messages list is not modified."""
        loop, _ = self._make_loop()

        async def mock_llm(msgs: list, tools: list) -> dict:
            return _make_response(content="ok")

        original = [{"role": "user", "content": "hi"}]
        original_len = len(original)
        await loop.run(llm_call=mock_llm, messages=original, tools=[])
        assert len(original) == original_len

    def test_invalid_max_iterations(self):
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        with pytest.raises(ValueError, match="max_iterations"):
            AgentLoop(tool_executor=executor, max_iterations=0)
