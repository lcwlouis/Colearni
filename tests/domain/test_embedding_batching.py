"""Unit tests for embedding batching behavior."""

from collections.abc import Sequence

import pytest
from core.contracts import EmbeddingProvider
from domain.embeddings.pipeline import embed_texts_batched


class RecordingProvider(EmbeddingProvider):
    """Embedding provider test double that records calls."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text))] for text in texts]


class MismatchProvider(EmbeddingProvider):
    """Provider test double that intentionally returns bad counts."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if len(texts) <= 1:
            return [[1.0] for _ in texts]
        return [[1.0] for _ in texts[:-1]]


def test_embed_texts_batched_splits_into_bounded_batches() -> None:
    """Batching should split input by batch_size and preserve ordering."""
    provider = RecordingProvider()

    output = embed_texts_batched(
        provider=provider,
        texts=["a", "bb", "ccc", "dddd", "eeeee"],
        batch_size=2,
    )

    assert provider.calls == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert output == [[1.0], [2.0], [3.0], [4.0], [5.0]]


def test_embed_texts_batched_raises_on_provider_count_mismatch() -> None:
    """Batching should fail fast when provider cardinality is invalid."""
    provider = MismatchProvider()

    with pytest.raises(ValueError, match="expected 2, got 1"):
        embed_texts_batched(provider=provider, texts=["alpha", "beta"], batch_size=2)
