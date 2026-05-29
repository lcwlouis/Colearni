import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptNode
from backend.app.models.source import ConceptSourceLink, SourceChunk, SourceRecord, SourceRevision
from backend.app.models.trail import Trail

ALLOWED_RELATIONS = {"primary", "reference", "supplementary", "prerequisite_source"}


async def link_source_to_concept(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    concept_id: uuid.UUID,
    relation: str,
    commit: bool = True,
    skip_existing: bool = False,
) -> ConceptSourceLink:
    """
    Create a ConceptSourceLink between an uploaded source and a concept.

    Raises LookupError if source or concept/trail not found.
    Raises ValueError for bad relation or duplicate link.
    """
    if relation not in ALLOWED_RELATIONS:
        raise ValueError("invalid relation")

    await _require_source(session, workspace_id=workspace_id, source_id=source_id)
    await _require_concept(session, workspace_id=workspace_id, concept_id=concept_id)

    existing = await session.scalar(
        select(ConceptSourceLink).where(
            ConceptSourceLink.source_id == source_id,
            ConceptSourceLink.concept_id == concept_id,
            ConceptSourceLink.relation == relation,
        )
    )
    if existing is not None:
        if skip_existing:
            return existing
        raise ValueError("link already exists")

    link = ConceptSourceLink(source_id=source_id, concept_id=concept_id, relation=relation)
    session.add(link)
    if not commit:
        return link
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("link already exists") from exc
    await session.refresh(link)
    return link


async def auto_link_source_to_trail(
    session: AsyncSession,
    source_revision_id: uuid.UUID,
    trail_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
    revision = await session.get(SourceRevision, source_revision_id)
    if revision is None or revision.workspace_id != workspace_id:
        raise LookupError(f"Source revision {source_revision_id} not found")

    chunk_texts = list(
        await session.scalars(
            select(SourceChunk.text).where(
                SourceChunk.source_revision_id == source_revision_id,
                SourceChunk.workspace_id == workspace_id,
            )
        )
    )
    if not chunk_texts:
        return

    concepts = list(
        await session.scalars(
            select(ConceptNode)
            .join(Trail, Trail.id == ConceptNode.trail_id)
            .where(
                ConceptNode.trail_id == trail_id,
                Trail.workspace_id == workspace_id,
            )
            .order_by(ConceptNode.title, ConceptNode.id)
        )
    )
    full_text = "\n".join(chunk_texts).lower()
    for concept in concepts:
        if concept.title.lower() in full_text:
            await link_source_to_concept(
                session,
                workspace_id=workspace_id,
                source_id=revision.source_id,
                concept_id=concept.id,
                relation="supplementary",
                commit=False,
                skip_existing=True,
            )


async def list_source_links(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
) -> list[ConceptSourceLink]:
    """Return all ConceptSourceLink rows for this source in this workspace."""
    await _require_source(session, workspace_id=workspace_id, source_id=source_id)
    return list(
        await session.scalars(
            select(ConceptSourceLink)
            .join(ConceptNode, ConceptNode.id == ConceptSourceLink.concept_id)
            .join(Trail, Trail.id == ConceptNode.trail_id)
            .where(ConceptSourceLink.source_id == source_id)
            .where(Trail.workspace_id == workspace_id)
            .order_by(ConceptSourceLink.relation, ConceptSourceLink.id)
        )
    )


async def list_concept_sources(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> list[tuple[ConceptSourceLink, SourceRecord, str | None]]:
    """Return all (link, source) pairs for a concept, workspace-scoped."""
    await _require_concept(session, workspace_id=workspace_id, concept_id=concept_id)
    latest_revisions = (
        select(
            SourceRevision.source_id.label("source_id"),
            func.max(SourceRevision.revision_number).label("revision_number"),
        )
        .where(SourceRevision.workspace_id == workspace_id)
        .group_by(SourceRevision.source_id)
        .subquery()
    )
    rows = await session.execute(
        select(ConceptSourceLink, SourceRecord, SourceRevision.status)
        .join(SourceRecord, ConceptSourceLink.source_id == SourceRecord.id)
        .outerjoin(
            latest_revisions,
            latest_revisions.c.source_id == SourceRecord.id,
        )
        .outerjoin(
            SourceRevision,
            (SourceRevision.source_id == latest_revisions.c.source_id)
            & (SourceRevision.revision_number == latest_revisions.c.revision_number)
            & (SourceRevision.workspace_id == workspace_id),
        )
        .where(
            ConceptSourceLink.concept_id == concept_id,
            SourceRecord.workspace_id == workspace_id,
        )
        .order_by(SourceRecord.title, ConceptSourceLink.relation, ConceptSourceLink.id)
    )
    return [(link, source, status) for link, source, status in rows.all()]


async def _require_source(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
) -> SourceRecord:
    source = await session.scalar(
        select(SourceRecord).where(
            SourceRecord.id == source_id,
            SourceRecord.workspace_id == workspace_id,
        )
    )
    if source is None:
        raise LookupError(f"Source {source_id} not found")
    return source


async def _require_concept(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> ConceptNode:
    concept = await session.scalar(
        select(ConceptNode)
        .join(Trail, Trail.id == ConceptNode.trail_id)
        .where(ConceptNode.id == concept_id, Trail.workspace_id == workspace_id)
    )
    if concept is None:
        raise LookupError(f"Concept {concept_id} not found")
    return concept
