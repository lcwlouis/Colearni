"""Level-up quiz routes (workspace-scoped)."""

from __future__ import annotations

from typing import Any

from adapters.db.chat import ChatNotFoundError, resolve_session_by_public_id
from adapters.db.dependencies import get_db_session
from adapters.llm.factory import build_graph_llm_client
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import LevelUpQuizSubmitResponse, QuizCreateResponse
from core.schemas import (
    LevelUpPromoteToPracticeResponse,
    LevelUpQuizDetailResponse,
    LevelUpQuizHistoryListResponse,
)
from core.settings import Settings
from domain.learning.level_up import (
    LevelUpQuizGradingError,
    LevelUpQuizNotFoundError,
    LevelUpQuizUnavailableError,
    LevelUpQuizValidationError,
    create_level_up_quiz,
    get_level_up_quiz,
    list_level_up_quizzes,
    promote_level_up_quiz_to_practice,
    submit_level_up_quiz,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/quizzes", tags=["quizzes"])


class CreateLevelUpQuizRequest(BaseModel):
    concept_id: int = Field(gt=0)
    session_id: str | None = Field(default=None, description="Session UUID public_id")
    question_count: int | None = Field(default=None, ge=5, le=12)
    items: list[dict[str, Any]] | None = None


class SubmitLevelUpQuizRequest(BaseModel):
    answers: list[dict[str, Any]] = Field(min_length=1)


@router.post(
    "/level-up",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizCreateResponse,
)
def create_quiz_level_up(
    payload: CreateLevelUpQuizRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
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

    # Resolve UUID session_id → internal int
    resolved_session_id: int | None = None
    if payload.session_id:
        try:
            resolved_session_id = resolve_session_by_public_id(
                db, public_id=payload.session_id,
                workspace_id=ws.workspace_id, user_id=ws.user.id,
            )
        except ChatNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        return QuizCreateResponse.model_validate(
            create_level_up_quiz(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                concept_id=payload.concept_id,
                session_id=resolved_session_id,
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
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Level-up quiz creation failed: {exc}",
        ) from exc


@router.get("/level-up", response_model=LevelUpQuizHistoryListResponse)
def list_quiz_level_up(
    concept_id: int | None = None,
    limit: int = 20,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> LevelUpQuizHistoryListResponse:
    try:
        return LevelUpQuizHistoryListResponse.model_validate(
            list_level_up_quizzes(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                concept_id=concept_id,
                limit=min(limit, 100),
            )
        )
    except LevelUpQuizValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/level-up/{quiz_id}", response_model=LevelUpQuizDetailResponse)
def get_quiz_level_up(
    quiz_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> LevelUpQuizDetailResponse:
    try:
        return LevelUpQuizDetailResponse.model_validate(
            get_level_up_quiz(
                db,
                quiz_id=quiz_id,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
            )
        )
    except LevelUpQuizNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LevelUpQuizValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/level-up/{quiz_id}/promote",
    status_code=status.HTTP_201_CREATED,
    response_model=LevelUpPromoteToPracticeResponse,
)
def promote_level_up_quiz_route(
    quiz_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> LevelUpPromoteToPracticeResponse:
    try:
        return LevelUpPromoteToPracticeResponse.model_validate(
            promote_level_up_quiz_to_practice(
                db,
                quiz_id=quiz_id,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
            )
        )
    except LevelUpQuizNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LevelUpQuizValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LevelUpQuizUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/{quiz_id}/submit", response_model=LevelUpQuizSubmitResponse)
def submit_quiz_level_up(
    quiz_id: int,
    payload: SubmitLevelUpQuizRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
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
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
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
