"""Tests for domain.chat.tool_augmented — tool-augmented LLM generation."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.agent_loop import AgentLoopResult
from core.llm_messages import Message
from core.schemas.assistant import GenerationTrace
from core.tools import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_llm_response(
    content: str = "Hello!",
    tool_calls: list[dict[str, Any]] | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> dict[str, Any]:
    """Build a minimal OpenAI-format response dict."""
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "choices": [{"message": msg}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


class _StubLLMClient:
    """Minimal stub exposing _call_with_observability and _tutor_temperature."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [_fake_llm_response()])
        self._call_count = 0
        self._tutor_temperature = 0.7

    def _call_with_observability(self, **kwargs: Any) -> dict[str, Any]:
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]

    def complete_messages(
        self, messages: Any, *, prompt_meta: Any = None, **kw: Any
    ) -> tuple[str, GenerationTrace]:
        resp = self._call_with_observability(messages=messages)
        text = resp["choices"][0]["message"].get("content", "")
        return text, GenerationTrace()


def _simple_messages() -> list[Message]:
    return [
        {"role": "system", "content": "You are a tutor."},
        {"role": "user", "content": "What is recursion?"},
    ]


def _empty_registry() -> ToolRegistry:
    return ToolRegistry()


def _registry_with_dummy_tool() -> ToolRegistry:
    """Registry with one no-op tool."""
    from pydantic import BaseModel

    class _Params(BaseModel):
        query: str = "test"

    class _DummyTool:
        name = "dummy_tool"
        description = "A dummy tool for testing"
        parameters_model = _Params

        async def execute(self, **kwargs: Any) -> str:
            return json.dumps({"result": "dummy_result"})

    registry = ToolRegistry()
    registry.register(_DummyTool())
    return registry


# ---------------------------------------------------------------------------
# generate_with_tools
# ---------------------------------------------------------------------------


class TestGenerateWithTools:
    """Tests for the sync entry point ``generate_with_tools``."""

    def test_simple_text_response(self) -> None:
        from domain.chat.tool_augmented import generate_with_tools

        result = generate_with_tools(
            messages=_simple_messages(),
            llm_client=_StubLLMClient(),
            tool_registry=_registry_with_dummy_tool(),
            max_iterations=3,
        )
        assert isinstance(result, AgentLoopResult)
        assert result.text == "Hello!"
        assert result.iterations == 1
        assert result.tool_calls_made == 0

    def test_tool_call_then_text(self) -> None:
        """LLM makes one tool call, then produces a final text response."""
        from domain.chat.tool_augmented import generate_with_tools

        tool_call_response = _fake_llm_response(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {
                        "name": "dummy_tool",
                        "arguments": json.dumps({"query": "test"}),
                    },
                }
            ],
        )
        final_response = _fake_llm_response(content="Recursion is self-reference.")
        client = _StubLLMClient(responses=[tool_call_response, final_response])

        result = generate_with_tools(
            messages=_simple_messages(),
            llm_client=client,
            tool_registry=_registry_with_dummy_tool(),
            max_iterations=5,
        )
        assert result.text == "Recursion is self-reference."
        assert result.iterations == 2
        assert result.tool_calls_made == 1
        assert not result.budget_exhausted

    def test_budget_exhausted(self) -> None:
        """Loop stops after max_iterations even if LLM keeps calling tools."""
        from domain.chat.tool_augmented import generate_with_tools

        tool_call_response = _fake_llm_response(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {
                        "name": "dummy_tool",
                        "arguments": json.dumps({"query": "q"}),
                    },
                }
            ],
        )
        # Return tool calls every time — never a final text
        client = _StubLLMClient(responses=[tool_call_response])

        result = generate_with_tools(
            messages=_simple_messages(),
            llm_client=client,
            tool_registry=_registry_with_dummy_tool(),
            max_iterations=2,
        )
        assert result.budget_exhausted
        assert result.iterations == 2

    def test_raises_for_incompatible_client(self) -> None:
        from domain.chat.tool_augmented import generate_with_tools

        bad_client = MagicMock(spec=[])  # no _call_with_observability

        with pytest.raises(TypeError, match="does not expose"):
            generate_with_tools(
                messages=_simple_messages(),
                llm_client=bad_client,
                tool_registry=_registry_with_dummy_tool(),
            )


