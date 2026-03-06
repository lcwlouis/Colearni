"""Tests for L3.3 — SDK retries and context-window fallbacks."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from adapters.llm.providers import LiteLLMGraphLLMClient, OpenAIGraphLLMClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sdk_response(content: str = "ok") -> MagicMock:
    """Return a MagicMock that quacks like a LiteLLM ModelResponse."""
    resp = MagicMock()
    resp.model_dump.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }
    return resp


def _noop_limiter_execute(fn: Any, **kwargs: Any) -> Any:
    """Bypass the rate limiter by calling fn directly."""
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# OpenAI SDK max_retries
# ---------------------------------------------------------------------------


class TestOpenAIRetries:
    """Verify max_retries is forwarded to the OpenAI client."""

    def test_default_max_retries(self) -> None:
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = OpenAIGraphLLMClient(
                api_key="sk-test",
                model="gpt-4o",
                timeout_seconds=10.0,
            )
            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["max_retries"] == 2
            assert client._max_retries == 2

    def test_custom_max_retries(self) -> None:
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = OpenAIGraphLLMClient(
                api_key="sk-test",
                model="gpt-4o",
                timeout_seconds=10.0,
                max_retries=5,
            )
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["max_retries"] == 5
            assert client._max_retries == 5

    def test_zero_retries(self) -> None:
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            OpenAIGraphLLMClient(
                api_key="sk-test",
                model="gpt-4o",
                timeout_seconds=10.0,
                max_retries=0,
            )
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["max_retries"] == 0


# ---------------------------------------------------------------------------
# LiteLLM num_retries + context_window_fallback_dict
# ---------------------------------------------------------------------------


class TestLiteLLMRetries:
    """Verify num_retries and context_window_fallback_dict in LiteLLM kwargs."""

    def test_sdk_call_includes_num_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _capture(**kwargs: Any) -> Any:
            captured.append(kwargs)
            return _make_sdk_response()

        monkeypatch.setattr("litellm.completion", _capture)
        monkeypatch.setattr(
            "adapters.llm.providers.get_llm_limiter",
            lambda: MagicMock(execute=_noop_limiter_execute),
        )

        client = LiteLLMGraphLLMClient(
            model="gpt-4o-mini",
            timeout_seconds=5.0,
            num_retries=3,
        )
        client._sdk_call(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            response_format=None,
        )
        assert captured[0]["num_retries"] == 3

    def test_sdk_call_default_num_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _capture(**kwargs: Any) -> Any:
            captured.append(kwargs)
            return _make_sdk_response()

        monkeypatch.setattr("litellm.completion", _capture)
        monkeypatch.setattr(
            "adapters.llm.providers.get_llm_limiter",
            lambda: MagicMock(execute=_noop_limiter_execute),
        )

        client = LiteLLMGraphLLMClient(
            model="gpt-4o-mini",
            timeout_seconds=5.0,
        )
        client._sdk_call(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            response_format=None,
        )
        assert captured[0]["num_retries"] == 2

    def test_sdk_call_includes_fallback_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _capture(**kwargs: Any) -> Any:
            captured.append(kwargs)
            return _make_sdk_response()

        monkeypatch.setattr("litellm.completion", _capture)
        monkeypatch.setattr(
            "adapters.llm.providers.get_llm_limiter",
            lambda: MagicMock(execute=_noop_limiter_execute),
        )

        fallbacks = {"gpt-4o": "gpt-4o-mini"}
        client = LiteLLMGraphLLMClient(
            model="gpt-4o",
            timeout_seconds=5.0,
            context_window_fallback_dict=fallbacks,
        )
        client._sdk_call(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            response_format=None,
        )
        assert captured[0]["context_window_fallback_dict"] == fallbacks

    def test_sdk_call_omits_empty_fallback_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _capture(**kwargs: Any) -> Any:
            captured.append(kwargs)
            return _make_sdk_response()

        monkeypatch.setattr("litellm.completion", _capture)
        monkeypatch.setattr(
            "adapters.llm.providers.get_llm_limiter",
            lambda: MagicMock(execute=_noop_limiter_execute),
        )

        client = LiteLLMGraphLLMClient(
            model="gpt-4o",
            timeout_seconds=5.0,
            context_window_fallback_dict={},
        )
        client._sdk_call(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
            response_format=None,
        )
        assert "context_window_fallback_dict" not in captured[0]

    def test_stream_call_includes_num_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _capture(**kwargs: Any) -> Any:
            captured.append(kwargs)
            return iter([])

        monkeypatch.setattr("litellm.completion", _capture)
        monkeypatch.setattr(
            "adapters.llm.providers.get_llm_limiter",
            lambda: MagicMock(execute=_noop_limiter_execute),
        )

        client = LiteLLMGraphLLMClient(
            model="gpt-4o-mini",
            timeout_seconds=5.0,
            num_retries=4,
        )
        # Consume the generator to trigger the call
        list(client._sdk_stream_call(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
        ))
        assert captured[0]["num_retries"] == 4

    def test_stream_call_includes_fallback_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[dict[str, Any]] = []

        def _capture(**kwargs: Any) -> Any:
            captured.append(kwargs)
            return iter([])

        monkeypatch.setattr("litellm.completion", _capture)
        monkeypatch.setattr(
            "adapters.llm.providers.get_llm_limiter",
            lambda: MagicMock(execute=_noop_limiter_execute),
        )

        fallbacks = {"gpt-4o": "gpt-4o-mini"}
        client = LiteLLMGraphLLMClient(
            model="gpt-4o",
            timeout_seconds=5.0,
            context_window_fallback_dict=fallbacks,
        )
        list(client._sdk_stream_call(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.0,
        ))
        assert captured[0]["context_window_fallback_dict"] == fallbacks


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    """Verify new settings fields have correct defaults."""

    def test_llm_sdk_max_retries_default(self) -> None:
        from core.settings import Settings

        s = Settings(
            neo4j_uri="bolt://localhost:7687",
            openai_api_key="sk-test",
        )
        assert s.llm_sdk_max_retries == 2

    def test_llm_context_window_fallbacks_default(self) -> None:
        from core.settings import Settings

        s = Settings(
            neo4j_uri="bolt://localhost:7687",
            openai_api_key="sk-test",
        )
        assert s.llm_context_window_fallbacks == {"gpt-4o": "gpt-4o-mini"}

    def test_llm_context_window_fallbacks_overridable(self) -> None:
        from core.settings import Settings

        custom = {"gpt-4": "gpt-3.5-turbo"}
        s = Settings(
            neo4j_uri="bolt://localhost:7687",
            openai_api_key="sk-test",
            APP_LLM_CONTEXT_WINDOW_FALLBACKS=custom,
        )
        assert s.llm_context_window_fallbacks == custom
