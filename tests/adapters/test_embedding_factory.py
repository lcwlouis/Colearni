from __future__ import annotations

from typing import Any

import pytest
from adapters.embeddings.factory import build_embedding_provider
from adapters.embeddings.litellm_provider import LiteLLMEmbeddingProvider
from adapters.embeddings.mock_provider import MockEmbeddingProvider
from adapters.embeddings.openai_provider import OpenAIEmbeddingProvider
from core.settings import Settings, get_settings


def _clear_embedding_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "APP_EMBEDDING_PROVIDER",
        "EMBEDDING_PROVIDER",
        "APP_EMBEDDING_MODEL",
        "EMBEDDING_MODEL",
        "APP_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "APP_DEEPSEEK_API_KEY",
        "DEEPSEEK_API_KEY",
        "APP_LITELLM_MODEL",
        "LITELLM_MODEL",
        "APP_LITELLM_BASE_URL",
        "LITELLM_BASE_URL",
        "APP_LITELLM_API_KEY",
        "LITELLM_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


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
            "embedding_model": "openai/text-embedding-3-small",
            "embedding_dim": 4,
            "embedding_timeout_seconds": 9.5,
            "litellm_base_url": "http://localhost:4000",
            "litellm_api_key": "proxy-key",
        }
    )
    provider = build_embedding_provider(settings=settings)
    assert isinstance(provider, _FakeLiteLLMProvider)
    assert captured == {
        "model": "openai/text-embedding-3-small",
        "embedding_dim": 4,
        "timeout_seconds": 9.5,
        "api_base": "http://localhost:4000",
        "api_key": "proxy-key",
    }


def test_factory_litellm_direct_mode_resolves_openai_api_key() -> None:
    """In direct mode (no proxy), openai/ model uses openai_api_key."""
    settings = get_settings().model_copy(
        update={
            "embedding_provider": "litellm",
            "embedding_model": "openai/text-embedding-3-small",
            "litellm_base_url": None,
            "openai_api_key": "sk-openai",
            "litellm_api_key": "sk-fallback",
        }
    )
    provider = build_embedding_provider(settings=settings)
    assert isinstance(provider, LiteLLMEmbeddingProvider)
    assert provider._api_key == "sk-openai"
    assert provider._api_base is None


def test_factory_litellm_direct_mode_resolves_deepseek_api_key() -> None:
    """In direct mode, deepseek/ model uses deepseek_api_key."""
    settings = get_settings().model_copy(
        update={
            "embedding_provider": "litellm",
            "embedding_model": "deepseek/deepseek-chat",
            "litellm_base_url": None,
            "deepseek_api_key": "sk-deepseek",
            "litellm_api_key": "sk-fallback",
        }
    )
    provider = build_embedding_provider(settings=settings)
    assert isinstance(provider, LiteLLMEmbeddingProvider)
    assert provider._api_key == "sk-deepseek"


def test_factory_litellm_direct_mode_falls_back_to_litellm_key() -> None:
    """In direct mode, unknown provider falls back to litellm_api_key."""
    settings = get_settings().model_copy(
        update={
            "embedding_provider": "litellm",
            "embedding_model": "custom-model",
            "litellm_base_url": None,
            "litellm_api_key": "sk-fallback",
        }
    )
    provider = build_embedding_provider(settings=settings)
    assert isinstance(provider, LiteLLMEmbeddingProvider)
    assert provider._api_key == "sk-fallback"


def test_factory_raises_when_litellm_embedding_model_is_missing() -> None:
    settings = get_settings().model_copy(
        update={"embedding_provider": "litellm", "embedding_model": "  "}
    )
    with pytest.raises(ValueError, match="APP_EMBEDDING_MODEL"):
        build_embedding_provider(settings=settings)


@pytest.mark.parametrize(
    ("provider", "extra_env", "expected_type"),
    [
        ("mock", {}, MockEmbeddingProvider),
        ("openai", {"APP_OPENAI_API_KEY": "sk-test"}, OpenAIEmbeddingProvider),
        ("litellm", {"APP_EMBEDDING_MODEL": "openai/text-embedding-3-small"}, LiteLLMEmbeddingProvider),
    ],
)
def test_factory_builds_provider_from_env_settings(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    extra_env: dict[str, str],
    expected_type: type[object],
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("APP_EMBEDDING_PROVIDER", provider)
    for key, value in extra_env.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert isinstance(build_embedding_provider(settings=settings), expected_type)


def test_factory_env_litellm_provider_requires_embedding_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("APP_EMBEDDING_PROVIDER", "litellm")
    monkeypatch.setenv("APP_EMBEDDING_MODEL", "   ")

    settings = Settings(_env_file=None)

    with pytest.raises(ValueError, match="APP_EMBEDDING_MODEL"):
        build_embedding_provider(settings=settings)
