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


class TestApplyCacheControl:
    def test_annotates_first_system_message(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are a tutor."},
            {"role": "system", "content": "Context: Biology"},
            {"role": "user", "content": "What is DNA?"},
        ]
        result = _BaseGraphLLMClient._apply_cache_control(messages)
        first = result[0]
        assert isinstance(first["content"], list)
        assert first["content"][0]["type"] == "text"
        assert first["content"][0]["text"] == "You are a tutor."
        assert first["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_leaves_subsequent_system_messages_unchanged(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Prefix"},
            {"role": "system", "content": "Context block"},
            {"role": "user", "content": "Q"},
        ]
        result = _BaseGraphLLMClient._apply_cache_control(messages)
        assert isinstance(result[1]["content"], str)
        assert result[1]["content"] == "Context block"

    def test_leaves_user_messages_unchanged(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Sys"},
            {"role": "user", "content": "Hello"},
        ]
        result = _BaseGraphLLMClient._apply_cache_control(messages)
        assert result[1]["content"] == "Hello"

    def test_no_system_messages_returns_copy(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": "Hello"},
        ]
        result = _BaseGraphLLMClient._apply_cache_control(messages)
        assert result == messages

    def test_does_not_mutate_original(self) -> None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Original"},
            {"role": "user", "content": "Q"},
        ]
        _BaseGraphLLMClient._apply_cache_control(messages)
        assert isinstance(messages[0]["content"], str)


class TestPrepareMessages:
    def test_applies_cache_control_for_anthropic(self) -> None:
        client = _StubClient(model="claude-3-5-sonnet-20241022")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Prefix"},
            {"role": "user", "content": "Q"},
        ]
        result = client._prepare_messages(messages)
        assert isinstance(result[0]["content"], list)

    def test_no_cache_control_for_openai(self) -> None:
        client = _StubClient(model="gpt-4o")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "Prefix"},
            {"role": "user", "content": "Q"},
        ]
        result = client._prepare_messages(messages)
        assert result is messages  # identity — no copy needed
        assert isinstance(result[0]["content"], str)
