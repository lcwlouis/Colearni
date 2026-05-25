import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.llm_client import LLMClient
from backend.app.db import get_session
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.schemas.concept import ConceptEdgeRead, ConceptNodeRead
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.mastery import MasteryRecordRead
from backend.app.schemas.trail import (
    NextConceptResponse,
    TrailDetailResponse,
    TrailGenerateRequest,
    TrailGenerateResponse,
    TrailGraphRead,
    TrailListResponse,
    TrailRead,
)
from backend.app.schemas.trail_pack import TrailPackExportResponse
from backend.app.services.graph_view import delete_trail, get_trail_detail, list_trails
from backend.app.services.recommendation import get_next_concept_for_trail
from backend.app.services.trail_generation import (
    GenerationError,
    GraphGenerator,
    LLMGraphGenerator,
    generate_and_store_trail,
    stream_generate_trail_events,
)
from backend.app.services.trail_pack_export import export_trail_pack
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
            max_nodes=body.max_nodes,
        )
    except LookupError as exc:
        return JSONResponse(
            status_code=404,
            content=ErrorEnvelope(error=ErrorBody(code="not_found", message=str(exc))).model_dump(),
        )
    except GenerationError as exc:
        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(error=ErrorBody(code="llm_error", message=str(exc))).model_dump(),
        )

    trail_read = TrailRead.model_validate(trail)
    trail_read.node_count = len(nodes)
    trail_read.edge_count = len(edges)

    return TrailGenerateResponse(
        trail=trail_read,
        graph=_graph_read(nodes, edges),
    )


@router.post("/generate/stream", response_model=None)
async def generate_trail_stream(
    workspace_id: uuid.UUID,
    body: TrailGenerateRequest,
    session: AsyncSession = Depends(get_session),
    generator: GraphGenerator = Depends(get_graph_generator),
) -> StreamingResponse:
    return StreamingResponse(
        stream_generate_trail_events(
            session=session,
            generator=generator,
            workspace_id=workspace_id,
            topic=body.topic,
            goal=body.goal,
            target_depth=body.target_depth,
            max_nodes=body.max_nodes,
        ),
        media_type="text/event-stream",
    )


@router.get("", response_model=TrailListResponse)
async def list_trails_route(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TrailListResponse | JSONResponse:
    try:
        trails = await list_trails(session, workspace_id=workspace_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return TrailListResponse(trails=[TrailRead.model_validate(trail) for trail in trails])


@router.get("/{trail_id}", response_model=TrailDetailResponse)
async def get_trail_detail_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TrailDetailResponse | JSONResponse:
    try:
        trail, nodes, edges, mastery_summary = await get_trail_detail(
            session, workspace_id=workspace_id, trail_id=trail_id
        )
    except LookupError as exc:
        return _not_found(str(exc))
    return TrailDetailResponse(
        trail=TrailRead.model_validate(trail),
        graph=_graph_read(nodes, edges, getattr(trail, "mastery_by_concept", {})),
        mastery_summary=mastery_summary,
    )


@router.get("/{trail_id}/next", response_model=NextConceptResponse)
async def get_next_concept_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> NextConceptResponse | JSONResponse:
    try:
        recommendation = await get_next_concept_for_trail(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))

    return NextConceptResponse(
        concept_id=recommendation.concept.id if recommendation.concept else None,
        concept_title=recommendation.concept.title if recommendation.concept else None,
        reason=recommendation.reason,
        all_mastered=recommendation.all_mastered,
        mastery_status=recommendation.mastery_status,
        concept_level=recommendation.concept_level,
    )


@router.get("/{trail_id}/export", response_model=TrailPackExportResponse)
async def export_trail_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    format: str = Query(default="json"),
    session: AsyncSession = Depends(get_session),
) -> TrailPackExportResponse | JSONResponse:
    if format != "json":
        return _invalid_input(
            f"Unsupported export format '{format}'. Only 'json' is currently available."
        )
    try:
        return await export_trail_pack(session, workspace_id=workspace_id, trail_id=trail_id)
    except LookupError as exc:
        return _not_found(str(exc))


@router.delete("/{trail_id}", status_code=204, response_model=None)
async def delete_trail_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response | JSONResponse:
    try:
        await delete_trail(session, workspace_id=workspace_id, trail_id=trail_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return Response(status_code=204)


def _graph_read(
    nodes: list[ConceptNode],
    edges: list[ConceptEdge],
    mastery_by_concept: dict | None = None,
) -> TrailGraphRead:
    return TrailGraphRead(
        nodes=[ConceptNodeRead.model_validate(node) for node in nodes],
        edges=[ConceptEdgeRead.model_validate(edge) for edge in edges],
        mastery={
            concept_id: MasteryRecordRead.model_validate(state)
            for concept_id, state in (mastery_by_concept or {}).items()
        },
    )


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )


def _invalid_input(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=ErrorEnvelope(error=ErrorBody(code="invalid_input", message=message)).model_dump(),
    )
