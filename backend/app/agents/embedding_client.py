from __future__ import annotations

from backend.app.settings import Settings

EMBEDDING_PROVIDER_BASE_URLS: dict[str, str] = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "ollama": "http://localhost:11434/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class EmbeddingClient:
    """Multi-provider embedding client using OpenAI SDK base_url overrides."""

    def __init__(
        self,
        *,
        provider: str = "disabled",
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
        api_key: str = "",
        api_base: str = "",
        client=None,
    ) -> None:
        self._provider = provider.lower()
        self._model = model
        self._dimensions = dimensions
        self._api_key = api_key
        self._api_base = api_base
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> EmbeddingClient:
        provider = settings.embedding_provider.lower()
        api_key = settings.embedding_api_key
        if provider == "ollama" and not api_key:
            api_key = "ollama"
        if not api_key and provider in {"openai", settings.llm_provider.lower()}:
            api_key = settings.llm_api_key
        return cls(
            provider=provider,
            model=settings.embedding_model,
            dimensions=settings.embedding_dim,
            api_key=api_key,
            api_base=settings.embedding_api_base,
        )

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Return embedding vectors, or None when embeddings are disabled."""
        if self._provider == "disabled":
            return None
        if not texts:
            return []
        client = self._client or self._openai_client()
        params: dict[str, object] = {"model": self._model, "input": texts}
        if self._should_request_dimensions():
            params["dimensions"] = self._dimensions
        response = await client.embeddings.create(**params)
        vectors = [item.embedding for item in response.data]
        self._validate_dimensions(vectors)
        return vectors

    def _should_request_dimensions(self) -> bool:
        if self._dimensions is None:
            return False
        # Ollama's OpenAI-compatible embedding endpoint does not consistently
        # support the dimensions parameter. Fixed-size local models are instead
        # validated after the response.
        return self._provider != "ollama"

    def _validate_dimensions(self, vectors: list[list[float]]) -> None:
        if self._dimensions is None:
            return
        for index, vector in enumerate(vectors):
            if len(vector) != self._dimensions:
                raise ValueError(
                    f"Embedding provider returned {len(vector)} dimensions for item {index}, "
                    f"but EMBEDDING_DIM is {self._dimensions}. Configure the provider/model "
                    "to return the same dimension as the database vector column."
                )

    def _openai_client(self):  # type: ignore[return]
        from openai import AsyncOpenAI

        kwargs: dict[str, str] = {"api_key": self._api_key}
        base_url = self._base_url()
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)

    def _base_url(self) -> str:
        if self._provider == "openai":
            return ""
        if self._provider == "openai_compatible":
            return self._api_base
        return EMBEDDING_PROVIDER_BASE_URLS.get(self._provider, "")
