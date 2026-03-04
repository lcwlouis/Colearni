"""Unit tests for full-text retriever mapping behavior."""

from __future__ import annotations

import pytest
from adapters.db import chunks_repository
from domain.retrieval.fts_retriever import PgFtsRetriever


def test_fts_retrieve_clamps_top_k_and_maps_canonical_ranked_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FTS retriever should clamp top_k and map rows to RankedChunk contract."""
    captured: dict[str, object] = {}

    def fake_full_text_top_k(session, query, workspace_id, top_k):  # noqa: ANN001, ANN202
        captured["session"] = session
        captured["query"] = query
        captured["workspace_id"] = workspace_id
        captured["top_k"] = top_k
        return [
            chunks_repository.FullTextSearchRow(
                chunk_id=5,
                document_id=10,
                chunk_index=3,
                text="fts hit one",
                fts_rank=0.9,
            ),
        ]

    monkeypatch.setattr(chunks_repository, "full_text_top_k", fake_full_text_top_k)

    retriever = PgFtsRetriever(session=object(), retrieval_max_top_k=1)
    ranked = retriever.retrieve(query="entropy", workspace_id=77, top_k=10)

    assert captured["query"] == "entropy"
    assert captured["workspace_id"] == 77
    assert captured["top_k"] == 1
    assert len(ranked) == 1
    assert ranked[0].workspace_id == 77
    assert ranked[0].document_id == 10
    assert ranked[0].chunk_id == 5
    assert ranked[0].chunk_index == 3
    assert ranked[0].text == "fts hit one"
    assert ranked[0].score == pytest.approx(0.9)
    assert ranked[0].retrieval_method == "fts"


def test_fts_retrieve_enforces_minimum_top_k_of_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """FTS retriever should force top_k >= 1 before querying."""
    captured: dict[str, int] = {}

    def fake_full_text_top_k(session, query, workspace_id, top_k):  # noqa: ANN001, ANN202
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr(chunks_repository, "full_text_top_k", fake_full_text_top_k)

    retriever = PgFtsRetriever(session=object(), retrieval_max_top_k=20)
    ranked = retriever.retrieve(query="anything", workspace_id=7, top_k=0)

    assert captured["top_k"] == 1
    assert ranked == []
