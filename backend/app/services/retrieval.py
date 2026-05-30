from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.embedding_client import EmbeddingClient
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.source import ConceptSourceLink, SourceChunk, SourceRecord, SourceRevision
from backend.app.models.trail import Trail
from backend.app.services.reranker import ChunkSearchResult, RerankerClient
from backend.app.settings import settings

if TYPE_CHECKING:
    from backend.app.services.conversations import TutorSourceMetadata

_ALLOWED_TUTOR_ACCESS = ("public", "private")
_MAX_RETRIEVAL_RESULTS = 10


async def get_concept_sources_for_tutor(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    max_sources: int = 10,
) -> list[TutorSourceMetadata]:
    limit = _clamp_limit(max_sources)
    if limit == 0:
        return []

    rows = await session.execute(
        select(ConceptSourceLink.relation, SourceRecord)
        .join(SourceRecord, ConceptSourceLink.source_id == SourceRecord.id)
        .join(ConceptNode, ConceptSourceLink.concept_id == ConceptNode.id)
        .join(Trail, ConceptNode.trail_id == Trail.id)
        .where(
            ConceptSourceLink.concept_id == concept_id,
            SourceRecord.workspace_id == workspace_id,
            Trail.workspace_id == workspace_id,
            SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
        )
        .order_by(
            _relation_priority(),
            func.lower(SourceRecord.title),
            SourceRecord.title,
            SourceRecord.id,
        )
        .limit(limit)
    )
    return [_to_tutor_source_metadata(relation, source) for relation, source in rows.all()]


def get_graph_neighbourhood(
    *,
    concept: ConceptNode,
    all_nodes: list[ConceptNode],
    edges: list[ConceptEdge],
    max_per_type: int = 5,
) -> dict[str, list[ConceptNode]]:
    node_by_id: dict[uuid.UUID, ConceptNode] = {n.id: n for n in all_nodes}

    prerequisites: list[ConceptNode] = []
    contained_nodes: list[ConceptNode] = []
    containing_nodes: list[ConceptNode] = []
    related: list[ConceptNode] = []
    application_nodes: list[ConceptNode] = []
    seen: set[uuid.UUID] = set()

    for edge in edges:
        src = node_by_id.get(edge.source_node_id)
        tgt = node_by_id.get(edge.target_node_id)
        if src is None or tgt is None:
            continue

        if edge.relation_type == "prerequisite" and edge.target_node_id == concept.id:
            prerequisites.append(src)
        elif edge.relation_type == "contains" and edge.source_node_id == concept.id:
            contained_nodes.append(tgt)
        elif edge.relation_type == "contains" and edge.target_node_id == concept.id:
            containing_nodes.append(src)
        elif edge.relation_type == "application":
            if edge.source_node_id == concept.id and tgt.id not in seen:
                seen.add(tgt.id)
                application_nodes.append(tgt)
            elif edge.target_node_id == concept.id and src.id not in seen:
                seen.add(src.id)
                application_nodes.append(src)
        elif edge.relation_type == "related":
            neighbor = None
            if edge.source_node_id == concept.id:
                neighbor = tgt
            elif edge.target_node_id == concept.id:
                neighbor = src
            if neighbor is not None and neighbor.id not in seen:
                seen.add(neighbor.id)
                related.append(neighbor)

    limit = max(0, max_per_type)
    return {
        "prerequisites": prerequisites[:limit],
        "contained_nodes": contained_nodes[:limit],
        "containing_nodes": containing_nodes[:limit],
        "related": related[:limit],
        "application_nodes": application_nodes[:limit],
    }


