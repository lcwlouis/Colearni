"""Chat route definitions (workspace-scoped)."""

from __future__ import annotations

import logging
import time
from collections import Counter

from adapters.db.chat import ChatNotFoundError, resolve_session_by_public_id
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import (
    AssistantResponseEnvelope,
    ChatMessagesResponse,
    ChatRespondRequest,
    ChatSessionListResponse,
    ChatSessionSummary,
)
from core.settings import Settings

log = logging.getLogger("apps.api.routes.chat")
KEEPALIVE_INTERVAL = 15  # seconds – SSE comment to prevent proxy/browser timeouts
from domain.chat.respond import generate_chat_response
from domain.chat.sessions import (
    ChatSessionNotFoundError,
    create_session,
    delete_session,
    get_messages,
    list_sessions,
    rename_session,
)
from domain.chat.stream import generate_chat_response_stream
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/chat", tags=["chat"])


class ChatSessionCreateRequest(BaseModel):
    title: str | None = None
    concept_id: int | None = Field(default=None, gt=0)


class ChatSessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ChatRespondAPIRequest(BaseModel):
    """Client-facing respond request (no workspace_id / user_id)."""

    query: str = Field(min_length=1)
    session_id: str | None = Field(default=None, description="Session UUID public_id")
    concept_id: int | None = Field(default=None, gt=0)
    suggested_concept_id: int | None = Field(default=None, gt=0)
    concept_switch_decision: str | None = None
    top_k: int = Field(default=5, ge=1)
    grounding_mode: str | None = None
    tutor_protocol: bool = False


