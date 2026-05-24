import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.research import TrailResearchTrace
from backend.app.models.source import ConceptSourceLink, SourceRecord
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.concept import ConceptEdgeRead, ConceptNodeRead
from backend.app.schemas.mastery import MasteryRecordRead
from backend.app.schemas.trail import TrailGraphRead, TrailRead
from backend.app.schemas.trail_pack_import import (
    HydrationResponse,
    HydrationSkippedSource,
    ImportResearchTrace,
    ImportTrailPack,
    ResearchTraceResponse,
    TrailPackImportReport,
    TrailPackImportResponse,
)

UNSAFE_FIELDS = {
    "raw_chunks",
    "chunks",
    "embeddings",
    "embedding",
    "uploaded_files",
    "uploaded_file",
    "private_notes",
    "private_note",
    "mastery_records",
    "mastery",
    "chat_history",
    "conversation_history",
    "raw_prose",
    "raw_text",
    "source_text",
    "source_content",
    "generated_summary",
    "generated_summaries",
    "generated_quiz",
    "generated_quizzes",
}


class TrailPackImportError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def import_trail_pack(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    payload: dict[str, Any],
) -> TrailPackImportResponse:
    await _require_workspace(session, workspace_id)
    pack_payload = _unwrap_payload(payload)
    _reject_unsafe_fields(pack_payload)

    try:
        pack = ImportTrailPack.model_validate(pack_payload)
    except ValidationError as exc:
        raise TrailPackImportError(str(exc)) from exc

    _validate_pack(pack)
    return await _persist_import(session, workspace_id=workspace_id, pack=pack)


async def get_research_trace(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> ResearchTraceResponse:
    await _get_scoped_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    trace = await session.scalar(
        select(TrailResearchTrace).where(
            TrailResearchTrace.workspace_id == workspace_id,
            TrailResearchTrace.trail_id == trail_id,
        )
    )
    return ResearchTraceResponse(trace=trace.trace_json if trace else {})


async def hydrate_trail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    source_ids: list[uuid.UUID],
    use_model_knowledge: bool,
) -> HydrationResponse:
    if not source_ids and not use_model_knowledge:
        raise TrailPackImportError(
            "Hydration requires source_ids or use_model_knowledge=true"
        )
    await _get_scoped_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    concept: ConceptNode | None = None
    if concept_id is not None:
        concept = await session.scalar(
            select(ConceptNode).where(
                ConceptNode.id == concept_id,
                ConceptNode.trail_id == trail_id,
            )
        )
        if concept is None:
            raise LookupError(f"Concept {concept_id} not found")

    try:
        skipped: list[HydrationSkippedSource] = []
        created_sources: list[SourceRecord] = []
        seen_source_ids: set[uuid.UUID] = set()

        for source_id in source_ids:
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            source = await session.scalar(
                select(SourceRecord).where(
                    SourceRecord.id == source_id,
                    SourceRecord.workspace_id == workspace_id,
                )
            )
            if source is None:
                skipped.append(
                    HydrationSkippedSource(source_id=source_id, reason="source_not_found")
                )
                continue
            if source.access != "public" or source.origin != "research_agent":
                skipped.append(
                    HydrationSkippedSource(source_id=source_id, reason="source_not_public_research")
                )
                continue
            if not await _source_linked_to_trail(session, source_id=source.id, trail_id=trail_id):
                skipped.append(
                    HydrationSkippedSource(source_id=source_id, reason="source_not_in_trail")
                )
                continue

            hydrated = SourceRecord(
                workspace_id=workspace_id,
                origin="manual",
                access="private",
                title=f"Hydration placeholder: {source.title}",
                url=source.url,
                license=source.license,
                include_on_public_export=False,
                metadata_json={
                    "hydration_status": "placeholder_only",
                    "original_source_id": str(source.id),
                    "original_url": source.url,
                    "original_access": source.access,
                    "original_license": source.license,
                    "use_model_knowledge": use_model_knowledge,
                    "reason": (
                        "Phase 7 hydration MVP records private intent only; "
                        "no fetching/indexing."
                    ),
                },
            )
            session.add(hydrated)
            created_sources.append(hydrated)

        if use_model_knowledge:
            hydrated = SourceRecord(
                workspace_id=workspace_id,
                origin="manual",
                access="private",
                title="Hydration placeholder: model knowledge requested",
                url=None,
                license=None,
                include_on_public_export=False,
                metadata_json={
                    "hydration_status": "placeholder_only",
                    "use_model_knowledge": True,
                    "reason": (
                        "Learner requested model-knowledge hydration; "
                        "no generated content stored."
                    ),
                },
            )
            session.add(hydrated)
            created_sources.append(hydrated)

        await session.flush()
        if concept is not None:
            for source in created_sources:
                session.add(
                    ConceptSourceLink(
                        concept_id=concept.id,
                        source_id=source.id,
                        relation="hydration",
                    )
                )

        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return HydrationResponse(
        hydrated_concepts=1 if concept is not None and created_sources else 0,
        private_records_created=len(created_sources),
        skipped_sources=skipped,
    )


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TrailPackImportError("Trail Pack payload must be a JSON object")
    if "pack" in payload:
        unexpected = set(payload) - {"pack", "report"}
        if unexpected:
            raise TrailPackImportError(
                f"Unsupported export wrapper fields: {', '.join(sorted(unexpected))}"
            )
        pack = payload.get("pack")
        if not isinstance(pack, dict):
            raise TrailPackImportError("Export wrapper field 'pack' must be an object")
        return pack
    return payload


