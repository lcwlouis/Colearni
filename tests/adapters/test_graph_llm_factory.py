"""Unit tests for graph LLM client factory wiring."""

from __future__ import annotations

import pytest
from adapters.llm.factory import build_graph_llm_client, build_tutor_llm_client
from adapters.llm.providers import LiteLLMGraphLLMClient, OpenAIGraphLLMClient
from core.settings import get_settings


@pytest.mark.parametrize(
    ("provider", "update", "expected_type"),
    [
        (
            "openai",
            {"openai_api_key": "test-key", "graph_llm_model": "gpt-4.1-mini"},
            OpenAIGraphLLMClient,
        ),
        (
            "litellm",
            {"graph_llm_model": "deepseek/deepseek-chat", "deepseek_api_key": "sk-ds"},
            LiteLLMGraphLLMClient,
        ),
        (
            "litellm",
            {"litellm_base_url": "http://localhost:4000/v1", "graph_llm_model": "gpt-4o-mini", "litellm_api_key": "proxy-key"},
            LiteLLMGraphLLMClient,
        ),
    ],
)
def test_build_graph_llm_client_returns_expected_adapter(
    provider: str,
    update: dict[str, str],
    expected_type: type[object],
) -> None:
    settings = get_settings().model_copy(update={"graph_llm_provider": provider, **update})
    assert isinstance(build_graph_llm_client(settings=settings), expected_type)


@pytest.mark.parametrize(
    ("update", "error"),
    [
        ({"graph_llm_provider": "openai", "openai_api_key": None}, "APP_OPENAI_API_KEY"),
        ({"graph_llm_provider": "unsupported"}, "Unsupported graph_llm_provider"),
    ],
)
def test_build_graph_llm_client_errors(update: dict[str, object], error: str) -> None:
    settings = get_settings().model_copy(update=update)
    with pytest.raises(ValueError, match=error):
        build_graph_llm_client(settings=settings)


def test_build_graph_llm_client_timeout_override() -> None:
    """timeout_override should replace the default timeout in the built client."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "openai",
            "openai_api_key": "test-key",
            "graph_llm_model": "gpt-4.1-mini",
            "graph_llm_timeout_seconds": 30.0,
        },
    )
    client = build_graph_llm_client(settings=settings, timeout_override=120.0)
    assert isinstance(client, OpenAIGraphLLMClient)
    assert client._timeout_seconds == 120.0


def test_build_graph_llm_client_no_timeout_override_uses_default() -> None:
    """Without timeout_override, client should use settings default."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "openai",
            "openai_api_key": "test-key",
            "graph_llm_model": "gpt-4.1-mini",
            "graph_llm_timeout_seconds": 42.0,
        },
    )
    client = build_graph_llm_client(settings=settings)
    assert isinstance(client, OpenAIGraphLLMClient)
    assert client._timeout_seconds == 42.0


# ── build_tutor_llm_client tests ─────────────────────────────────────


def test_build_tutor_llm_client_falls_back_to_graph() -> None:
    """When tutor settings are None, returns same type as graph client."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "openai",
            "openai_api_key": "test-key",
            "graph_llm_model": "gpt-4.1-mini",
            "tutor_llm_provider": None,
            "tutor_llm_model": None,
        },
    )
    client = build_tutor_llm_client(settings=settings)
    assert isinstance(client, OpenAIGraphLLMClient)


def test_build_tutor_llm_client_with_tutor_model() -> None:
    """When tutor_llm_model is set, builds separate client with that model."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "openai",
            "openai_api_key": "test-key",
            "graph_llm_model": "gpt-4.1-mini",
            "tutor_llm_provider": None,
            "tutor_llm_model": "gpt-4o",
        },
    )
    client = build_tutor_llm_client(settings=settings)
    assert isinstance(client, OpenAIGraphLLMClient)
    assert client._model == "gpt-4o"


def test_build_tutor_llm_client_openai_provider() -> None:
    """When tutor_llm_provider is openai with tutor_llm_model, builds OpenAI client."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "litellm",
            "graph_llm_model": "openai/gpt-4.1-mini",
            "openai_api_key": "test-key",
            "tutor_llm_provider": "openai",
            "tutor_llm_model": "gpt-4o",
        },
    )
    client = build_tutor_llm_client(settings=settings)
    assert isinstance(client, OpenAIGraphLLMClient)
    assert client._model == "gpt-4o"


def test_build_tutor_llm_client_litellm_provider() -> None:
    """When tutor_llm_provider is litellm with tutor_llm_model, builds LiteLLM client."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "openai",
            "openai_api_key": "test-key",
            "graph_llm_model": "gpt-4.1-mini",
            "tutor_llm_provider": "litellm",
            "tutor_llm_model": "openai/gpt-4o",
        },
    )
    client = build_tutor_llm_client(settings=settings)
    assert isinstance(client, LiteLLMGraphLLMClient)
    assert client._model == "openai/gpt-4o"


def test_build_tutor_llm_client_model_only_uses_graph_provider() -> None:
    """When only tutor_llm_model is set (no provider), uses graph_llm_provider."""
    settings = get_settings().model_copy(
        update={
            "graph_llm_provider": "litellm",
            "graph_llm_model": "openai/gpt-4.1-mini",
            "deepseek_api_key": "sk-ds",
            "tutor_llm_provider": None,
            "tutor_llm_model": "deepseek/deepseek-chat",
        },
    )
    client = build_tutor_llm_client(settings=settings)
    assert isinstance(client, LiteLLMGraphLLMClient)
    assert client._model == "deepseek/deepseek-chat"
