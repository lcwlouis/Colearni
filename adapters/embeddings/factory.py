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

        model = _non_empty_or_none(active_settings.embedding_model)
        if model is None:
            raise ValueError(
                "APP_EMBEDDING_MODEL (or EMBEDDING_MODEL) must be set "
                "when APP_EMBEDDING_PROVIDER=litellm"
            )
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        api_key = _resolve_litellm_api_key(model, active_settings, api_base)
        return LiteLLMEmbeddingProvider(
            model=model,
            embedding_dim=active_settings.embedding_dim,
            timeout_seconds=active_settings.embedding_timeout_seconds,
            api_base=api_base,
            api_key=api_key,
        )

    raise ValueError(f"Unsupported embedding provider: {active_settings.embedding_provider}")


def _non_empty_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _resolve_litellm_api_key(
    model: str,
    settings: "Settings",
    api_base: str | None,
) -> str | None:
    """Resolve the API key for a LiteLLM model.

    In proxy mode (api_base set), use the shared proxy key.
    In direct mode, detect the provider from the model prefix and use
    the matching per-provider key, falling back to litellm_api_key.
    """
    if api_base:
        return _non_empty_or_none(settings.litellm_api_key)

    if "/" in model:
        prefix = model.split("/")[0].lower()
        if prefix == "openai":
            key = _non_empty_or_none(settings.openai_api_key)
            if key:
                return key
        elif prefix == "deepseek":
            key = _non_empty_or_none(settings.deepseek_api_key)
            if key:
                return key
        elif prefix == "gemini":
            key = _non_empty_or_none(settings.gemini_api_key)
            if key:
                return key
        elif prefix == "openrouter":
            key = _non_empty_or_none(settings.openrouter_api_key)
            if key:
                return key

    return _non_empty_or_none(settings.litellm_api_key)
