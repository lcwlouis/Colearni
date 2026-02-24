from __future__ import annotations

from typing import Any

from adapters.db.dependencies import get_db_session
from adapters.llm.factory import build_graph_llm_client
from core.settings import Settings
from domain.learning.practice import (
    PracticeGenerationError,
    PracticeGradingError,
    PracticeNotFoundError,
    PracticeUnavailableError,
    PracticeValidationError,
    create_practice_quiz,
    generate_practice_flashcards,
    submit_practice_quiz,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/practice", tags=["practice"])


class FlashcardsRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    card_count: int = Field(default=6, ge=3, le=12)


class CreateQuizRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    session_id: int | None = Field(default=None, gt=0)
    question_count: int = Field(default=4, ge=3, le=6)


class SubmitQuizRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    answers: list[dict[str, Any]] = Field(min_length=1)


def _llm_client(request: Request) -> Any:
    client = getattr(request.app.state, "graph_llm_client", None)
    if client is not None:
        return client
    state = getattr(request.app.state, "settings", None)
    settings = state if isinstance(state, Settings) else None
    try:
        return build_graph_llm_client(settings=settings)
    except ValueError:
        return None


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, PracticeNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, PracticeUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/flashcards")
def flashcards(
    payload: FlashcardsRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        return generate_practice_flashcards(
            db,
            workspace_id=payload.workspace_id,
            concept_id=payload.concept_id,
            card_count=payload.card_count,
            llm_client=_llm_client(request),
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)


@router.post("/quizzes", status_code=status.HTTP_201_CREATED)
def create_quiz(
    payload: CreateQuizRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        return create_practice_quiz(
            db,
            workspace_id=payload.workspace_id,
            user_id=payload.user_id,
            concept_id=payload.concept_id,
            session_id=payload.session_id,
            question_count=payload.question_count,
            llm_client=_llm_client(request),
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(
    quiz_id: int,
    payload: SubmitQuizRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        return submit_practice_quiz(
            db,
            quiz_id=quiz_id,
            workspace_id=payload.workspace_id,
            user_id=payload.user_id,
            answers=payload.answers,
            llm_client=_llm_client(request),
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeGradingError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)
