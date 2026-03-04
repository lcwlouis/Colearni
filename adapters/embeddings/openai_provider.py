"""OpenAI embedding provider adapter."""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.contracts import EmbeddingProvider
from core.rate_limiter import get_embedding_limiter


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by OpenAI's embeddings API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        embedding_dim: int,
        timeout_seconds: float,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is required for provider 'openai'")
        if embedding_dim < 1:
            raise ValueError("embedding_dim must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self._api_key = api_key
        self._model = model
        self._embedding_dim = embedding_dim
        self._timeout_seconds = timeout_seconds
        self._url = f"{base_url.rstrip('/')}/embeddings"

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for every input text."""
        if not texts:
            return []

        payload = {
            "model": self._model,
            "input": list(texts),
        }
        request = Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def _do_request() -> str:
            with urlopen(request, timeout=self._timeout_seconds) as resp:  # noqa: S310
                return resp.read().decode("utf-8")

        try:
            response_body = get_embedding_limiter().execute(_do_request)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
            raise RuntimeError(
                f"OpenAI embeddings request failed with status {exc.code}: {body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"OpenAI embeddings request failed: {exc.reason}") from exc

        parsed = json.loads(response_body)
        raw_items = parsed.get("data")
        if not isinstance(raw_items, list):
            raise ValueError("OpenAI embeddings response missing 'data' list")

        ordered_items = sorted(raw_items, key=lambda item: item.get("index", 0))
        embeddings: list[list[float]] = []
        for item in ordered_items:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("OpenAI embeddings response has invalid embedding payload")
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