def _reject_unsafe_fields(value: Any, *, path: str = "pack") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in UNSAFE_FIELDS:
                if not (key == "mastery" and _is_graph_mastery_path(path)):
                    raise TrailPackImportError(f"Unsafe Trail Pack field rejected at {path}.{key}")
            _reject_unsafe_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_unsafe_fields(child, path=f"{path}[{index}]")


def _validate_pack(pack: ImportTrailPack) -> None:
    if pack.manifest.content_included:
        raise TrailPackImportError("Trail Pack content_included must be false")

    node_ids = [node.id for node in pack.graph.nodes]
    duplicate_node_ids = _duplicates(node_ids)
    if duplicate_node_ids:
        raise TrailPackImportError(f"Duplicate node ids: {', '.join(duplicate_node_ids)}")
    if not node_ids:
        raise TrailPackImportError("Trail Pack graph must contain at least one node")

    node_id_set = set(node_ids)
    for edge in pack.graph.edges:
        if edge.source not in node_id_set:
            raise TrailPackImportError(f"Edge references unknown source node: {edge.source}")
        if edge.target not in node_id_set:
            raise TrailPackImportError(f"Edge references unknown target node: {edge.target}")

    concept_keys = set(pack.concepts)
    missing_concept_ids = sorted(node_id_set - concept_keys)
    if missing_concept_ids:
        raise TrailPackImportError(
            "Missing concept payloads for graph node ids: " + ", ".join(missing_concept_ids)
        )
    for concept_key, concept in pack.concepts.items():
        if concept.id != concept_key:
            raise TrailPackImportError(f"Concept key/id mismatch for {concept_key}")
        if concept.id not in node_id_set:
            raise TrailPackImportError(f"Concept references unknown graph node: {concept.id}")
        if concept.content_included:
            raise TrailPackImportError(f"Concept {concept.id} includes content")

    duplicate_slugs = _duplicates([_slug_for_node(node.id) for node in pack.graph.nodes])
    if duplicate_slugs:
        raise TrailPackImportError(f"Duplicate concept slugs: {', '.join(duplicate_slugs)}")

    source_ids = [source.id for source in pack.sources]
    duplicate_source_ids = _duplicates(source_ids)
    if duplicate_source_ids:
        raise TrailPackImportError(f"Duplicate source ids: {', '.join(duplicate_source_ids)}")

    for source in pack.sources:
        if source.content_included:
            raise TrailPackImportError(f"Source {source.id} includes content")
        if not _safe_public_source(source.origin, source.access, source.include_on_public_export):
            raise TrailPackImportError(f"Unsafe source rejected: {source.id}")

    if concept_keys - node_id_set:
        raise TrailPackImportError("Concepts contain ids not present in graph")


