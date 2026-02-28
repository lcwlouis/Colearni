"""Chat route definitions (workspace-scoped)."""

from __future__ import annotations

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
from domain.chat.respond import generate_chat_response
from domain.chat.sessions import (
    ChatSessionNotFoundError,
    create_session,
    delete_session,
    get_messages,
    list_sessions,
    rename_session,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/chat", tags=["chat"])


class ChatSessionCreateRequest(BaseModel):
    title: str | None = None


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
    )
    try:
        return generate_chat_response(
            session=db,
            request=internal,
            settings=settings,
        )
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
