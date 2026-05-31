"""Artifact routes.

Thin routes; all logic lives in backend.app.services.artifacts and
backend.app.services.artifact_builder.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.llm_client import LLMClient
from backend.app.db import AsyncSessionLocal, get_session
from backend.app.schemas.artifact import (
    ArtifactBuildRequest,
    ArtifactListResponse,
    ArtifactRead,
)
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.services.artifact_builder import (
    ArtifactBuilder,
    ArtifactGenerationError,
    LLMArtifactBuilder,
    build_artifact,
    stream_artifact,
)
from backend.app.services.artifacts import get_artifact, list_artifacts
from backend.app.settings import settings

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/artifacts")


def get_artifact_builder() -> ArtifactBuilder:
    return LLMArtifactBuilder(client=LLMClient.from_settings(settings))


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # Sessionmaker handed to detached artifact generation so the background task
    # owns a session that outlives the request. Tests override this to bind the
    # background task to their in-memory engine.
    return AsyncSessionLocal


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ArtifactListResponse:
    artifacts = await list_artifacts(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )
    return ArtifactListResponse(
        artifacts=[ArtifactRead.model_validate(artifact) for artifact in artifacts]
    )


@router.post(
    "/build",
    response_model=ArtifactRead,
    responses={404: {"model": ErrorEnvelope}, 502: {"model": ErrorEnvelope}},
)
async def build_artifact_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    body: ArtifactBuildRequest,
    session: AsyncSession = Depends(get_session),
    builder: ArtifactBuilder = Depends(get_artifact_builder),
) -> ArtifactRead | JSONResponse:
    try:
        artifact = await build_artifact(
            session,
            builder,
            workspace_id=workspace_id,
            trail_id=trail_id,
            kind=body.kind,
            concept_id=body.concept_id,
            force_new=body.force_new,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except ArtifactGenerationError as exc:
        await session.rollback()
        return _llm_error(str(exc))
    return ArtifactRead.model_validate(artifact)


@router.post("/build/stream", response_model=None)
async def stream_build_artifact_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    body: ArtifactBuildRequest,
    session: AsyncSession = Depends(get_session),
    builder: ArtifactBuilder = Depends(get_artifact_builder),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse | JSONResponse:
    # The streaming endpoint is a dedupe-only LIVE PREVIEW of detached
    # generation; forced regeneration goes through the non-stream POST /build so
    # the single-flight manager never has to reconcile force-vs-dedupe races.
    if body.force_new:
        return JSONResponse(
            status_code=400,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="invalid_request",
                    message="force_new is not supported on /build/stream; use POST /build.",
                )
            ).model_dump(),
        )
    return StreamingResponse(
        stream_artifact(
            session,
            builder,
            workspace_id=workspace_id,
            trail_id=trail_id,
            kind=body.kind,
            concept_id=body.concept_id,
            session_factory=session_factory,
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/{artifact_id}",
    response_model=ArtifactRead,
    responses={404: {"model": ErrorEnvelope}},
)
async def get_artifact_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ArtifactRead | JSONResponse:
    try:
        artifact = await get_artifact(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            artifact_id=artifact_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    return ArtifactRead.model_validate(artifact)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )


def _llm_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content=ErrorEnvelope(error=ErrorBody(code="llm_error", message=message)).model_dump(),
    )