async def _persist_import(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    pack: ImportTrailPack,
) -> TrailPackImportResponse:
    try:
        trail = Trail(
            workspace_id=workspace_id,
            title=pack.manifest.title,
            topic=pack.manifest.topic or pack.manifest.title,
            goal=pack.manifest.goal or "Imported from Trail Pack",
            target_depth=pack.manifest.target_depth or "understand",
        )
        session.add(trail)
        await session.flush()

        concept_by_id = {concept.id: concept for concept in pack.concepts.values()}
        node_by_import_id: dict[str, ConceptNode] = {}
        nodes: list[ConceptNode] = []
        for import_node in pack.graph.nodes:
            concept = concept_by_id[import_node.id]
            node = ConceptNode(
                trail_id=trail.id,
                slug=_slug_for_node(import_node.id),
                title=concept.title,
                node_type=concept.node_type,
                concept_level=concept.concept_level,
                difficulty=import_node.difficulty or "beginner",
                bloom_level=import_node.bloom_level or "understand",
                mastery_check_labels=concept.mastery_check_labels,
                metadata_json={"imported_pack_node_id": import_node.id},
            )
            session.add(node)
            node_by_import_id[import_node.id] = node
            nodes.append(node)
        await session.flush()

        edges: list[ConceptEdge] = []
        for import_edge in pack.graph.edges:
            edge = ConceptEdge(
                trail_id=trail.id,
                source_node_id=node_by_import_id[import_edge.source].id,
                target_node_id=node_by_import_id[import_edge.target].id,
                relation_type=import_edge.relation_type,
            )
            session.add(edge)
            edges.append(edge)

        source_by_import_id: dict[str, SourceRecord] = {}
        for import_source in pack.sources:
            source = SourceRecord(
                workspace_id=workspace_id,
                origin=import_source.origin,
                access=import_source.access,
                title=import_source.title,
                url=import_source.url,
                license=import_source.license,
                include_on_public_export=import_source.include_on_public_export,
                metadata_json={"imported_pack_source_id": import_source.id},
            )
            session.add(source)
            source_by_import_id[import_source.id] = source
        await session.flush()

        missing_source_refs: set[str] = set()
        for concept in pack.concepts.values():
            node = node_by_import_id[concept.id]
            for source_ref in concept.source_refs:
                source = source_by_import_id.get(source_ref.source_id)
                if source is None:
                    missing_source_refs.add(source_ref.source_id)
                    continue
                session.add(
                    ConceptSourceLink(
                        concept_id=node.id,
                        source_id=source.id,
                        relation=source_ref.relation,
                    )
                )

        if _trace_has_data(pack.research_trace):
            session.add(
                TrailResearchTrace(
                    workspace_id=workspace_id,
                    trail_id=trail.id,
                    trace_json=pack.research_trace.model_dump(mode="json"),
                )
            )

        await session.commit()
        await session.refresh(trail)
    except Exception:
        await session.rollback()
        raise

    warnings = []
    if missing_source_refs:
        warnings.append(
            "Missing source refs not imported: " + ", ".join(sorted(missing_source_refs))
        )
    if pack.manifest.topic is None:
        warnings.append("Manifest topic missing; defaulted trail.topic to manifest.title")
    if pack.manifest.goal is None:
        warnings.append("Manifest goal missing; defaulted trail.goal to 'Imported from Trail Pack'")
    if pack.manifest.target_depth is None:
        warnings.append("Manifest target_depth missing; defaulted to 'understand'")
    if any(node.difficulty is None for node in pack.graph.nodes):
        warnings.append("Node difficulty missing; defaulted missing values to 'beginner'")
    if any(node.bloom_level is None for node in pack.graph.nodes):
        warnings.append("Node bloom_level missing; defaulted missing values to 'understand'")

    nodes.sort(key=lambda node: node.slug)

    trail_read = TrailRead.model_validate(trail)
    trail_read.node_count = len(nodes)
    trail_read.edge_count = len(edges)
    return TrailPackImportResponse(
        trail=trail_read,
        graph=TrailGraphRead(
            nodes=[ConceptNodeRead.model_validate(node) for node in nodes],
            edges=[ConceptEdgeRead.model_validate(edge) for edge in edges],
            mastery={
                node.id: MasteryRecordRead(
                    id=None,
                    workspace_id=workspace_id,
                    concept_id=node.id,
                    status="not_started",
                    bloom_level=node.bloom_level,
                    score=0.0,
                    updated_at=None,
                )
                for node in nodes
            },
        ),
        report=TrailPackImportReport(
            trail_id=trail.id,
            concepts_imported=len(nodes),
            edges_imported=len(edges),
            sources_available=len(source_by_import_id),
            sources_missing=len(missing_source_refs),
            hydration_required=bool(source_by_import_id or missing_source_refs),
            warnings=warnings,
        ),
    )


async def _require_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")


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


async def _source_linked_to_trail(
    session: AsyncSession,
    *,
    source_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> bool:
    linked_source_id = await session.scalar(
        select(ConceptSourceLink.source_id)
        .join(ConceptNode, ConceptNode.id == ConceptSourceLink.concept_id)
        .where(
            ConceptSourceLink.source_id == source_id,
            ConceptNode.trail_id == trail_id,
        )
        .limit(1)
    )
    return linked_source_id is not None


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _slug_for_node(node_id: str) -> str:
    slug = node_id.strip()
    if not slug:
        raise TrailPackImportError("Node id must not be blank")
    return slug


def _safe_public_source(origin: str, access: str, include_on_public_export: bool) -> bool:
    return origin == "research_agent" and access == "public" and include_on_public_export is True


def _is_graph_mastery_path(path: str) -> bool:
    return path.startswith("pack.graph.nodes[")


def _trace_has_data(trace: ImportResearchTrace) -> bool:
    return any(
        (
            trace.topic,
            trace.generated_by,
            trace.queries,
            trace.selected_public_sources,
            trace.selected_sources,
            trace.excluded_sources,
        )
    )
