"""Tutor chat routes.

Thin routes; all logic lives in backend.app.services.tutor and
backend.app.services.conversations.

Factory function ``get_tutor_agent`` is defined here so tests can override it
via ``app.dependency_overrides`` without touching service internals.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db import AsyncSessionLocal, get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.tutor import ChatRequest, ConversationHistoryResponse, ConversationMessage
from backend.app.services.conversations import get_conversation_history, validate_concept_scope
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


@router.get("/{concept_id}/conversation", response_model=ConversationHistoryResponse)
async def get_conversation_endpoint(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
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
