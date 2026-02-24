"""Chat route definitions."""

from __future__ import annotations

from adapters.db.dependencies import get_db_session
from core.schemas import AssistantResponseEnvelope, ChatRespondRequest
from core.settings import Settings
from domain.chat.respond import generate_chat_response
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/respond", response_model=AssistantResponseEnvelope)
def respond_chat(
    payload: ChatRespondRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> AssistantResponseEnvelope:
    """Generate one verified assistant response envelope."""
    settings_state = getattr(request.app.state, "settings", None)
    settings = settings_state if isinstance(settings_state, Settings) else None
    return generate_chat_response(
        session=db,
        request=payload,
        settings=settings,
    )
