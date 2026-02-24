"""Core protocol contracts shared across layers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Protocol

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


class GraphLLMClient(Protocol):
    """Protocol for LLM-based graph extraction and disambiguation."""

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        """Extract schema-shaped concept and edge candidates from a chunk."""

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        """Choose merge target vs create-new from bounded candidate set."""
