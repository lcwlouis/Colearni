from __future__ import annotations

from typing import Any

import pytest
from adapters.embeddings.factory import build_embedding_provider
from adapters.embeddings.mock_provider import MockEmbeddingProvider
from adapters.embeddings.openai_provider import OpenAIEmbeddingProvider
from core.settings import get_settings


def test_factory_returns_mock_provider() -> None:
    settings = get_settings().model_copy(update={"embedding_provider": "mock", "embedding_dim": 7})
    assert isinstance(build_embedding_provider(settings=settings), MockEmbeddingProvider)


def test_factory_returns_openai_provider_when_api_key_is_set() -> None:
    settings = get_settings().model_copy(
        update={
            "embedding_provider": "openai",
            "openai_api_key": "sk-test",
            "embedding_model": "text-embedding-3-small",
        }
    )
    assert isinstance(build_embedding_provider(settings=settings), OpenAIEmbeddingProvider)


def test_factory_raises_when_openai_provider_missing_api_key() -> None:
    settings = get_settings().model_copy(
        update={"embedding_provider": "openai", "openai_api_key": "   "}
    )
    with pytest.raises(ValueError, match="APP_OPENAI_API_KEY"):
        build_embedding_provider(settings=settings)


def test_factory_returns_litellm_provider_with_expected_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeLiteLLMProvider:
        def __init__(
            self,
            *,
            model: str,
            embedding_dim: int,
            timeout_seconds: float,
            api_base: str | None = None,
            api_key: str | None = None,
        ) -> None:
            captured.update(
                {
                    "model": model,
                    "embedding_dim": embedding_dim,
                    "timeout_seconds": timeout_seconds,
                    "api_base": api_base,
                    "api_key": api_key,
                }
            )

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] for _ in texts]

    monkeypatch.setattr(
        "adapters.embeddings.litellm_provider.LiteLLMEmbeddingProvider",
        _FakeLiteLLMProvider,
    )
    settings = get_settings().model_copy(
        update={
            "embedding_provider": "litellm",
            "embedding_dim": 4,
            "embedding_timeout_seconds": 9.5,
            "litellm_model": "text-embedding-proxy",
            "litellm_base_url": "http://localhost:4000",
            "litellm_api_key": "proxy-key",
        }
    )
    provider = build_embedding_provider(settings=settings)
    assert isinstance(provider, _FakeLiteLLMProvider)
    assert captured == {
        "model": "text-embedding-proxy",
        "embedding_dim": 4,
        "timeout_seconds": 9.5,
        "api_base": "http://localhost:4000",
        "api_key": "proxy-key",
    }


def test_factory_raises_when_litellm_model_is_missing() -> None:
    settings = get_settings().model_copy(
        update={"embedding_provider": "litellm", "litellm_model": "  "}
    )
    with pytest.raises(ValueError, match="APP_LITELLM_MODEL"):
        build_embedding_provider(settings=settings)
