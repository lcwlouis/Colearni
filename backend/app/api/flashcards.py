"""Flashcard routes (dedicated subsystem, Phase 15c).

Thin routes; all logic lives in backend.app.services.flashcards (generation +
review), flashcard_scheduler (Leitner) and flashcard_export (CSV/JSON export).
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.embedding_client import EmbeddingClient
from backend.app.agents.llm_client import LLMClient
from backend.app.db import AsyncSessionLocal, get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.flashcard import (
    FlashcardDeckRead,
    FlashcardGenerateRequest,
    FlashcardGenerateResponse,
    FlashcardRead,
    FlashcardReviewRequest,
)
from backend.app.services.flashcard_export import export_deck_csv, export_deck_json
from backend.app.services.flashcards import (
    Embedder,
    FlashcardGenerationError,
    FlashcardGenerator,
    LLMFlashcardGenerator,
    generate_deck,
    get_deck,
    review_card,
    stream_generate_deck,
)
from backend.app.settings import settings

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/flashcards"
)


def get_flashcard_generator() -> FlashcardGenerator:
    return LLMFlashcardGenerator(client=LLMClient.from_settings(settings))


def get_embedder() -> Embedder:
    return EmbeddingClient.from_settings(settings)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # Sessionmaker handed to detached flashcard generation so the background
    # task owns a session that outlives the request.
    return AsyncSessionLocal


@router.post(
    "/generate",
    response_model=FlashcardGenerateResponse,
    responses={404: {"model": ErrorEnvelope}, 502: {"model": ErrorEnvelope}},
)
async def generate_flashcards_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: FlashcardGenerateRequest = Body(default_factory=FlashcardGenerateRequest),
    session: AsyncSession = Depends(get_session),
    generator: FlashcardGenerator = Depends(get_flashcard_generator),
    embedder: Embedder = Depends(get_embedder),
) -> FlashcardGenerateResponse | JSONResponse:
    try:
        deck, exhausted, reason = await generate_deck(
            session,
            generator,
            embedder,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            extend=body.extend,
            force=body.force,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except FlashcardGenerationError as exc:
        await session.rollback()
        return _llm_error(str(exc))
    return FlashcardGenerateResponse(deck=deck, exhausted=exhausted, reason=reason)


@router.post(
    "/generate/stream",
    response_model=None,
    responses={404: {"model": ErrorEnvelope}, 502: {"model": ErrorEnvelope}},
)
async def stream_generate_flashcards_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: FlashcardGenerateRequest = Body(default_factory=FlashcardGenerateRequest),
    session: AsyncSession = Depends(get_session),
    generator: FlashcardGenerator = Depends(get_flashcard_generator),
    embedder: Embedder = Depends(get_embedder),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse:
    return StreamingResponse(
        stream_generate_deck(
            session,
            generator,
            embedder,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            extend=body.extend,
            force=body.force,
            session_factory=session_factory,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=FlashcardDeckRead, responses={404: {"model": ErrorEnvelope}})
async def get_flashcards_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FlashcardDeckRead | JSONResponse:
    try:
        return await get_deck(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))


@router.post(
    "/{card_id}/review",
    response_model=FlashcardRead,
    responses={404: {"model": ErrorEnvelope}},
)
async def review_flashcard_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    card_id: uuid.UUID,
    body: FlashcardReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> FlashcardRead | JSONResponse:
    try:
        return await review_card(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            card_id=card_id,
            recalled=body.recalled,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))


@router.get("/export", response_model=None, responses={404: {"model": ErrorEnvelope}})
async def export_flashcards_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    format: str = Query(default="csv"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if format not in ("csv", "json"):
        return JSONResponse(
            status_code=400,
            content=ErrorEnvelope(
                error=ErrorBody(code="invalid_request", message="format must be csv or json")
            ).model_dump(),
        )
    try:
        deck = await get_deck(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))

    filename = f"deck-{deck.id}"
    if format == "csv":
        return PlainTextResponse(
            export_deck_csv(deck),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    return Response(
        content=json.dumps(export_deck_json(deck), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


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
