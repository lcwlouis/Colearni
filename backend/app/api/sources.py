import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.source import (
    ConceptSourceLinkCreate,
    ConceptSourceLinkRead,
    ConceptSourceLinksResponse,
    SourceUploadResponse,
)
from backend.app.services.concept_source_links import (
    link_source_to_concept,
    list_source_links,
)
from backend.app.services.source_ingestion import (
    MAX_UPLOAD_BYTES,
    SourceUploadError,
    get_private_source,
    upload_private_source,
)
from backend.app.settings import settings

router = APIRouter(prefix="/api/workspaces/{workspace_id}/sources")


@router.post(
    "/upload",
    response_model=SourceUploadResponse,
    status_code=201,
    responses={
        400: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        413: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)
async def upload_source_route(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    trail_id: uuid.UUID | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> SourceUploadResponse | JSONResponse:
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        return await upload_private_source(
            session,
            workspace_id=workspace_id,
            filename=file.filename or "upload",
            content=content,
            storage_root=settings.source_storage_root,
            title=title,
            content_type=file.content_type,
            trail_id=trail_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    except SourceUploadError as exc:
        code = "storage_error" if exc.status_code >= 500 else "invalid_input"
        return _error(exc.status_code, code, str(exc))


@router.get(
    "/{source_id}",
    response_model=SourceUploadResponse,
    responses={404: {"model": ErrorEnvelope}},
)
async def get_source_route(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SourceUploadResponse | JSONResponse:
    try:
        return await get_private_source(session, workspace_id=workspace_id, source_id=source_id)
    except LookupError as exc:
        return _not_found(str(exc))


@router.post(
    "/{source_id}/links",
    response_model=ConceptSourceLinkRead,
    status_code=201,
    responses={
        400: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
    },
)
async def link_source_to_concept_route(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    body: ConceptSourceLinkCreate,
    session: AsyncSession = Depends(get_session),
) -> ConceptSourceLinkRead | JSONResponse:
    try:
        link = await link_source_to_concept(
            session,
            workspace_id=workspace_id,
            source_id=source_id,
            concept_id=body.concept_id,
            relation=body.relation,
        )
        return ConceptSourceLinkRead.model_validate(link)
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except ValueError as exc:
        await session.rollback()
        if str(exc) == "link already exists":
            return _error(409, "conflict", str(exc))
        return _error(400, "invalid_input", str(exc))


@router.get(
    "/{source_id}/links",
    response_model=ConceptSourceLinksResponse,
    responses={404: {"model": ErrorEnvelope}},
)
async def list_source_links_route(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ConceptSourceLinksResponse | JSONResponse:
    try:
        links = await list_source_links(session, workspace_id=workspace_id, source_id=source_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return ConceptSourceLinksResponse(
        links=[ConceptSourceLinkRead.model_validate(link) for link in links]
    )


def _not_found(message: str) -> JSONResponse:
    return _error(404, "not_found", message)


def _error(status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=details or {})
        ).model_dump(),
    )
