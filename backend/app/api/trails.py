import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.llm_client import LLMClient
from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.trail import (
    TrailGenerateRequest,
    TrailGenerateResponse,
    TrailGraphRead,
    TrailRead,
)
from backend.app.services.trail_generation import (
    GenerationError,
    GraphGenerator,
    LLMGraphGenerator,
    generate_and_store_trail,
)
from backend.app.settings import settings

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails")


def get_graph_generator() -> GraphGenerator:
    return LLMGraphGenerator(client=LLMClient.from_settings(settings))


@router.post("/generate", response_model=TrailGenerateResponse, status_code=201)
async def generate_trail(
    workspace_id: uuid.UUID,
    body: TrailGenerateRequest,
    session: AsyncSession = Depends(get_session),
    generator: GraphGenerator = Depends(get_graph_generator),
) -> TrailGenerateResponse | JSONResponse:
    try:
        trail, nodes, edges = await generate_and_store_trail(
            session=session,
            generator=generator,
            workspace_id=workspace_id,
            topic=body.topic,
            goal=body.goal,
            target_depth=body.target_depth,
        )
    except LookupError as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorEnvelope(
                error=ErrorBody(code="not_found", message=str(exc))
            ).model_dump(),
        )
    except GenerationError as exc:
        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                error=ErrorBody(code="llm_error", message=str(exc))
            ).model_dump(),
        )

    trail_read = TrailRead.model_validate(trail)
    trail_read.node_count = len(nodes)
    trail_read.edge_count = len(edges)

    return TrailGenerateResponse(
        trail=trail_read,
        graph=TrailGraphRead(nodes=nodes, edges=edges),
    )
