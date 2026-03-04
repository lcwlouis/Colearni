"""LiteLLM embedding provider adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import litellm
from core.contracts import EmbeddingProvider
from core.rate_limiter import get_embedding_limiter


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by LiteLLM's Python SDK."""

    def __init__(
        self,
        model: str,
        embedding_dim: int,
        timeout_seconds: float,
        api_base: str | None = None,
        api_key: str | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("LiteLLM model is required for provider 'litellm'")
        if embedding_dim < 1:
            raise ValueError("embedding_dim must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self._model = model
        self._embedding_dim = embedding_dim
        self._timeout_seconds = timeout_seconds
        self._api_base = api_base
        self._api_key = api_key

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for every input text."""
        if not texts:
            return []

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "input": list(texts),
            "timeout": self._timeout_seconds,
        }
        if self._api_base is not None:
            request_kwargs["api_base"] = self._api_base
        if self._api_key is not None:
            request_kwargs["api_key"] = self._api_key

        try:
            response = get_embedding_limiter().execute(litellm.embedding, **request_kwargs)
        except Exception as exc:
            raise RuntimeError(f"LiteLLM embeddings request failed: {exc}") from exc

        raw_items = self._extract_data(response)
        if not isinstance(raw_items, list):
            raise ValueError("LiteLLM embeddings response missing 'data' list")

        ordered_items = sorted(raw_items, key=self._extract_index)
        embeddings: list[list[float]] = []
        for item in ordered_items:
            embedding = self._extract_embedding(item)
            if len(embedding) != self._embedding_dim:
                raise ValueError(
                    "Embedding dimension mismatch: "
                    f"expected {self._embedding_dim}, got {len(embedding)}"
                )
            embeddings.append([float(value) for value in embedding])

        if len(embeddings) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}"
            )

        return embeddings

    @staticmethod
    def _extract_data(response: object) -> object:
        if isinstance(response, Mapping):
            return response.get("data")

        if hasattr(response, "get"):
            try:
                return response.get("data")  # type: ignore[call-arg]
            except TypeError:
                pass

        return getattr(response, "data", None)

    @classmethod
    def _extract_index(cls, item: object) -> int:
        payload = cls._as_mapping(item)
        index = payload.get("index", 0)
        if isinstance(index, int):
            return index
        try:
            return int(index)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _extract_embedding(cls, item: object) -> list[object]:
        payload = cls._as_mapping(item)
        embedding = payload.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError("LiteLLM embeddings response has invalid embedding payload")
        return embedding

    @staticmethod
    def _as_mapping(item: object) -> Mapping[str, object]:
        if isinstance(item, Mapping):
            return item

        if hasattr(item, "model_dump"):
            model_dump = item.model_dump()
            if isinstance(model_dump, Mapping):
                return model_dump

        if hasattr(item, "dict"):
            raw_dict = item.dict()
            if isinstance(raw_dict, Mapping):
                return raw_dict

        raise ValueError("LiteLLM embeddings response has invalid item payload")
