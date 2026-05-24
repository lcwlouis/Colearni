import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.trail_pack_import import (
    HydrationRequest,
    HydrationResponse,
    ResearchTraceResponse,
    TrailPackImportResponse,
)
from backend.app.services.trail_pack_import import (
    TrailPackImportError,
    get_research_trace,
    hydrate_trail,
    import_trail_pack,
)

router = APIRouter(prefix="/api/workspaces/{workspace_id}")
ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
}


@router.post(
    "/trail-packs/import",
    response_model=TrailPackImportResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
)
async def import_trail_pack_route(
    workspace_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TrailPackImportResponse | JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return _invalid_input("Malformed JSON Trail Pack payload")
    if not isinstance(payload, dict):
        return _invalid_input("Trail Pack payload must be a JSON object")

    try:
        return await import_trail_pack(session, workspace_id=workspace_id, payload=payload)
    except LookupError as exc:
        return _not_found(str(exc))
    except TrailPackImportError as exc:
        return _error(exc.status_code, "invalid_input", str(exc))


@router.get(
    "/trails/{trail_id}/research",
    response_model=ResearchTraceResponse,
    responses={400: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_research_trace_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ResearchTraceResponse | JSONResponse:
    try:
        return await get_research_trace(session, workspace_id=workspace_id, trail_id=trail_id)
    except LookupError as exc:
        return _not_found(str(exc))


@router.post(
    "/trails/{trail_id}/hydrate",
    response_model=HydrationResponse,
    responses={404: {"model": ErrorEnvelope}},
)
async def hydrate_trail_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    body: HydrationRequest,
    session: AsyncSession = Depends(get_session),
) -> HydrationResponse | JSONResponse:
    try:
        return await hydrate_trail(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=body.concept_id,
            source_ids=body.source_ids,
            use_model_knowledge=body.use_model_knowledge,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    except TrailPackImportError as exc:
        return _error(exc.status_code, "invalid_input", str(exc))


def _not_found(message: str) -> JSONResponse:
    return _error(404, "not_found", message)


def _invalid_input(message: str) -> JSONResponse:
    return _error(400, "invalid_input", message)


def _error(status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=details or {})
        ).model_dump(),
    )
