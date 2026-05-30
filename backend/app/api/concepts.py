import uuid
from typing import cast

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.llm_client import LLMClient
from backend.app.db import AsyncSessionLocal, get_session
from backend.app.schemas.concept import (
    ConceptDetailResponse,
    ConceptPrimerRead,
    PrimerGenerateRequest,
)
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.mastery import (
    GradeResult,
    LevelUpCard,
    QuizGenerateRequest,
    QuizGradeRequest,
)
from backend.app.schemas.source import ConceptSourceListItem, ConceptSourcesResponse
from backend.app.schemas.types import QuizType, SourceAccess, SourceOrigin
from backend.app.services.concept_primers import (
    LLMPrimerGenerator,
    PrimerGenerationError,
    PrimerGenerator,
    generate_concept_primer,
    stream_concept_primer,
)
from backend.app.services.concept_source_links import list_concept_sources
from backend.app.services.graph_view import get_concept_detail
from backend.app.services.quizzes import (
    LLMQuizGenerator,
    LLMQuizGrader,
    QuizGenerationError,
    QuizGenerator,
    QuizGrader,
    QuizGradingError,
    QuizValidationError,
    generate_quiz_card,
    grade_quiz_submission,
)
from backend.app.settings import settings

router = APIRouter(prefix="/api/workspaces/{workspace_id}/trails/{trail_id}/concepts")
concept_sources_router = APIRouter(prefix="/api/workspaces/{workspace_id}/concepts")


def get_quiz_generator() -> QuizGenerator:
    return LLMQuizGenerator(client=LLMClient.from_settings(settings))


def get_quiz_grader() -> QuizGrader:
    return LLMQuizGrader(client=LLMClient.from_settings(settings))


def get_primer_generator() -> PrimerGenerator:
    return LLMPrimerGenerator(client=LLMClient.from_settings(settings))


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # Sessionmaker handed to detached primer generation so the background task
    # owns a session that outlives the request. Tests override this to bind the
    # background task to their in-memory engine.
    return AsyncSessionLocal


@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept_detail_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ConceptDetailResponse | JSONResponse:
    try:
        detail = await get_concept_detail(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    return ConceptDetailResponse.model_validate(detail)


@router.post("/{concept_id}/primer", response_model=ConceptPrimerRead)
async def generate_primer_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: PrimerGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
    generator: PrimerGenerator = Depends(get_primer_generator),
) -> ConceptPrimerRead | JSONResponse:
    try:
        return await generate_concept_primer(
            session,
            generator,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            force_new=body.force_new if body else False,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except PrimerGenerationError as exc:
        await session.rollback()
        return _llm_error(str(exc))


@router.post("/{concept_id}/primer/stream", response_model=None)
async def stream_primer_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    generator: PrimerGenerator = Depends(get_primer_generator),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> StreamingResponse:
    return StreamingResponse(
        stream_concept_primer(
            session,
            generator,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            session_factory=session_factory,
        ),
        media_type="text/event-stream",
    )


@concept_sources_router.get(
    "/{concept_id}/sources",
    response_model=ConceptSourcesResponse,
    responses={404: {"model": ErrorEnvelope}},
)
async def get_concept_sources_route(
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ConceptSourcesResponse | JSONResponse:
    try:
        rows = await list_concept_sources(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        return _not_found(str(exc))
    sources = []
    for link, source, ingestion_status in rows:
        sources.append(
            ConceptSourceListItem(
                source_id=source.id,
                title=source.title,
                origin=cast(SourceOrigin, source.origin),
                access=cast(SourceAccess, source.access),
                url=source.url,
                relation=link.relation,
                ingestion_status=ingestion_status,
            )
        )
    return ConceptSourcesResponse(sources=sources)


@router.post("/{concept_id}/level-up", response_model=LevelUpCard)
async def generate_level_up_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: QuizGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
    generator: QuizGenerator = Depends(get_quiz_generator),
) -> LevelUpCard | JSONResponse:
    try:
        return await generate_quiz_card(
            session,
            generator,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            quiz_type="level_up",
            force_new=body.force_new if body else False,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except QuizGenerationError as exc:
        await session.rollback()
        return _llm_error(str(exc))


@router.post("/{concept_id}/practice", response_model=LevelUpCard)
async def generate_practice_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: QuizGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
    generator: QuizGenerator = Depends(get_quiz_generator),
) -> LevelUpCard | JSONResponse:
    try:
        return await generate_quiz_card(
            session,
            generator,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            quiz_type="practice",
            force_new=body.force_new if body else False,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except QuizGenerationError as exc:
        await session.rollback()
        return _llm_error(str(exc))


@router.post("/{concept_id}/grade", response_model=GradeResult)
async def grade_level_up_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: QuizGradeRequest,
    session: AsyncSession = Depends(get_session),
    grader: QuizGrader = Depends(get_quiz_grader),
) -> GradeResult | JSONResponse:
    return await _grade_route(
        session,
        grader,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
        quiz_type="level_up",
        body=body,
    )


@router.post("/{concept_id}/practice/grade", response_model=GradeResult)
async def grade_practice_route(
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    body: QuizGradeRequest,
    session: AsyncSession = Depends(get_session),
    grader: QuizGrader = Depends(get_quiz_grader),
) -> GradeResult | JSONResponse:
    return await _grade_route(
        session,
        grader,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
        quiz_type="practice",
        body=body,
    )


async def _grade_route(
    session: AsyncSession,
    grader: QuizGrader,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    quiz_type: QuizType,
    body: QuizGradeRequest,
) -> GradeResult | JSONResponse:
    try:
        return await grade_quiz_submission(
            session,
            grader,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            quiz_type=quiz_type,
            questions=body.questions,
            answers=body.answers,
        )
    except LookupError as exc:
        await session.rollback()
        return _not_found(str(exc))
    except QuizValidationError as exc:
        await session.rollback()
        return _invalid_input(str(exc))
    except QuizGradingError as exc:
        await session.rollback()
        return _llm_error(str(exc))


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )


def _invalid_input(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=ErrorEnvelope(error=ErrorBody(code="invalid_input", message=message)).model_dump(),
    )


def _llm_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorEnvelope(error=ErrorBody(code="llm_error", message=message)).model_dump(),
    )
