"""Notes service.

All business logic for the learner Notes feature lives here; the routes in
backend.app.api.notes stay thin. Notes are workspace + trail scoped (and
optionally concept scoped). Ownership is enforced on every operation so a note
can never be read, mutated, or deleted across workspace/trail boundaries.

Notes are PRIVATE workspace content and are intentionally excluded from public
Trail Pack exports.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptNode
from backend.app.models.note import Note
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.note import NoteCreateRequest, NoteUpdateRequest


async def _validate_trail_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> None:
    """Verify the workspace -> trail hierarchy. Raises LookupError on mismatch."""
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")
    trail = await session.scalar(
        select(Trail.id).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")


async def _validate_concept_in_trail(
    session: AsyncSession,
    *,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> None:
    """Verify the concept belongs to the trail. Raises LookupError on mismatch."""
    concept = await session.scalar(
        select(ConceptNode.id).where(ConceptNode.id == concept_id, ConceptNode.trail_id == trail_id)
    )
    if concept is None:
        raise LookupError(f"Concept {concept_id} not found in this trail")


async def list_notes(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None = None,
) -> list[Note]:
    """List notes for a trail, newest first, optionally filtered by concept."""
    await _validate_trail_scope(session, workspace_id=workspace_id, trail_id=trail_id)
    stmt = (
        select(Note)
        .where(Note.workspace_id == workspace_id, Note.trail_id == trail_id)
        .order_by(Note.created_at.desc(), Note.id.desc())
    )
    if concept_id is not None:
        stmt = stmt.where(Note.concept_id == concept_id)
    return list(await session.scalars(stmt))


async def create_note(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    payload: NoteCreateRequest,
) -> Note:
    """Create a note in a trail, optionally pinned to a concept in that trail."""
    await _validate_trail_scope(session, workspace_id=workspace_id, trail_id=trail_id)
    if payload.concept_id is not None:
        await _validate_concept_in_trail(session, trail_id=trail_id, concept_id=payload.concept_id)

    note = Note(
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=payload.concept_id,
        title=payload.title,
        body=payload.body,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def _get_owned_note(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    note_id: uuid.UUID,
) -> Note:
    note = await session.scalar(
        select(Note).where(
            Note.id == note_id,
            Note.workspace_id == workspace_id,
            Note.trail_id == trail_id,
        )
    )
    if note is None:
        raise LookupError(f"Note {note_id} not found")
    return note


async def update_note(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: NoteUpdateRequest,
) -> Note:
    """Patch a note's title and/or body.

    Only fields the client explicitly sent are applied, so a client can clear
    the title (``title: null``) without touching the body, or update the body
    without touching the title. A request that sets no fields raises ValueError.
    """
    fields_set = payload.model_fields_set
    if not fields_set & {"title", "body"}:
        raise ValueError("At least one of 'title' or 'body' must be provided")

    note = await _get_owned_note(
        session, workspace_id=workspace_id, trail_id=trail_id, note_id=note_id
    )
    if "title" in fields_set:
        note.title = payload.title
    if "body" in fields_set:
        # body is min_length=1 when present, so this is always non-empty here.
        note.body = payload.body  # type: ignore[assignment]

    await session.commit()
    await session.refresh(note)
    return note


async def delete_note(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    note_id: uuid.UUID,
) -> None:
    """Delete a note scoped to the workspace + trail."""
    note = await _get_owned_note(
        session, workspace_id=workspace_id, trail_id=trail_id, note_id=note_id
    )
    await session.delete(note)
    await session.commit()
