import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
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
    return LLMGraphGenerator(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        api_base=settings.llm_api_base,
    )


@router.post("/generate", response_model=TrailGenerateResponse, status_code=201)
async def generate_trail(
    workspace_id: uuid.UUID,
    body: TrailGenerateRequest,
    session: AsyncSession = Depends(get_session),
    generator: GraphGenerator = Depends(get_graph_generator),
) -> TrailGenerateResponse:
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "llm_error", "message": str(exc)},
        ) from exc

    trail_read = TrailRead.model_validate(trail)
    trail_read.node_count = len(nodes)
    trail_read.edge_count = len(edges)

    return TrailGenerateResponse(
        trail=trail_read,
        graph=TrailGraphRead(nodes=nodes, edges=edges),
    )
