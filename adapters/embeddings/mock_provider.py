"""Deterministic mock embedding provider for tests/local runs."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from core.contracts import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Generate deterministic unit-length embeddings from text."""

    def __init__(self, embedding_dim: int) -> None:
        if embedding_dim < 1:
            raise ValueError("embedding_dim must be positive")
        self._embedding_dim = embedding_dim

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors for each input text."""
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [
            ((digest[index % len(digest)] / 255.0) * 2.0) - 1.0
            for index in range(self._embedding_dim)
        ]
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            return [0.0] * self._embedding_dim
        return [value / norm for value in values]