@router.post("/sessions", response_model=ChatSessionSummary, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ChatSessionSummary:
    return ChatSessionSummary.model_validate(
        create_session(
            db,
            workspace_id=ws.workspace_id,
            user_id=ws.user.id,
            title=payload.title,
            concept_id=payload.concept_id,
        )
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
def get_chat_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ChatSessionListResponse:
    return ChatSessionListResponse.model_validate(
        list_sessions(
            db,
            workspace_id=ws.workspace_id,
            user_id=ws.user.id,
            limit=limit,
        )
    )


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesResponse)
def get_chat_session_messages(
    session_id: str,
    limit: int = Query(default=300, ge=1, le=1000),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ChatMessagesResponse:
    try:
        internal_id = resolve_session_by_public_id(
            db, public_id=session_id, workspace_id=ws.workspace_id, user_id=ws.user.id,
        )
        return ChatMessagesResponse.model_validate(
            get_messages(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                session_id=internal_id,
                limit=limit,
            )
        )
    except (ChatSessionNotFoundError, ChatNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session_route(
    session_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        internal_id = resolve_session_by_public_id(
            db, public_id=session_id, workspace_id=ws.workspace_id, user_id=ws.user.id,
        )
        delete_session(
            db,
            workspace_id=ws.workspace_id,
            user_id=ws.user.id,
            session_id=internal_id,
        )
    except (ChatSessionNotFoundError, ChatNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/sessions/{session_id}", response_model=ChatSessionSummary)
def rename_chat_session_route(
    session_id: str,
    payload: ChatSessionRenameRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ChatSessionSummary:
    try:
        internal_id = resolve_session_by_public_id(
            db, public_id=session_id, workspace_id=ws.workspace_id, user_id=ws.user.id,
        )
        return ChatSessionSummary.model_validate(
            rename_session(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                session_id=internal_id,
                title=payload.title,
            )
        )
    except (ChatSessionNotFoundError, ChatNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/respond", response_model=AssistantResponseEnvelope)
def respond_chat(
    payload: ChatRespondAPIRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> AssistantResponseEnvelope:
    """Generate one verified assistant response envelope."""
    settings_state = getattr(request.app.state, "settings", None)
    settings = settings_state if isinstance(settings_state, Settings) else None

    # Resolve UUID session_id → internal int if provided
    resolved_session_id: int | None = None
    if payload.session_id:
        try:
            resolved_session_id = resolve_session_by_public_id(
                db, public_id=payload.session_id,
                workspace_id=ws.workspace_id, user_id=ws.user.id,
            )
        except ChatNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    internal = ChatRespondRequest(
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        query=payload.query,
        session_id=resolved_session_id,
        concept_id=payload.concept_id,
        suggested_concept_id=payload.suggested_concept_id,
        concept_switch_decision=payload.concept_switch_decision,
        top_k=payload.top_k,
        grounding_mode=payload.grounding_mode,
        tutor_protocol=payload.tutor_protocol,
    )
    try:
        return generate_chat_response(
            session=db,
            request=internal,
            settings=settings,
        )
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/respond/stream")
def respond_chat_stream(
    payload: ChatRespondAPIRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Stream chat response events via SSE."""
    settings_state = getattr(request.app.state, "settings", None)
    settings = settings_state if isinstance(settings_state, Settings) else None

    # Check feature flag
    active_settings = settings or Settings()
    if not active_settings.chat_streaming_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Streaming is not enabled",
        )

    resolved_session_id: int | None = None
    if payload.session_id:
        try:
            resolved_session_id = resolve_session_by_public_id(
                db,
                public_id=payload.session_id,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
            )
        except ChatNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    internal = ChatRespondRequest(
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        query=payload.query,
        session_id=resolved_session_id,
        concept_id=payload.concept_id,
        suggested_concept_id=payload.suggested_concept_id,
        concept_switch_decision=payload.concept_switch_decision,
        top_k=payload.top_k,
        grounding_mode=payload.grounding_mode,
        tutor_protocol=payload.tutor_protocol,
    )

    def _sse_generator():
        event_count = 0
        event_types: Counter[str] = Counter()
        log.info("stream start ws=%s session=%s", ws.workspace_id, resolved_session_id)
        last_event_time = time.monotonic()
        for event in generate_chat_response_stream(
            session=db,
            request=internal,
            settings=settings,
        ):
            now = time.monotonic()
            if now - last_event_time > KEEPALIVE_INTERVAL:
                yield ": keepalive\n\n"
            event_count += 1
            event_types[event.event] += 1
            data = event.model_dump_json()
            log.debug(
                "stream event #%d type=%s ws=%s",
                event_count, event.event, ws.workspace_id,
            )
            yield f"event: {event.event}\ndata: {data}\n\n"
            last_event_time = time.monotonic()
        log.info(
            "stream complete ws=%s session=%s events=%d breakdown=%s",
            ws.workspace_id,
            resolved_session_id,
            event_count,
            dict(event_types),
        )

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Regeneration ──────────────────────────────────────────────────────


class RegenerateRequest(BaseModel):
    """Request body for the regeneration endpoint (currently empty, extensible)."""


@router.post("/sessions/{session_id}/messages/{msg_id}/regenerate")
def regenerate_message(
    session_id: str,
    msg_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
    request: Request = None,  # type: ignore[assignment]
) -> StreamingResponse:
    """Supersede an assistant message and stream a regenerated response.

    Marks the target assistant message as ``superseded``, retrieves the
    original user query, and triggers a new streaming response.
    """
    from domain.chat.session_memory import (
        RegenerationError,
        supersede_and_get_user_query,
    )

    # Resolve session public_id → internal id
    try:
        resolved_session_id = resolve_session_by_public_id(
            db,
            public_id=session_id,
            workspace_id=ws.workspace_id,
            user_id=ws.user.id,
        )
    except ChatNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    # Supersede old message and get user query
    try:
        user_query = supersede_and_get_user_query(
            db, message_id=msg_id, session_id=resolved_session_id,
        )
        db.commit()
    except RegenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc

    # Build internal request for re-generation
    settings_state = getattr(request.app.state, "settings", None) if request else None
    settings = settings_state if isinstance(settings_state, Settings) else None

    internal = ChatRespondRequest(
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        query=user_query,
        session_id=resolved_session_id,
    )

    def _sse_generator():
        event_count = 0
        last_event_time = time.monotonic()
        for event in generate_chat_response_stream(
            session=db,
            request=internal,
            settings=settings,
        ):
            now = time.monotonic()
            if now - last_event_time > KEEPALIVE_INTERVAL:
                yield ": keepalive\n\n"
            event_count += 1
            data = event.model_dump_json()
            yield f"event: {event.event}\ndata: {data}\n\n"
            last_event_time = time.monotonic()

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
