"""Types for chunk retrieval outputs."""

from dataclasses import dataclass
from typing import Literal

RetrievalMethod = Literal["vector", "fts", "hybrid"]


@dataclass(frozen=True, slots=True)
class RankedChunk:
    """Ranked retrieval result for a chunk."""

    workspace_id: int
    document_id: int
    chunk_id: int
    snippet: str
    score: float
    retrieval_method: RetrievalMethod
