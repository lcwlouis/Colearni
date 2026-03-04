"""Unit tests for hybrid vector + FTS reranking."""

from __future__ import annotations

import pytest
from domain.retrieval.hybrid_retriever import HybridRetriever
from domain.retrieval.types import RankedChunk, RetrievalMethod


class StubRetriever:
    """Simple retriever stub that records calls and truncates by top_k."""

    def __init__(self, rows: list[RankedChunk]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, int, int]] = []

    def retrieve(self, query: str, workspace_id: int, top_k: int) -> list[RankedChunk]:
        self.calls.append((query, workspace_id, top_k))
        return self._rows[:top_k]


def _row(chunk_id: int, method: RetrievalMethod = "vector") -> RankedChunk:
    return RankedChunk(
        workspace_id=7,
        document_id=10,
        chunk_id=chunk_id,
        chunk_index=chunk_id % 5,
        text=f"chunk-{chunk_id}",
        score=1.0,
        retrieval_method=method,
    )


def test_hybrid_retriever_merges_disjoint_and_overlapping_candidates() -> None:
    """Hybrid retriever should apply weighted RRF and method labels deterministically."""
    vector = StubRetriever(rows=[_row(10), _row(20), _row(30)])
    fts = StubRetriever(rows=[_row(30, "fts"), _row(40, "fts"), _row(20, "fts")])
    retriever = HybridRetriever(vector_retriever=vector, fts_retriever=fts, retrieval_max_top_k=10)

    ranked = retriever.retrieve(query="hybrid", workspace_id=7, top_k=10)

    assert [row.chunk_id for row in ranked] == [30, 20, 10, 40]
    assert [row.retrieval_method for row in ranked] == ["hybrid", "hybrid", "vector", "fts"]
    assert ranked[0].score == pytest.approx((0.6 / (60 + 3)) + (0.4 / (60 + 1)))
    assert ranked[1].score == pytest.approx((0.6 / (60 + 2)) + (0.4 / (60 + 3)))
    assert ranked[2].score == pytest.approx(0.6 / (60 + 1))
    assert ranked[3].score == pytest.approx(0.4 / (60 + 2))


def test_hybrid_retriever_tie_break_and_top_k_clamp_are_deterministic() -> None:
    """Tie breaks should be stable and bounded top_k should propagate to both sources."""
    vector = StubRetriever(rows=[_row(100), _row(101), _row(102)])
    fts = StubRetriever(rows=[_row(200, "fts"), _row(201, "fts"), _row(202, "fts")])
    retriever = HybridRetriever(
        vector_retriever=vector,
        fts_retriever=fts,
        retrieval_max_top_k=2,
        vector_weight=1.0,
        fts_weight=1.0,
    )

    ranked = retriever.retrieve(query="tie", workspace_id=7, top_k=99)

    assert vector.calls == [("tie", 7, 2)]
    assert fts.calls == [("tie", 7, 2)]
    assert len(ranked) == 2
    assert ranked[0].chunk_id == 100
    assert ranked[1].chunk_id == 200
    assert ranked[0].score == pytest.approx(ranked[1].score)
