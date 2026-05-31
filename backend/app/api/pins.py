"""Pin (Saved/Pinned) routes.

Thin routes; all logic lives in backend.app.services.pins. Pins are workspace +
trail scoped and idempotent.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.pin import PinItemType, PinListResponse, PinRequest
from backend.app.services.pins import list_pins, pin_item, unpin_item

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/pins")


@router.post("", responses={404: {"model": ErrorEnvelope}})
async def pin_item_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    body: PinRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await pin_item(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            item_type=body.item_type,
            item_id=uuid.UUID(body.item_id),
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    return JSONResponse(status_code=200, content={"status": "pinned"})


@router.delete("", responses={404: {"model": ErrorEnvelope}})
async def unpin_item_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    item_type: PinItemType = Query(...),
    item_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await unpin_item(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            item_type=item_type,
            item_id=uuid.UUID(item_id),
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    return JSONResponse(status_code=200, content={"status": "unpinned"})


@router.get("", response_model=PinListResponse, responses={404: {"model": ErrorEnvelope}})
async def list_pins_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> PinListResponse | JSONResponse:
    try:
        return await list_pins(session, workspace_id=workspace_id, trail_id=trail_id)
    except LookupError as exc:
        return _not_found(str(exc))


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )
