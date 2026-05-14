import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.trail import MasterySummary


async def list_trails(session: AsyncSession, *, workspace_id: uuid.UUID) -> list[Trail]:
    await _require_workspace(session, workspace_id)
    node_counts = (
        select(ConceptNode.trail_id, func.count(ConceptNode.id).label("node_count"))
        .group_by(ConceptNode.trail_id)
        .subquery()
    )
    edge_counts = (
        select(ConceptEdge.trail_id, func.count(ConceptEdge.id).label("edge_count"))
        .group_by(ConceptEdge.trail_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            Trail,
            func.coalesce(node_counts.c.node_count, 0),
            func.coalesce(edge_counts.c.edge_count, 0),
        )
        .outerjoin(node_counts, node_counts.c.trail_id == Trail.id)
        .outerjoin(edge_counts, edge_counts.c.trail_id == Trail.id)
        .where(Trail.workspace_id == workspace_id)
        .order_by(Trail.created_at)
    )
    trails: list[Trail] = []
    for trail, node_count, edge_count in rows.all():
        trail.node_count = node_count
        trail.edge_count = edge_count
        trails.append(trail)
    return trails


async def get_trail_detail(
    session: AsyncSession, *, workspace_id: uuid.UUID, trail_id: uuid.UUID
) -> tuple[Trail, list[ConceptNode], list[ConceptEdge], MasterySummary]:
    trail = await _get_scoped_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    nodes = list(
        await session.scalars(
            select(ConceptNode).where(ConceptNode.trail_id == trail_id).order_by(ConceptNode.title)
        )
    )
    edges = list(
        await session.scalars(
            select(ConceptEdge).where(ConceptEdge.trail_id == trail_id).order_by(ConceptEdge.id)
        )
    )
    trail.node_count = len(nodes)
    trail.edge_count = len(edges)
    mastery_summary = MasterySummary(
        total=len(nodes),
        not_started=len(nodes),
        learning=0,
        needs_review=0,
        mastered=0,
    )
    return trail, nodes, edges, mastery_summary


async def delete_trail(
    session: AsyncSession, *, workspace_id: uuid.UUID, trail_id: uuid.UUID
) -> None:
    await _get_scoped_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    await session.execute(delete(ConceptEdge).where(ConceptEdge.trail_id == trail_id))
    await session.execute(delete(ConceptNode).where(ConceptNode.trail_id == trail_id))
    await session.execute(delete(Trail).where(Trail.id == trail_id))
    await session.commit()


async def get_concept_detail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> dict:
    await _get_scoped_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    nodes = list(
        await session.scalars(
            select(ConceptNode).where(ConceptNode.trail_id == trail_id).order_by(ConceptNode.title)
        )
    )
    node_by_id = {node.id: node for node in nodes}
    concept = node_by_id.get(concept_id)
    if concept is None:
        raise LookupError(f"Concept {concept_id} not found")

    edges = list(
        await session.scalars(select(ConceptEdge).where(ConceptEdge.trail_id == trail_id))
    )

    prerequisites: list[ConceptNode] = []
    contained_nodes: list[ConceptNode] = []
    containing_nodes: list[ConceptNode] = []
    related: list[ConceptNode] = []
    seen_related: set[uuid.UUID] = set()

    for edge in edges:
        source = node_by_id.get(edge.source_node_id)
        target = node_by_id.get(edge.target_node_id)
        if source is None or target is None:
            continue
        if edge.relation_type == "prerequisite" and edge.target_node_id == concept_id:
            prerequisites.append(source)
        elif edge.relation_type == "contains" and edge.source_node_id == concept_id:
            contained_nodes.append(target)
        elif edge.relation_type == "contains" and edge.target_node_id == concept_id:
            containing_nodes.append(source)
        elif edge.relation_type in {"application", "related"}:
            neighbor = None
            if edge.source_node_id == concept_id:
                neighbor = target
            elif edge.target_node_id == concept_id:
                neighbor = source
            if neighbor is not None and neighbor.id not in seen_related:
                seen_related.add(neighbor.id)
                related.append(neighbor)

    return {
        "concept": concept,
        "prerequisites": prerequisites,
        "contained_nodes": contained_nodes,
        "containing_nodes": containing_nodes,
        "related": related,
        "mastery": None,
        "sources": [],
    }


async def _require_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")


async def _get_scoped_trail(
    session: AsyncSession, *, workspace_id: uuid.UUID, trail_id: uuid.UUID
) -> Trail:
    trail = await session.scalar(
        select(Trail).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")
    return trail
