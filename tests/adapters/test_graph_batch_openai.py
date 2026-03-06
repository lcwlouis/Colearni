"""Tests for OpenAI batch extraction using asyncio.gather (L7.3)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_messages import MessageBuilder


def _make_openai_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a fake OpenAI chat completion response dict."""
    return {
        "choices": [
            {
                "message": {"content": json.dumps(payload), "role": "assistant"},
                "finish_reason": "stop",
                "index": 0,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def test_openai_batch_uses_asyncio_gather() -> None:
    """OpenAIGraphLLMClient._batch_complete_messages_json uses async gather."""
    from adapters.llm.providers import OpenAIGraphLLMClient

    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    msgs_a = MessageBuilder().system("sys").user("a").build()
    msgs_b = MessageBuilder().system("sys").user("b").build()

    responses = [
        _make_openai_response({"x": "result_a"}),
        _make_openai_response({"x": "result_b"}),
    ]
    call_idx = {"i": 0}

    async def _mock_async_sdk_call(**kwargs: Any) -> Mapping[str, Any]:
        idx = call_idx["i"]
        call_idx["i"] += 1
        return responses[idx]

    with patch("openai.OpenAI"), patch("openai.AsyncOpenAI"):
        client = OpenAIGraphLLMClient(
            api_key="test-key",
            model="gpt-4",
            timeout_seconds=30.0,
        )

    client._async_sdk_call = _mock_async_sdk_call  # type: ignore[assignment]

    results = client._batch_complete_messages_json(
        [msgs_a, msgs_b],
        schema_name="test",
        schema=schema,
    )

    assert len(results) == 2
    assert results[0] == {"x": "result_a"}
    assert results[1] == {"x": "result_b"}


def test_openai_batch_empty_input() -> None:
    """Empty message_lists returns empty results."""
    from adapters.llm.providers import OpenAIGraphLLMClient

    with patch("openai.OpenAI"), patch("openai.AsyncOpenAI"):
        client = OpenAIGraphLLMClient(
            api_key="test-key",
            model="gpt-4",
            timeout_seconds=30.0,
        )

    results = client._batch_complete_messages_json(
        [],
        schema_name="test",
        schema={"type": "object"},
    )
    assert results == []


def test_litellm_batch_uses_batch_completion() -> None:
    """LiteLLMGraphLLMClient._batch_complete_messages_json uses litellm.batch_completion."""
    from adapters.llm.providers import LiteLLMGraphLLMClient

    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    msgs_a = MessageBuilder().system("sys").user("a").build()
    msgs_b = MessageBuilder().system("sys").user("b").build()

    resp_a = MagicMock()
    resp_a.model_dump.return_value = _make_openai_response({"x": "result_a"})
    resp_b = MagicMock()
    resp_b.model_dump.return_value = _make_openai_response({"x": "result_b"})

    mock_limiter = MagicMock()
    mock_limiter.execute.return_value = [resp_a, resp_b]

    with (
        patch("adapters.llm.providers.get_llm_limiter", return_value=mock_limiter),
        patch("litellm.enable_json_schema_validation", True),
    ):
        client = LiteLLMGraphLLMClient(
            model="openai/gpt-4",
            timeout_seconds=30.0,
            json_schema_validation=False,
        )

        results = client._batch_complete_messages_json(
            [msgs_a, msgs_b],
            schema_name="test",
            schema=schema,
        )

    assert len(results) == 2
    assert results[0] == {"x": "result_a"}
    assert results[1] == {"x": "result_b"}
    mock_limiter.execute.assert_called_once()