# ---------------------------------------------------------------------------
# _try_tool_augmented (via generate_tutor_text)
# ---------------------------------------------------------------------------


class TestToolAugmentedIntegration:
    """Test the feature-flag gating in generate_tutor_text."""

    def test_skipped_when_flag_disabled(self) -> None:
        """Tool path is not entered when enable_tool_calling is False."""
        from domain.chat.response_service import generate_tutor_text

        mock_settings = MagicMock()
        mock_settings.enable_tool_calling = False

        with patch("domain.chat.response_service.get_settings", return_value=mock_settings):
            text, trace = generate_tutor_text(
                query="hello",
                evidence=[],
                mastery_status=None,
                grounding_mode="hybrid",
                llm_client=None,
                history_text="",
                assessment_context="",
            )
        # Falls through to template fallback (no LLM client)
        assert isinstance(text, str)

    def test_skipped_when_no_llm_client(self) -> None:
        """Tool path is not entered when llm_client is None."""
        from domain.chat.response_service import generate_tutor_text

        mock_settings = MagicMock()
        mock_settings.enable_tool_calling = True

        with patch("domain.chat.response_service.get_settings", return_value=mock_settings):
            text, trace = generate_tutor_text(
                query="hello",
                evidence=[],
                mastery_status=None,
                grounding_mode="hybrid",
                llm_client=None,
                history_text="",
                assessment_context="",
            )
        assert isinstance(text, str)

    def test_tool_path_used_when_enabled(self) -> None:
        """When flag is on and tools exist, generate_with_tools is called."""
        from domain.chat.response_service import generate_tutor_text

        mock_settings = MagicMock()
        mock_settings.enable_tool_calling = True
        mock_settings.agent_max_iterations = 3
        mock_settings.web_search_api_key = None
        mock_settings.web_search_max_results = 5

        loop_result = AgentLoopResult(
            text="Tool-augmented answer",
            messages=[],
            iterations=1,
            tool_calls_made=1,
            total_prompt_tokens=20,
            total_completion_tokens=15,
        )

        client = _StubLLMClient()
        dummy_registry = _registry_with_dummy_tool()

        with (
            patch("domain.chat.response_service.get_settings", return_value=mock_settings),
            patch(
                "domain.tools.registry_factory.build_tool_registry",
                return_value=dummy_registry,
            ),
            patch(
                "domain.chat.tool_augmented.generate_with_tools",
                return_value=loop_result,
            ),
        ):
            text, trace = generate_tutor_text(
                query="hello",
                evidence=[],
                mastery_status=None,
                grounding_mode="hybrid",
                llm_client=client,
                history_text="",
                assessment_context="",
                session=MagicMock(),
                workspace_id=1,
                user_id=42,
            )

        assert text == "Tool-augmented answer"
        assert isinstance(trace, GenerationTrace)
        assert trace.prompt_tokens == 20
        assert trace.completion_tokens == 15

    def test_fallback_on_empty_registry(self) -> None:
        """When no tools are registered, falls through to normal path."""
        from domain.chat.response_service import generate_tutor_text

        mock_settings = MagicMock()
        mock_settings.enable_tool_calling = True
        mock_settings.web_search_api_key = None
        mock_settings.web_search_max_results = 5

        client = _StubLLMClient()
        empty_reg = _empty_registry()

        with (
            patch("domain.chat.response_service.get_settings", return_value=mock_settings),
            patch(
                "domain.tools.registry_factory.build_tool_registry",
                return_value=empty_reg,
            ),
        ):
            text, trace = generate_tutor_text(
                query="hello",
                evidence=[],
                mastery_status=None,
                grounding_mode="hybrid",
                llm_client=client,
                history_text="",
                assessment_context="",
                session=MagicMock(),
                workspace_id=1,
                user_id=42,
            )
        # Falls through to complete_messages path
        assert isinstance(text, str)
