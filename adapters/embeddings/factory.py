"""Factory helpers for embedding providers."""

from core.contracts import EmbeddingProvider
from core.settings import Settings, get_settings

from adapters.embeddings.mock_provider import MockEmbeddingProvider
from adapters.embeddings.openai_provider import OpenAIEmbeddingProvider


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Build the configured embedding provider implementation."""
    active_settings = settings or get_settings()

    if active_settings.embedding_provider == "mock":
        return MockEmbeddingProvider(embedding_dim=active_settings.embedding_dim)

    if active_settings.embedding_provider == "openai":
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

    raise ValueError(f"Unsupported embedding provider: {active_settings.embedding_provider}")
