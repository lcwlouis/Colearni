"""Tests for async LLM client methods (L3.5)."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.llm.providers import (
    LiteLLMGraphLLMClient,
    OpenAIGraphLLMClient,
    _BaseGraphLLMClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(content: str, *, as_json: bool = False) -> dict[str, Any]:
    """Build a minimal OpenAI-shaped response dict."""
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def _model_dump_response(content: str) -> MagicMock:
    """Return a mock object with .model_dump() returning the fake response."""
    resp = MagicMock()
    resp.model_dump.return_value = _fake_response(content)
    return resp


# ---------------------------------------------------------------------------
# OpenAI async tests
# ---------------------------------------------------------------------------


class TestOpenAIAsyncCompleteMethods:
    """Test async_complete_messages and async_complete_messages_json for OpenAI."""

    def _make_client(self) -> OpenAIGraphLLMClient:
        with patch("openai.OpenAI"), patch("openai.AsyncOpenAI"):
            return OpenAIGraphLLMClient(
                api_key="test-key",
                model="gpt-4",
                timeout_seconds=30.0,
            )

    @pytest.mark.anyio
    async def test_async_complete_messages(self) -> None:
        client = self._make_client()
        mock_create = AsyncMock(return_value=_model_dump_response("Hello world"))
        client._async_client.chat.completions.create = mock_create

        text, trace = await client.async_complete_messages(
            [{"role": "user", "content": "Hi"}],
        )

        assert text == "Hello world"
        assert trace.provider == "openai"
        assert trace.model == "gpt-4"
        assert trace.prompt_tokens == 10
        assert trace.completion_tokens == 5
        mock_create.assert_awaited_once()

    @pytest.mark.anyio
    async def test_async_complete_messages_json(self) -> None:
        client = self._make_client()
        payload = {"concepts": [], "edges": []}
        mock_create = AsyncMock(
            return_value=_model_dump_response(json.dumps(payload)),
        )
        client._async_client.chat.completions.create = mock_create

        result = await client.async_complete_messages_json(
            [{"role": "system", "content": "Return JSON"}, {"role": "user", "content": "extract"}],
            schema_name="test_schema",
            schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        )

        assert result == payload
        mock_create.assert_awaited_once()


# ---------------------------------------------------------------------------
# LiteLLM async tests
# ---------------------------------------------------------------------------


class TestLiteLLMAsyncCompleteMethods:
    """Test async_complete_messages and async_complete_messages_json for LiteLLM."""

    def _make_client(self) -> LiteLLMGraphLLMClient:
        return LiteLLMGraphLLMClient(
            model="anthropic/claude-3-haiku",
            timeout_seconds=30.0,
        )

    @pytest.mark.anyio
    async def test_async_complete_messages(self) -> None:
        client = self._make_client()
        mock_acompletion = AsyncMock(
            return_value=_model_dump_response("Bonjour"),
        )

        with patch("litellm.acompletion", mock_acompletion):
            text, trace = await client.async_complete_messages(
                [{"role": "user", "content": "Hi"}],
            )

        assert text == "Bonjour"
        assert trace.provider == "litellm"
        assert trace.model == "anthropic/claude-3-haiku"
        assert trace.total_tokens == 15
        mock_acompletion.assert_awaited_once()

    @pytest.mark.anyio
    async def test_async_complete_messages_json(self) -> None:
        client = self._make_client()
        payload = {"answer": 42}
        mock_acompletion = AsyncMock(
            return_value=_model_dump_response(json.dumps(payload)),
        )

        with patch("litellm.acompletion", mock_acompletion):
            result = await client.async_complete_messages_json(
                [{"role": "system", "content": "JSON"}, {"role": "user", "content": "what"}],
                schema_name="test",
                schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            )

        assert result == payload
        mock_acompletion.assert_awaited_once()


# ---------------------------------------------------------------------------
# Coroutine verification
# ---------------------------------------------------------------------------


class TestAsyncMethodsAreCoroutines:
    """Verify async methods are properly defined as coroutines."""

    def test_base_class_has_async_methods(self) -> None:
        assert hasattr(_BaseGraphLLMClient, "async_complete_messages")
        assert hasattr(_BaseGraphLLMClient, "async_complete_messages_json")
        assert inspect.iscoroutinefunction(_BaseGraphLLMClient.async_complete_messages)
        assert inspect.iscoroutinefunction(_BaseGraphLLMClient.async_complete_messages_json)

    def test_openai_has_async_sdk_methods(self) -> None:
        assert hasattr(OpenAIGraphLLMClient, "_async_sdk_call")
        assert inspect.iscoroutinefunction(OpenAIGraphLLMClient._async_sdk_call)
        assert hasattr(OpenAIGraphLLMClient, "_async_sdk_stream_call")
        assert inspect.isasyncgenfunction(OpenAIGraphLLMClient._async_sdk_stream_call)

    def test_litellm_has_async_sdk_methods(self) -> None:
        assert hasattr(LiteLLMGraphLLMClient, "_async_sdk_call")
        assert inspect.iscoroutinefunction(LiteLLMGraphLLMClient._async_sdk_call)
        assert hasattr(LiteLLMGraphLLMClient, "_async_sdk_stream_call")
        assert inspect.isasyncgenfunction(LiteLLMGraphLLMClient._async_sdk_stream_call)
