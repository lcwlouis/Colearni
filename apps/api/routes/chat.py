"""Chat route definitions."""

from __future__ import annotations

from adapters.db.chat import ChatNotFoundError
from adapters.db.dependencies import get_db_session
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
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatSessionCreateRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    title: str | None = None


@router.post("/sessions", response_model=ChatSessionSummary, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    payload: ChatSessionCreateRequest,
    db: Session = Depends(get_db_session),
) -> ChatSessionSummary:
    return ChatSessionSummary.model_validate(
        create_session(
            db,
            workspace_id=payload.workspace_id,
            user_id=payload.user_id,
            title=payload.title,
        )
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
def get_chat_sessions(
    workspace_id: int = Query(gt=0),
    user_id: int = Query(gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db_session),
) -> ChatSessionListResponse:
    return ChatSessionListResponse.model_validate(
        list_sessions(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
        )
    )


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesResponse)
def get_chat_session_messages(
    session_id: int,
    workspace_id: int = Query(gt=0),
    user_id: int = Query(gt=0),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db_session),
) -> ChatMessagesResponse:
    try:
        return ChatMessagesResponse.model_validate(
            get_messages(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                session_id=session_id,
                limit=limit,
            )
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session_route(
    session_id: int,
    workspace_id: int = Query(gt=0),
    user_id: int = Query(gt=0),
    db: Session = Depends(get_db_session),
) -> Response:
    try:
        delete_session(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            session_id=session_id,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/respond", response_model=AssistantResponseEnvelope)
def respond_chat(
    payload: ChatRespondRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> AssistantResponseEnvelope:
    """Generate one verified assistant response envelope."""
    settings_state = getattr(request.app.state, "settings", None)
    settings = settings_state if isinstance(settings_state, Settings) else None
    try:
        return generate_chat_response(
            session=db,
            request=payload,
            settings=settings,
        )
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
