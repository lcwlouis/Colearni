"""Tests for L3.2 prompt cache_control support in providers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from adapters.llm.providers import _BaseGraphLLMClient


class _StubClient(_BaseGraphLLMClient):
    """Minimal stub for testing cache_control helpers."""

    def __init__(self, *, model: str = "test-model", provider: str = "stub") -> None:
        super().__init__(
            model=model,
            timeout_seconds=30.0,
            provider=provider,
        )

    def _sdk_call(
        self, *, messages: list[dict[str, str]], temperature: float,
        response_format: dict[str, object] | None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> Mapping[str, Any]:
        raise NotImplementedError

    def _sdk_stream_call(
        self, *, messages: list[dict[str, str]], temperature: float,
        effort_override: str | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        raise NotImplementedError


class TestIsAnthropicModel:
    def test_claude_model(self) -> None:
        client = _StubClient(model="claude-3-5-sonnet-20241022")
        assert client._is_anthropic_model() is True

    def test_anthropic_prefix(self) -> None:
        client = _StubClient(model="anthropic/claude-3-haiku")
        assert client._is_anthropic_model() is True

    def test_openai_model(self) -> None:
        client = _StubClient(model="gpt-4o")
        assert client._is_anthropic_model() is False

    def test_litellm_non_anthropic(self) -> None:
        client = _StubClient(model="openai/gpt-4o-mini")
        assert client._is_anthropic_model() is False


class TestToContentBlocks:
    """Tests for _to_content_blocks — converts system/user to structured blocks."""

    def test_converts_system_and_user_to_blocks(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are a tutor."},
            {"role": "user", "content": "What is DNA?"},
        ]
        result = _BaseGraphLLMClient._to_content_blocks(messages)
        assert result[0]["content"] == [{"type": "text", "text": "You are a tutor."}]
        assert result[1]["content"] == [{"type": "text", "text": "What is DNA?"}]

    def test_leaves_assistant_messages_as_strings(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Sys"},
            {"role": "assistant", "content": "Sure, DNA is..."},
            {"role": "user", "content": "Thanks"},
        ]
        result = _BaseGraphLLMClient._to_content_blocks(messages)
        assert isinstance(result[1]["content"], str)
        assert result[1]["content"] == "Sure, DNA is..."

    def test_leaves_tool_messages_as_strings(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "tool", "content": '{"result": 42}', "tool_call_id": "x"},
        ]
        result = _BaseGraphLLMClient._to_content_blocks(messages)
        assert isinstance(result[0]["content"], str)

    def test_already_list_content_unchanged(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": [{"type": "text", "text": "pre-converted"}]},
        ]
        result = _BaseGraphLLMClient._to_content_blocks(messages)
        assert result[0]["content"] == [{"type": "text", "text": "pre-converted"}]

    def test_does_not_mutate_original(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Original"},
            {"role": "user", "content": "Q"},
        ]
        _BaseGraphLLMClient._to_content_blocks(messages)
        assert isinstance(messages[0]["content"], str)
        assert isinstance(messages[1]["content"], str)


class TestPrepareMessages:
    def test_anthropic_adds_cache_control(self) -> None:
        client = _StubClient(model="claude-3-5-sonnet-20241022")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Prefix"},
            {"role": "user", "content": "Q"},
        ]
        result = client._prepare_messages(messages)
        # System → content blocks with cache_control
        sys_blocks = result[0]["content"]
        assert isinstance(sys_blocks, list)
        assert sys_blocks[0]["cache_control"] == {"type": "ephemeral"}
        # User → content blocks without cache_control
        user_blocks = result[1]["content"]
        assert isinstance(user_blocks, list)
        assert "cache_control" not in user_blocks[0]

    def test_openai_uses_content_blocks_no_cache_control(self) -> None:
        client = _StubClient(model="gpt-4o")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Prefix"},
            {"role": "user", "content": "Q"},
        ]
        result = client._prepare_messages(messages)
        # System → content blocks without cache_control
        assert result[0]["content"] == [{"type": "text", "text": "Prefix"}]
        # User → content blocks
        assert result[1]["content"] == [{"type": "text", "text": "Q"}]

    def test_anthropic_second_system_has_no_cache_control(self) -> None:
        client = _StubClient(model="claude-3-5-sonnet-20241022")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Prefix"},
            {"role": "system", "content": "Context block"},
            {"role": "user", "content": "Q"},
        ]
        result = client._prepare_messages(messages)
        # First system has cache_control
        assert "cache_control" in result[0]["content"][0]
        # Second system is content blocks but no cache_control
        assert isinstance(result[1]["content"], list)
        assert "cache_control" not in result[1]["content"][0]

    def test_assistant_stays_plain_string(self) -> None:
        client = _StubClient(model="gpt-4o")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Sys"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Q"},
        ]
        result = client._prepare_messages(messages)
        assert isinstance(result[1]["content"], str)
