from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.source import ConceptSourceLink, SourceRecord
from backend.app.models.trail import Trail

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
