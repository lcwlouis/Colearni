from __future__ import annotations

from typing import Any

from adapters.db.dependencies import get_db_session
from adapters.llm.factory import build_graph_llm_client
from core.schemas import LevelUpQuizSubmitResponse, QuizCreateResponse
from core.settings import Settings
from domain.learning.level_up import (
    LevelUpQuizGradingError,
    LevelUpQuizNotFoundError,
    LevelUpQuizUnavailableError,
    LevelUpQuizValidationError,
    create_level_up_quiz,
    submit_level_up_quiz,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


class CreateLevelUpQuizRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    session_id: int | None = Field(default=None, gt=0)
    question_count: int | None = Field(default=None, ge=5, le=12)
    items: list[dict[str, Any]] | None = None


class SubmitLevelUpQuizRequest(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    answers: list[dict[str, Any]] = Field(min_length=1)


@router.post(
    "/level-up",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizCreateResponse,
)
def create_quiz_level_up(
    payload: CreateLevelUpQuizRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> QuizCreateResponse:
    llm_client = getattr(request.app.state, "graph_llm_client", None)
    if llm_client is None:
        settings_state = getattr(request.app.state, "settings", None)
        settings = settings_state if isinstance(settings_state, Settings) else None
        try:
            llm_client = build_graph_llm_client(settings=settings)
        except ValueError:
            llm_client = None
    try:
        return QuizCreateResponse.model_validate(
            create_level_up_quiz(
                db,
                workspace_id=payload.workspace_id,
                user_id=payload.user_id,
                concept_id=payload.concept_id,
                session_id=payload.session_id,
                question_count=payload.question_count,
                items=payload.items,
                llm_client=llm_client,
            )
        )
    except LevelUpQuizNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LevelUpQuizValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/{quiz_id}/submit", response_model=LevelUpQuizSubmitResponse)
def submit_quiz_level_up(
    quiz_id: int,
    payload: SubmitLevelUpQuizRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> LevelUpQuizSubmitResponse:
    llm_client = getattr(request.app.state, "graph_llm_client", None)
    if llm_client is None:
        settings_state = getattr(request.app.state, "settings", None)
        settings = settings_state if isinstance(settings_state, Settings) else None
        try:
            llm_client = build_graph_llm_client(settings=settings)
        except ValueError:
            llm_client = None

    try:
        return LevelUpQuizSubmitResponse.model_validate(
            submit_level_up_quiz(
                db,
                quiz_id=quiz_id,
                workspace_id=payload.workspace_id,
                user_id=payload.user_id,
                answers=payload.answers,
                llm_client=llm_client,
            )
        )
    except LevelUpQuizNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (LevelUpQuizValidationError, LevelUpQuizGradingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LevelUpQuizUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