async def search_sources_by_title(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    query: str,
    concept_id: uuid.UUID | None = None,
    max_results: int = 5,
) -> list[TutorSourceMetadata]:
    limit = _clamp_limit(max_results)
    normalized_query = query.strip().lower()
    if limit == 0 or not normalized_query:
        return []

    title_filter = func.lower(SourceRecord.title).contains(normalized_query)
    if concept_id is not None:
        rows = await session.execute(
            select(ConceptSourceLink.relation, SourceRecord)
            .join(SourceRecord, ConceptSourceLink.source_id == SourceRecord.id)
            .join(ConceptNode, ConceptSourceLink.concept_id == ConceptNode.id)
            .join(Trail, ConceptNode.trail_id == Trail.id)
            .where(
                ConceptSourceLink.concept_id == concept_id,
                SourceRecord.workspace_id == workspace_id,
                Trail.workspace_id == workspace_id,
                SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
                title_filter,
            )
            .order_by(
                _relation_priority(),
                func.lower(SourceRecord.title),
                SourceRecord.title,
                SourceRecord.id,
            )
            .limit(limit)
        )
        return [_to_tutor_source_metadata(relation, source) for relation, source in rows.all()]

    rows = await session.execute(
        select(SourceRecord)
        .where(
            SourceRecord.workspace_id == workspace_id,
            SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
            title_filter,
        )
        .order_by(func.lower(SourceRecord.title), SourceRecord.title, SourceRecord.id)
        .limit(limit)
    )
    return [_to_tutor_source_metadata("", source) for source in rows.scalars().all()]


async def search_sources_by_text(
    query: str,
    workspace_id: uuid.UUID,
    session: AsyncSession,
    limit: int = 10,
    reranker: RerankerClient | None = None,
    concept_id: uuid.UUID | None = None,
) -> list[ChunkSearchResult]:
    capped_limit = _clamp_limit(limit)
    normalized_query = query.strip()
    if capped_limit == 0 or not normalized_query:
        return []

    rows = await _vector_search_rows(
        normalized_query, workspace_id, session, capped_limit, concept_id=concept_id
    )
    if rows is None:
        rows = await _ilike_search_rows(
            normalized_query, workspace_id, session, capped_limit, concept_id=concept_id
        )

    results = [_to_chunk_search_result(row) for row in rows]
    results = (reranker or RerankerClient.from_settings(settings)).rerank(normalized_query, results)
    return results[:capped_limit]


