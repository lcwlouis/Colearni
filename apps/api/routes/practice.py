"""Practice flashcard and quiz routes (workspace-scoped)."""

from __future__ import annotations

from typing import Any

from adapters.db.chat import ChatNotFoundError, resolve_session_by_public_id
from adapters.db.dependencies import get_db_session
from adapters.llm.factory import build_graph_llm_client
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import (
    FlashcardRunDetailResponse,
    FlashcardRunListResponse,
    FlashcardRateRequest,
    FlashcardRateResponse,
    PracticeQuizDetailResponse,
    PracticeFlashcardsResponse,
    PracticeQuizHistoryListResponse,
    PracticeQuizSubmitResponse,
    QuizCreateResponse,
    StatefulFlashcardsResponse,
)
from core.settings import Settings
from domain.learning.practice import (
    PracticeGenerationError,
    PracticeGradingError,
    PracticeNotFoundError,
    PracticeUnavailableError,
    PracticeValidationError,
    create_practice_quiz,
    get_flashcard_run,
    get_practice_quiz,
    generate_practice_flashcards,
    generate_stateful_flashcards,
    list_flashcard_runs,
    list_practice_quizzes,
    rate_flashcard,
    submit_practice_quiz,
)
from domain.learning.spaced_repetition import get_due_flashcards
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/practice", tags=["practice"])


class FlashcardsRequest(BaseModel):
    concept_id: int = Field(gt=0)
    card_count: int = Field(default=6, ge=3, le=12)


class CreateQuizRequest(BaseModel):
    concept_id: int = Field(gt=0)
    session_id: str | None = Field(default=None, description="Session UUID public_id")
    question_count: int = Field(default=4, ge=3, le=6)


class SubmitQuizRequest(BaseModel):
    answers: list[dict[str, Any]] = Field(min_length=1)


class StatefulFlashcardsRequest(BaseModel):
    concept_id: int = Field(gt=0)
    card_count: int = Field(default=6, ge=3, le=12)


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


@router.post("/flashcards", response_model=PracticeFlashcardsResponse)
def flashcards(
    payload: FlashcardsRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> PracticeFlashcardsResponse:
    try:
        return PracticeFlashcardsResponse.model_validate(
            generate_practice_flashcards(
                db,
                workspace_id=ws.workspace_id,
                concept_id=payload.concept_id,
                card_count=payload.card_count,
                llm_client=_llm_client(request),
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)


@router.post(
    "/quizzes",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizCreateResponse,
)
def create_quiz(
    payload: CreateQuizRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> QuizCreateResponse:
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
            create_practice_quiz(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                concept_id=payload.concept_id,
                session_id=resolved_session_id,
                question_count=payload.question_count,
                llm_client=_llm_client(request),
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)


@router.post("/quizzes/{quiz_id}/submit", response_model=PracticeQuizSubmitResponse)
def submit_quiz(
    quiz_id: int,
    payload: SubmitQuizRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> PracticeQuizSubmitResponse:
    try:
        return PracticeQuizSubmitResponse.model_validate(
            submit_practice_quiz(
                db,
                quiz_id=quiz_id,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                answers=payload.answers,
                llm_client=_llm_client(request),
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeGradingError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)


@router.get("/quizzes", response_model=PracticeQuizHistoryListResponse)
def list_quizzes(
    concept_id: int | None = None,
    limit: int = 20,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> PracticeQuizHistoryListResponse:
    try:
        return PracticeQuizHistoryListResponse.model_validate(
            list_practice_quizzes(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                concept_id=concept_id,
                limit=min(limit, 100),
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
    ) as exc:
        _raise_http(exc)


@router.get("/quizzes/{quiz_id}", response_model=PracticeQuizDetailResponse)
def get_quiz(
    quiz_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> PracticeQuizDetailResponse:
    try:
        return PracticeQuizDetailResponse.model_validate(
            get_practice_quiz(
                db,
                quiz_id=quiz_id,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
    ) as exc:
        _raise_http(exc)


# ── Slice 10: Stateful flashcard endpoints ────────────────────────────


@router.post("/flashcards/stateful", response_model=StatefulFlashcardsResponse)
def stateful_flashcards(
    payload: StatefulFlashcardsRequest,
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> StatefulFlashcardsResponse:
    """Generate stateful flashcards persisted to the bank."""
    try:
        return StatefulFlashcardsResponse.model_validate(
            generate_stateful_flashcards(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                concept_id=payload.concept_id,
                card_count=payload.card_count,
                llm_client=_llm_client(request),
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
        PracticeGenerationError,
        PracticeUnavailableError,
    ) as exc:
        _raise_http(exc)


@router.post("/flashcards/rate", response_model=FlashcardRateResponse)
def rate_flashcard_route(
    payload: FlashcardRateRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> FlashcardRateResponse:
    """Rate a flashcard (again/hard/good/easy)."""
    try:
        return FlashcardRateResponse.model_validate(
            rate_flashcard(
                db,
                flashcard_id=payload.flashcard_id,
                user_id=ws.user.id,
                self_rating=payload.self_rating,
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
    ) as exc:
        _raise_http(exc)


@router.get("/flashcards/due")
def due_flashcards_route(
    limit: int = 10,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> dict:
    """Return flashcards due for spaced-repetition review."""
    cards = get_due_flashcards(
        db,
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        limit=min(limit, 50),
    )
    return {"workspace_id": ws.workspace_id, "due_flashcards": cards}


@router.get("/flashcards/runs", response_model=FlashcardRunListResponse)
def list_flashcard_runs_route(
    concept_id: int | None = None,
    limit: int = 20,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> FlashcardRunListResponse:
    try:
        return FlashcardRunListResponse.model_validate(
            list_flashcard_runs(
                db,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
                concept_id=concept_id,
                limit=min(limit, 100),
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
    ) as exc:
        _raise_http(exc)


@router.get("/flashcards/runs/{run_id}", response_model=FlashcardRunDetailResponse)
def get_flashcard_run_route(
    run_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> FlashcardRunDetailResponse:
    try:
        return FlashcardRunDetailResponse.model_validate(
            get_flashcard_run(
                db,
                run_id=run_id,
                workspace_id=ws.workspace_id,
                user_id=ws.user.id,
            )
        )
    except (
        PracticeNotFoundError,
        PracticeValidationError,
    ) as exc:
        _raise_http(exc)


@router.get("/concepts/{concept_id}/activity")
def concept_activity_route(
    concept_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Return aggregate study activity for a concept (AR7.1)."""
    from domain.learning.concept_activity import get_concept_activity

    try:
        return get_concept_activity(
            db,
            workspace_id=ws.workspace_id,
            user_id=ws.user.id,
            concept_id=concept_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc
