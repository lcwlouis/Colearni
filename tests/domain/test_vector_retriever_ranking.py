"""Unit tests for pgvector retriever ranking behavior."""

from collections.abc import Sequence

import pytest
from adapters.db import chunks_repository
from core.contracts import EmbeddingProvider
from domain.retrieval.vector_retriever import PgVectorRetriever


class FakeProvider(EmbeddingProvider):
    """Simple provider double that records query embeds."""

    def __init__(self, response: list[list[float]]) -> None:
        self._response = response
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return self._response


def test_retrieve_clamps_top_k_and_applies_deterministic_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retriever should clamp top_k and rank by (distance, chunk_id)."""
    captured: dict[str, object] = {}

    def fake_vector_top_k(session, query_embedding, workspace_id, top_k):  # noqa: ANN001, ANN202
        captured["session"] = session
        captured["query_embedding"] = query_embedding
        captured["workspace_id"] = workspace_id
        captured["top_k"] = top_k
        return [
            chunks_repository.VectorSearchRow(
                chunk_id=9,
                document_id=11,
                chunk_index=2,
                text="second tie",
                cosine_distance=0.4,
            ),
            chunks_repository.VectorSearchRow(
                chunk_id=3,
                document_id=10,
                chunk_index=1,
                text="best",
                cosine_distance=0.1,
            ),
            chunks_repository.VectorSearchRow(
                chunk_id=5,
                document_id=11,
                chunk_index=1,
                text="first tie",
                cosine_distance=0.4,
            ),
        ]

    monkeypatch.setattr(chunks_repository, "vector_top_k", fake_vector_top_k)

    provider = FakeProvider(response=[[0.2, 0.3, 0.4]])
    sentinel_session = object()
    retriever = PgVectorRetriever(
        session=sentinel_session,
        embedding_provider=provider,
        retrieval_max_top_k=2,
    )

    ranked = retriever.retrieve(query="what is cosine", workspace_id=42, top_k=99)

    assert provider.calls == [["what is cosine"]]
    assert captured["session"] is sentinel_session
    assert captured["workspace_id"] == 42
    assert captured["top_k"] == 2
    assert captured["query_embedding"] == [0.2, 0.3, 0.4]
    assert [item.chunk_id for item in ranked] == [3, 5]
    assert [item.chunk_index for item in ranked] == [1, 1]
    assert [item.workspace_id for item in ranked] == [42, 42]
    assert [item.document_id for item in ranked] == [10, 11]
    assert [item.text for item in ranked] == ["best", "first tie"]
    assert [item.retrieval_method for item in ranked] == ["vector", "vector"]
    assert ranked[0].score == pytest.approx(0.9)
    assert ranked[1].score == pytest.approx(0.6)


def test_retrieve_enforces_minimum_top_k_of_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retriever should clamp non-positive top_k to 1."""
    captured: dict[str, int] = {}

    def fake_vector_top_k(session, query_embedding, workspace_id, top_k):  # noqa: ANN001, ANN202
        captured["top_k"] = top_k
        return [
            chunks_repository.VectorSearchRow(
                chunk_id=1,
                document_id=2,
                chunk_index=3,
                text="only",
                cosine_distance=0.25,
            )
        ]

    monkeypatch.setattr(chunks_repository, "vector_top_k", fake_vector_top_k)

    retriever = PgVectorRetriever(
        session=object(),
        embedding_provider=FakeProvider(response=[[0.1]]),
        retrieval_max_top_k=20,
    )

    ranked = retriever.retrieve(query="x", workspace_id=7, top_k=0)

    assert captured["top_k"] == 1
    assert len(ranked) == 1
    assert ranked[0].workspace_id == 7
    assert ranked[0].chunk_index == 3
    assert ranked[0].text == "only"
    assert ranked[0].retrieval_method == "vector"


def test_retrieve_requires_single_query_embedding() -> None:
    """Retriever should fail fast if provider returns invalid query embedding count."""
    retriever = PgVectorRetriever(
        session=object(),
        embedding_provider=FakeProvider(response=[]),
        retrieval_max_top_k=5,
    )

    with pytest.raises(ValueError, match="exactly one query embedding"):
        retriever.retrieve(query="bad", workspace_id=1, top_k=1)
