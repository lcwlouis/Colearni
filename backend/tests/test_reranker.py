import uuid

from backend.app.services.reranker import ChunkSearchResult, RerankerClient


def test_reranker_none_returns_candidates_unchanged():
    candidate = _candidate()
    candidates = [candidate]

    assert RerankerClient(provider="none").rerank("query", candidates) is candidates


def test_chunk_search_result_constructable():
    result = _candidate()

    assert result.source_title == "Title"
    assert result.line_start == 1


def _candidate() -> ChunkSearchResult:
    return ChunkSearchResult(
        source_id=uuid.uuid4(),
        source_revision_id=uuid.uuid4(),
        source_title="Title",
        chunk_text="Chunk",
        section_heading="Section",
        line_start=1,
        line_end=2,
        similarity=None,
    )