async def _vector_search_rows(
    query: str,
    workspace_id: uuid.UUID,
    session: AsyncSession,
    limit: int,
    concept_id: uuid.UUID | None = None,
) -> list[tuple[SourceRecord, SourceRevision, SourceChunk, float]] | None:
    try:
        vectors = await EmbeddingClient.from_settings(settings).embed([query])
    except Exception:
        return None
    if vectors is None or not vectors:
        return None
    if not hasattr(SourceChunk.embedding, "cosine_distance"):
        return None

    query_vector = vectors[0]
    distance = SourceChunk.embedding.cosine_distance(query_vector).label("distance")

    stmt = (
        select(SourceRecord, SourceRevision, SourceChunk, distance)
        .join(SourceRevision, SourceRevision.source_id == SourceRecord.id)
        .join(SourceChunk, SourceChunk.source_revision_id == SourceRevision.id)
        .where(
            SourceRecord.workspace_id == workspace_id,
            SourceRevision.workspace_id == workspace_id,
            SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
            SourceChunk.workspace_id == workspace_id,
            SourceChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(limit)
    )
    if concept_id is not None:
        stmt = (
            select(SourceRecord, SourceRevision, SourceChunk, distance)
            .join(SourceRevision, SourceRevision.source_id == SourceRecord.id)
            .join(SourceChunk, SourceChunk.source_revision_id == SourceRevision.id)
            .join(ConceptSourceLink, ConceptSourceLink.source_id == SourceRecord.id)
            .where(
                ConceptSourceLink.concept_id == concept_id,
                SourceRecord.workspace_id == workspace_id,
                SourceRevision.workspace_id == workspace_id,
                SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
                SourceChunk.workspace_id == workspace_id,
                SourceChunk.embedding.is_not(None),
            )
            .distinct()
            .order_by(distance)
            .limit(limit)
        )
    try:
        rows = await session.execute(stmt)
    except SQLAlchemyError:
        return None
    return [
        (source, revision, chunk, distance)
        for source, revision, chunk, distance in rows.all()
    ]


async def _ilike_search_rows(
    query: str,
    workspace_id: uuid.UUID,
    session: AsyncSession,
    limit: int,
    concept_id: uuid.UUID | None = None,
) -> list[tuple[SourceRecord, SourceRevision, SourceChunk]]:
    if concept_id is not None:
        rows = await session.execute(
            select(SourceRecord, SourceRevision, SourceChunk)
            .join(SourceRevision, SourceRevision.source_id == SourceRecord.id)
            .join(SourceChunk, SourceChunk.source_revision_id == SourceRevision.id)
            .join(ConceptSourceLink, ConceptSourceLink.source_id == SourceRecord.id)
            .where(
                ConceptSourceLink.concept_id == concept_id,
                SourceRecord.workspace_id == workspace_id,
                SourceRevision.workspace_id == workspace_id,
                SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
                SourceChunk.workspace_id == workspace_id,
                SourceChunk.text.ilike(f"%{query}%"),
            )
            .distinct()
            .limit(limit)
        )
        return [(source, revision, chunk) for source, revision, chunk in rows.all()]

    rows = await session.execute(
        select(SourceRecord, SourceRevision, SourceChunk)
        .join(SourceRevision, SourceRevision.source_id == SourceRecord.id)
        .join(SourceChunk, SourceChunk.source_revision_id == SourceRevision.id)
        .where(
            SourceRecord.workspace_id == workspace_id,
            SourceRevision.workspace_id == workspace_id,
            SourceRecord.access.in_(_ALLOWED_TUTOR_ACCESS),
            SourceChunk.workspace_id == workspace_id,
            SourceChunk.text.ilike(f"%{query}%"),
        )
        .distinct()
        .limit(limit)
    )
    return [(source, revision, chunk) for source, revision, chunk in rows.all()]


async def read_document_section(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    source_revision_id: uuid.UUID,
    line_start: int,
    window_lines: int = 50,
) -> str:
    """Read a window of lines from SourceRevision.raw_text.

    Returns the markdown text of lines [line_start, line_start + window_lines).
    Line numbers are 1-indexed.

    Raises LookupError if the revision does not exist or belongs to a different workspace.
    window_lines is clamped to [1, 200] rather than rejected.
    """
    _WINDOW_MAX = 200
    if line_start < 1:
        raise ValueError("line_start must be >= 1")
    window_lines = min(max(window_lines, 1), _WINDOW_MAX)

    revision = await session.scalar(
        select(SourceRevision).where(
            SourceRevision.id == source_revision_id,
            SourceRevision.workspace_id == workspace_id,
        )
    )
    if revision is None:
        raise LookupError(f"Source revision {source_revision_id} not found")

    raw_text = revision.raw_text or ""
    lines = raw_text.splitlines()
    start_idx = line_start - 1  # convert to 0-indexed
    end_idx = start_idx + window_lines
    window = lines[start_idx:end_idx]
    return "\n".join(window)


def _clamp_limit(value: int) -> int:
    return max(0, min(value, _MAX_RETRIEVAL_RESULTS))


def _relation_priority():
    return case(
        (ConceptSourceLink.relation == "primary", 0),
        (ConceptSourceLink.relation == "reference", 1),
        else_=2,
    )


def _to_tutor_source_metadata(relation: str, source: SourceRecord) -> TutorSourceMetadata:
    from backend.app.services.conversations import TutorSourceMetadata

    return TutorSourceMetadata(
        id=source.id,
        title=source.title,
        url=source.url,
        origin=source.origin,
        access=source.access,
        license=source.license,
        relation=relation,
    )


def _to_chunk_search_result(
    row: tuple[SourceRecord, SourceRevision, SourceChunk]
    | tuple[SourceRecord, SourceRevision, SourceChunk, float],
) -> ChunkSearchResult:
    if len(row) == 4:
        source, revision, chunk, distance = row
        similarity = 1.0 - float(distance)
    else:
        source, revision, chunk = row
        similarity = None
    return ChunkSearchResult(
        source_id=source.id,
        source_revision_id=revision.id,
        source_title=source.title,
        chunk_text=chunk.text,
        section_heading=chunk.section_heading,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        similarity=similarity,
    )
