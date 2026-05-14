import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.concept import ConceptDetailResponse
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.services.graph_view import get_concept_detail

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/concepts")


@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept_detail_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ConceptDetailResponse | JSONResponse:
    try:
        detail = await get_concept_detail(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    return ConceptDetailResponse.model_validate(detail)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )
