"""Factory helpers for embedding providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.contracts import EmbeddingProvider
    from core.settings import Settings


def build_embedding_provider(settings: Settings | None = None) -> "EmbeddingProvider":
    """Build the configured embedding provider implementation."""
    if settings is None:
        from core.settings import get_settings

        active_settings = get_settings()
    else:
        active_settings = settings

    if active_settings.embedding_provider == "mock":
        from adapters.embeddings.mock_provider import MockEmbeddingProvider

        return MockEmbeddingProvider(embedding_dim=active_settings.embedding_dim)

    if active_settings.embedding_provider == "openai":
        from adapters.embeddings.openai_provider import OpenAIEmbeddingProvider

        if active_settings.openai_api_key is None or not active_settings.openai_api_key.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY (or OPENAI_API_KEY) must be set "
                "when APP_EMBEDDING_PROVIDER=openai"
            )
        return OpenAIEmbeddingProvider(
            api_key=active_settings.openai_api_key,
            model=active_settings.embedding_model,
            embedding_dim=active_settings.embedding_dim,
            timeout_seconds=active_settings.embedding_timeout_seconds,
        )

    if active_settings.embedding_provider == "litellm":
        from adapters.embeddings.litellm_provider import LiteLLMEmbeddingProvider

        model = _non_empty_or_none(active_settings.litellm_model)
        if model is None:
            raise ValueError(
                "APP_LITELLM_MODEL (or LITELLM_MODEL) must be set "
                "when APP_EMBEDDING_PROVIDER=litellm"
            )
        return LiteLLMEmbeddingProvider(
            model=model,
            embedding_dim=active_settings.embedding_dim,
            timeout_seconds=active_settings.embedding_timeout_seconds,
            api_base=_non_empty_or_none(active_settings.litellm_base_url),
            api_key=_non_empty_or_none(active_settings.litellm_api_key),
        )

    raise ValueError(f"Unsupported embedding provider: {active_settings.embedding_provider}")


def _non_empty_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None
