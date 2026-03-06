"""Tests for _model_supports_json_schema() with litellm runtime check."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from adapters.llm.providers import _BaseGraphLLMClient


class _StubClient(_BaseGraphLLMClient):
    """Minimal stub to test _model_supports_json_schema without a real SDK."""

    def __init__(self, *, model: str, provider: str) -> None:
        super().__init__(model=model, timeout_seconds=30.0, provider=provider)

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        return {"choices": [{"message": {"content": "{}"}}]}

    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        return iter([])


class TestModelSupportsJsonSchema:
    """Tests for the litellm-backed _model_supports_json_schema method."""

    @patch("litellm.supports_response_schema", return_value=True)
    def test_returns_true_for_gpt4o(self, mock_srs: MagicMock) -> None:
        client = _StubClient(model="gpt-4o", provider="openai")
        assert client._model_supports_json_schema() is True
        mock_srs.assert_called_once_with(model="gpt-4o", custom_llm_provider="openai")

    @patch("litellm.supports_response_schema", return_value=True)
    def test_returns_true_for_gpt41_mini(self, mock_srs: MagicMock) -> None:
        client = _StubClient(model="gpt-4.1-mini", provider="openai")
        assert client._model_supports_json_schema() is True
        mock_srs.assert_called_once_with(model="gpt-4.1-mini", custom_llm_provider="openai")

    @patch("litellm.supports_response_schema", return_value=False)
    def test_returns_false_for_unsupported_model(self, mock_srs: MagicMock) -> None:
        client = _StubClient(model="old-model-v1", provider="litellm")
        assert client._model_supports_json_schema() is False
        mock_srs.assert_called_once_with(model="old-model-v1")

    @patch("litellm.supports_response_schema", side_effect=Exception("unavailable"))
    def test_fallback_openai_provider(self, mock_srs: MagicMock) -> None:
        """Falls back to heuristic when litellm raises; openai provider → True."""
        client = _StubClient(model="gpt-4o", provider="openai")
        assert client._model_supports_json_schema() is True

    @patch("litellm.supports_response_schema", side_effect=Exception("unavailable"))
    def test_fallback_openai_prefix(self, mock_srs: MagicMock) -> None:
        """Falls back to heuristic; model starting with openai/ → True."""
        client = _StubClient(model="openai/gpt-4o", provider="litellm")
        assert client._model_supports_json_schema() is True

    @patch("litellm.supports_response_schema", side_effect=Exception("unavailable"))
    def test_fallback_gpt_in_model_name(self, mock_srs: MagicMock) -> None:
        """Falls back to heuristic; model containing gpt- → True."""
        client = _StubClient(model="gpt-3.5-turbo", provider="litellm")
        assert client._model_supports_json_schema() is True

    @patch("litellm.supports_response_schema", side_effect=Exception("unavailable"))
    def test_fallback_unknown_model_returns_false(self, mock_srs: MagicMock) -> None:
        """Falls back to heuristic; unknown provider + model → False."""
        client = _StubClient(model="some-other-model", provider="litellm")
        assert client._model_supports_json_schema() is False


class TestJsonSchemaWithOpenAIProvider:
    """Verify behavior specifically for OpenAI provider."""

    @patch("litellm.supports_response_schema", return_value=True)
    def test_openai_provider_supported(self, mock_srs: MagicMock) -> None:
        client = _StubClient(model="gpt-4o", provider="openai")
        assert client._model_supports_json_schema() is True
        mock_srs.assert_called_once_with(model="gpt-4o", custom_llm_provider="openai")


class TestJsonSchemaWithLiteLLMProvider:
    """Verify behavior specifically for LiteLLM provider."""

    @patch("litellm.supports_response_schema", return_value=True)
    def test_litellm_provider_supported(self, mock_srs: MagicMock) -> None:
        client = _StubClient(model="openai/gpt-4o", provider="litellm")
        assert client._model_supports_json_schema() is True
        mock_srs.assert_called_once_with(model="openai/gpt-4o")

    @patch("litellm.supports_response_schema", return_value=False)
    def test_litellm_provider_unsupported(self, mock_srs: MagicMock) -> None:
        client = _StubClient(model="anthropic/claude-3-haiku", provider="litellm")
        assert client._model_supports_json_schema() is False
