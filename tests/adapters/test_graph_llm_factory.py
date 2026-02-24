"""Unit tests for graph LLM client factory wiring."""

from __future__ import annotations

import pytest
from adapters.llm.factory import build_graph_llm_client
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
            {"litellm_base_url": "http://localhost:4000/v1", "graph_llm_model": "gpt-4o-mini"},
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
