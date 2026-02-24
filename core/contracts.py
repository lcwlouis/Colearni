"""Core protocol contracts shared across layers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from domain.retrieval.types import RankedChunk


class EmbeddingProvider(Protocol):
    """Protocol for embedding model adapters."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class ChunkRetriever(Protocol):
    """Protocol for chunk retrieval implementations."""

    def retrieve(self, query: str, workspace_id: int, top_k: int) -> list["RankedChunk"]:
        """Return ranked chunk matches for a query within one workspace."""
