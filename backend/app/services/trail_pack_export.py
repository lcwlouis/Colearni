import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.mastery import MasteryRecord
from backend.app.models.research import TrailResearchTrace
from backend.app.models.source import ConceptSourceLink, SourceRecord, SourceRevision
from backend.app.models.trail import Trail
from backend.app.schemas.trail_pack import (
    TrailPack,
    TrailPackConcept,
    TrailPackConceptSourceRef,
    TrailPackExportExcludedReport,
    TrailPackExportIncludedReport,
    TrailPackExportReport,
    TrailPackExportResponse,
    TrailPackGraph,
    TrailPackGraphEdge,
    TrailPackGraphNode,
    TrailPackManifest,
    TrailPackSource,
)


async def export_trail_pack(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> TrailPackExportResponse:
    trail = await _get_scoped_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    nodes = list(
        await session.scalars(
            select(ConceptNode).where(ConceptNode.trail_id == trail_id).order_by(ConceptNode.slug)
        )
    )
    slug_by_id = {node.id: node.slug for node in nodes}
    parent_slugs = {node.slug: set() for node in nodes}
    child_slugs = {node.slug: set() for node in nodes}
    prerequisite_slugs = {node.slug: set() for node in nodes}
    source_refs_by_slug = {node.slug: [] for node in nodes}
    seen_refs_by_slug = {node.slug: set() for node in nodes}

    edges = list(await session.scalars(select(ConceptEdge).where(ConceptEdge.trail_id == trail_id)))
    exported_edges: list[TrailPackGraphEdge] = []
    for edge in sorted(
        edges,
        key=lambda row: (
            slug_by_id.get(row.source_node_id, ""),
            slug_by_id.get(row.target_node_id, ""),
            row.relation_type,
            str(row.id),
        ),
    ):
        source_slug = slug_by_id.get(edge.source_node_id)
        target_slug = slug_by_id.get(edge.target_node_id)
        if source_slug is None or target_slug is None:
            continue
        exported_edges.append(
            TrailPackGraphEdge(
                source=source_slug,
                target=target_slug,
                relation_type=edge.relation_type,
            )
        )
        if edge.relation_type == "contains":
            child_slugs[source_slug].add(target_slug)
            parent_slugs[target_slug].add(source_slug)
        elif edge.relation_type == "prerequisite":
            prerequisite_slugs[target_slug].add(source_slug)

    source_rows = list(
        await session.execute(
            select(ConceptNode.slug, ConceptSourceLink.relation, SourceRecord)
            .join(ConceptSourceLink, ConceptSourceLink.concept_id == ConceptNode.id)
            .join(SourceRecord, SourceRecord.id == ConceptSourceLink.source_id)
            .where(ConceptNode.trail_id == trail_id)
            .order_by(
                ConceptNode.slug,
                SourceRecord.title,
                SourceRecord.id,
                ConceptSourceLink.relation,
            )
        )
    )
    exported_sources_by_id: dict[uuid.UUID, TrailPackSource] = {}
    excluded_uploaded_source_ids: set[uuid.UUID] = set()
    linked_source_ids: set[uuid.UUID] = set()
    included_source_links = 0

    for concept_slug, relation, source in source_rows:
        if source.workspace_id != workspace_id:
            continue
        linked_source_ids.add(source.id)
        if source.origin == "user_upload":
            excluded_uploaded_source_ids.add(source.id)
            continue
        if not _can_include_source_in_public_export(source):
            continue

        ref_key = (source.id, relation)
        if ref_key in seen_refs_by_slug[concept_slug]:
            continue
        seen_refs_by_slug[concept_slug].add(ref_key)
        source_refs_by_slug[concept_slug].append(
            TrailPackConceptSourceRef(source_id=source.id, relation=relation)
        )
        included_source_links += 1
        exported_sources_by_id.setdefault(
            source.id,
            TrailPackSource(
                id=source.id,
                title=source.title,
                url=source.url,
                origin=source.origin,
                access=source.access,
                license=source.license,
                include_on_public_export=source.include_on_public_export,
            ),
        )

    concepts = {
        node.slug: TrailPackConcept(
            id=node.slug,
            title=node.title,
            node_type=node.node_type,
            concept_level=node.concept_level,
            parents=sorted(parent_slugs[node.slug]),
            prerequisites=sorted(prerequisite_slugs[node.slug]),
            children=sorted(child_slugs[node.slug]),
            learning_objectives=[],
            mastery_check_labels=list(node.mastery_check_labels),
            source_refs=source_refs_by_slug[node.slug],
            hydration_required=bool(source_refs_by_slug[node.slug]),
        )
        for node in nodes
    }

    has_mastery_records = bool(
        await session.scalar(
            select(func.count(MasteryRecord.id))
            .join(ConceptNode, ConceptNode.id == MasteryRecord.concept_id)
            .where(
                ConceptNode.trail_id == trail_id,
                MasteryRecord.workspace_id == workspace_id,
            )
        )
    )
    source_revision_count = 0
    if linked_source_ids:
        source_revision_count = await session.scalar(
            select(func.count(SourceRevision.id)).where(
                SourceRevision.workspace_id == workspace_id,
                SourceRevision.source_id.in_(linked_source_ids),
            )
        ) or 0
    research_trace = await session.scalar(
        select(TrailResearchTrace).where(
            TrailResearchTrace.workspace_id == workspace_id,
            TrailResearchTrace.trail_id == trail_id,
        )
    )
    research_trace_json = research_trace.trace_json if research_trace else {}

    pack = TrailPack(
        manifest=TrailPackManifest(
            id=_build_pack_id(trail),
            title=trail.title,
            topic=trail.topic,
            goal=trail.goal,
            target_depth=trail.target_depth,
        ),
        graph=TrailPackGraph(
            nodes=[
                TrailPackGraphNode(
                    id=node.slug,
                    title=node.title,
                    node_type=node.node_type,
                    concept_level=node.concept_level,
                    difficulty=node.difficulty,
                    bloom_level=node.bloom_level,
                )
                for node in nodes
            ],
            edges=exported_edges,
        ),
        concepts=concepts,
        sources=sorted(
            exported_sources_by_id.values(),
            key=lambda source: (source.title.lower(), str(source.id)),
        ),
        research_trace=research_trace_json,
    )
    return TrailPackExportResponse(
        pack=pack,
        report=TrailPackExportReport(
            included=TrailPackExportIncludedReport(
                concepts=len(nodes),
                edges=len(exported_edges),
                source_links=included_source_links,
                has_research_trace=bool(research_trace_json),
            ),
            excluded=TrailPackExportExcludedReport(
                uploaded_files=len(excluded_uploaded_source_ids),
                source_revisions=source_revision_count or 0,
                chunks=0,
                embeddings=0,
                private_notes=0,
                mastery_records=has_mastery_records,
            ),
        ),
    )


def _can_include_source_in_public_export(source: SourceRecord) -> bool:
    return (
        source.origin == "research_agent"
        and source.access == "public"
        and source.include_on_public_export is True
    )


def _build_pack_id(trail: Trail) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", trail.title.lower()).strip("-")
    return slug or str(trail.id)


async def _get_scoped_trail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> Trail:
    trail = await session.scalar(
        select(Trail).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")
    return trail
