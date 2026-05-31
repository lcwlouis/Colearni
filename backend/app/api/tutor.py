"""Tutor chat routes.

Thin routes; all logic lives in backend.app.services.tutor and
backend.app.services.conversations.

Factory function ``get_tutor_agent`` is defined here so tests can override it
via ``app.dependency_overrides`` without touching service internals.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db import AsyncSessionLocal, get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.tutor import (
    ChatRequest,
    ConversationHistoryResponse,
    ConversationMessage,
    ConversationThreadListResponse,
    ConversationThreadSummary,
    ConversationThreadUpdateRequest,
)
from backend.app.services.conversations import (
    create_conversation_thread,
    delete_conversation_thread,
    get_conversation_history,
    list_conversation_threads,
    update_conversation_thread_title,
    validate_concept_scope,
)
from backend.app.services.tutor import (
    LLMTutorAgent,
    TutorAgent,
    stream_chat_response,
)
from backend.app.settings import settings

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/concepts")


# ---------------------------------------------------------------------------
# Dependency factories — override in tests via app.dependency_overrides
# ---------------------------------------------------------------------------


def get_tutor_agent() -> TutorAgent:
    """Return the LLM-backed tutor agent."""
    from backend.app.agents.llm_client import LLMClient

    return LLMTutorAgent(
        client=LLMClient.from_settings(settings),
        max_tokens=settings.llm_tutor_max_tokens,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # Sessionmaker handed to detached post-turn tutor follow-ups so the background
    # task owns a session that outlives the request. Tests override this to bind
    # the background task to their in-memory engine.
    return AsyncSessionLocal


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/{concept_id}/chat", response_model=None)
async def chat_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    agent: TutorAgent = Depends(get_tutor_agent),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse | JSONResponse:
    """Stream a Socratic tutor response via Server-Sent Events.

    Pre-validates workspace → trail → concept scope and returns 404 before
    starting the stream.  SSE error events are used for in-stream failures.
    """
    try:
        await validate_concept_scope(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))

    async def generate():
        async for event in stream_chat_response(
            session,
            agent,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            message=body.message,
            conversation_id=body.conversation_id,
            regenerate=body.regenerate,
            replace_latest_user=body.replace_latest_user,
            session_factory=session_factory,
        ):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{concept_id}/conversations", response_model=ConversationThreadSummary)
async def create_conversation_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ConversationThreadSummary | JSONResponse:
    try:
        conversation = await create_conversation_thread(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))

    return ConversationThreadSummary(
        id=conversation.id,
        title="New thread",
        preview=None,
        message_count=0,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/{concept_id}/conversations", response_model=ConversationThreadListResponse)
async def list_conversations_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> ConversationThreadListResponse | JSONResponse:
    try:
        conversations = await list_conversation_threads(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            limit=limit,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    return ConversationThreadListResponse(conversations=conversations)


@router.patch(
    "/{concept_id}/conversations/{conversation_id}", response_model=ConversationThreadSummary
)
async def update_conversation_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: ConversationThreadUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> ConversationThreadSummary | JSONResponse:
    try:
        return await update_conversation_thread_title(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            conversation_id=conversation_id,
            title=body.title,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))


@router.delete(
    "/{concept_id}/conversations/{conversation_id}",
    status_code=204,
    response_model=None,
)
async def delete_conversation_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await delete_conversation_thread(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            conversation_id=conversation_id,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    return Response(status_code=204)


@router.get("/{concept_id}/conversation", response_model=ConversationHistoryResponse)
async def get_conversation_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    conversation_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> ConversationHistoryResponse | JSONResponse:
    """Return conversation history for a concept in chronological order.

    Returns conversation_id=null and messages=[] if no conversation has started.
    """
    try:
        conv_id, turns = await get_conversation_history(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            conversation_id=conversation_id,
            limit=limit,
        )
    except LookupError as exc:
        return _not_found(str(exc))

    messages = [ConversationMessage.model_validate(t) for t in turns]
    return ConversationHistoryResponse(conversation_id=conv_id, messages=messages)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )
