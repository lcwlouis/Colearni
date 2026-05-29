from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.app.settings import Settings


@dataclass
class ChunkSearchResult:
    """Chunk-level retrieval result with line navigation metadata."""

    source_id: uuid.UUID
    source_revision_id: uuid.UUID
    source_title: str
    chunk_text: str
    section_heading: str | None
    line_start: int
    line_end: int
    similarity: float | None


class RerankerClient:
    """Pipeline stage for reranking chunk retrieval results."""

    def __init__(self, provider: str = "none", api_key: str = "") -> None:
        self.provider = provider
        self.api_key = api_key

    @classmethod
    def from_settings(cls, settings: Settings) -> RerankerClient:
        return cls(provider=settings.reranker_provider, api_key=settings.reranker_api_key)

    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Return candidates in reranked order. No-op returns input order."""
        return candidates
