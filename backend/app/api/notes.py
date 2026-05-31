"""Note routes.

Thin routes; all logic lives in backend.app.services.notes. Notes are workspace
+ trail scoped (and optionally concept scoped).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.note import (
    NoteCreateRequest,
    NoteListResponse,
    NoteRead,
    NoteUpdateRequest,
)
from backend.app.services.notes import (
    create_note,
    delete_note,
    list_notes,
    update_note,
)

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/notes")


@router.get("", response_model=NoteListResponse, responses={404: {"model": ErrorEnvelope}})
async def list_notes_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> NoteListResponse | JSONResponse:
    try:
        notes = await list_notes(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    return NoteListResponse(notes=[NoteRead.model_validate(note) for note in notes])


@router.post("", response_model=NoteRead, responses={404: {"model": ErrorEnvelope}})
async def create_note_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    body: NoteCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> NoteRead | JSONResponse:
    try:
        note = await create_note(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            payload=body,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    return NoteRead.model_validate(note)


@router.patch(
    "/{note_id}",
    response_model=NoteRead,
    responses={400: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def update_note_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    note_id: uuid.UUID,
    body: NoteUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> NoteRead | JSONResponse:
    try:
        note = await update_note(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            note_id=note_id,
            payload=body,
        )
    except ValueError as exc:
        await session.rollback()
        return _bad_request(str(exc))
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    return NoteRead.model_validate(note)


@router.delete("/{note_id}", responses={404: {"model": ErrorEnvelope}})
async def delete_note_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    note_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_note(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            note_id=note_id,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    return JSONResponse(status_code=200, content={"status": "deleted"})


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=ErrorEnvelope(
            error=ErrorBody(code="invalid_request", message=message)
        ).model_dump(),
    )
