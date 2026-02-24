"""Types for chunk retrieval outputs."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedChunk:
    """Ranked retrieval result for a chunk."""

    chunk_id: int
    document_id: int
    chunk_index: int
    text: str
    score: float
