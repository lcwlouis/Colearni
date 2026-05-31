"""Tests for workspace-scoped aggregation endpoints and services."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode  # noqa: F401
from backend.app.models.mastery import MasteryRecord, QuizAttempt
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail  # noqa: F401
from backend.app.models.workspace import Workspace
from backend.app.services.source_ingestion import list_workspace_sources
from backend.app.services.workspace_aggregation import (
    get_workspace_progress,
    list_workspace_quiz_attempts,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
async def api_client(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

_SIMPLE_QUESTION = {
    "id": "q1",
    "type": "short_answer",
    "prompt": "What is X?",
    "mastery_label": "understand_x",
}
_SIMPLE_ANSWER = {"question_id": "q1", "answer": "X is Y"}


async def _make_workspace(session, *, name: str = "WS") -> Workspace:
    ws = Workspace(name=name)
    session.add(ws)
    await session.flush()
    return ws


async def _make_trail(session, *, workspace_id: uuid.UUID, title: str = "Trail") -> Trail:
    trail = Trail(
        workspace_id=workspace_id,
        title=title,
        topic=title,
        goal="Learn",
        target_depth="understand",
    )
    session.add(trail)
    await session.flush()
    return trail


async def _make_concept(session, *, trail_id: uuid.UUID, title: str = "Concept", slug: str = "concept") -> ConceptNode:
    concept = ConceptNode(
        trail_id=trail_id,
        slug=slug,
        title=title,
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=[],
        metadata_json={},
    )
    session.add(concept)
    await session.flush()
    return concept


async def _make_quiz_attempt(
    session,
    *,
    concept_id: uuid.UUID,
    passed: bool = True,
    score: float = 0.8,
    created_at: datetime | None = None,
) -> QuizAttempt:
    attempt = QuizAttempt(
        concept_id=concept_id,
        quiz_type="level_up",
        questions_json=[_SIMPLE_QUESTION],
        answers_json=[_SIMPLE_ANSWER],
        evaluator_feedback="Good",
        passed=passed,
        score=score,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def _make_mastery_record(
    session,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    status: str = "mastered",
    score: float = 0.9,
    bloom_level: str = "understand",
) -> MasteryRecord:
    record = MasteryRecord(
        workspace_id=workspace_id,
        concept_id=concept_id,
        status=status,
        bloom_level=bloom_level,
        score=score,
    )
    session.add(record)
    await session.flush()
    return record


async def _make_source(session, *, workspace_id: uuid.UUID, title: str = "Source") -> SourceRecord:
    source = SourceRecord(
        workspace_id=workspace_id,
        origin="manual",
        access="private",
        title=title,
        url=None,
        license=None,
        include_on_public_export=False,
        metadata_json={},
    )
    session.add(source)
    await session.flush()
    return source


# ── list_workspace_quiz_attempts ──────────────────────────────────────────────


async def test_quiz_attempts_empty_for_new_workspace(session):
    ws = await _make_workspace(session)
    await session.commit()

    result = await list_workspace_quiz_attempts(session, workspace_id=ws.id)

    assert result == []


async def test_quiz_attempts_scoped_to_workspace(session):
    ws1 = await _make_workspace(session, name="WS1")
    ws2 = await _make_workspace(session, name="WS2")
    trail1 = await _make_trail(session, workspace_id=ws1.id)
    trail2 = await _make_trail(session, workspace_id=ws2.id)
    concept1 = await _make_concept(session, trail_id=trail1.id)
    concept2 = await _make_concept(session, trail_id=trail2.id)
    await _make_quiz_attempt(session, concept_id=concept1.id)
    await _make_quiz_attempt(session, concept_id=concept2.id)
    await session.commit()

    result = await list_workspace_quiz_attempts(session, workspace_id=ws1.id)

    assert len(result) == 1
    assert result[0].concept_id == concept1.id


async def test_quiz_attempts_ordered_newest_first(session):
    ws = await _make_workspace(session)
    trail = await _make_trail(session, workspace_id=ws.id)
    concept = await _make_concept(session, trail_id=trail.id)
    now = datetime.now(UTC)
    older = await _make_quiz_attempt(session, concept_id=concept.id, score=0.5, created_at=now - timedelta(hours=2))
    newer = await _make_quiz_attempt(session, concept_id=concept.id, score=0.9, created_at=now)
    await session.commit()

    result = await list_workspace_quiz_attempts(session, workspace_id=ws.id)

    assert len(result) == 2
    assert result[0].id == newer.id
    assert result[1].id == older.id


async def test_quiz_attempts_not_found_raises(session):
    with pytest.raises(LookupError):
        await list_workspace_quiz_attempts(session, workspace_id=uuid.uuid4())


# ── get_workspace_progress ────────────────────────────────────────────────────


async def test_progress_returns_mastery_counts(session):
    ws = await _make_workspace(session)
    trail = await _make_trail(session, workspace_id=ws.id)
    c1 = await _make_concept(session, trail_id=trail.id, slug="c1", title="C1")
    c2 = await _make_concept(session, trail_id=trail.id, slug="c2", title="C2")
    await _make_mastery_record(session, workspace_id=ws.id, concept_id=c1.id, status="mastered", score=1.0)
    await _make_mastery_record(session, workspace_id=ws.id, concept_id=c2.id, status="learning", score=0.4)
    await session.commit()

    result = await get_workspace_progress(session, workspace_id=ws.id)

    assert len(result.trails) == 1
    trail_item = result.trails[0]
    assert trail_item.trail_id == trail.id
    summary = trail_item.mastery_summary
    assert summary.total == 2
    assert summary.mastered == 1
    assert summary.learning == 1
    assert summary.not_started == 0


async def test_progress_concepts_without_mastery_default_not_started(session):
    ws = await _make_workspace(session)
    trail = await _make_trail(session, workspace_id=ws.id)
    await _make_concept(session, trail_id=trail.id, slug="c1", title="C1")
    await session.commit()

    result = await get_workspace_progress(session, workspace_id=ws.id)

    trail_item = result.trails[0]
    assert trail_item.mastery_summary.not_started == 1
    assert trail_item.mastery_summary.total == 1
    concept_item = trail_item.concepts[0]
    assert concept_item.status == "not_started"
    assert concept_item.score == 0.0


async def test_progress_cross_workspace_isolation(session):
    ws1 = await _make_workspace(session, name="WS1")
    ws2 = await _make_workspace(session, name="WS2")
    await _make_trail(session, workspace_id=ws2.id, title="Other Trail")
    await session.commit()

    result = await get_workspace_progress(session, workspace_id=ws1.id)

    assert result.trails == []


async def test_progress_not_found_raises(session):
    with pytest.raises(LookupError):
        await get_workspace_progress(session, workspace_id=uuid.uuid4())


# ── list_workspace_sources ────────────────────────────────────────────────────


async def test_sources_empty_for_new_workspace(session):
    ws = await _make_workspace(session)
    await session.commit()

    result = await list_workspace_sources(session, workspace_id=ws.id)

    assert result == []


async def test_sources_scoped_to_workspace(session):
    ws1 = await _make_workspace(session, name="WS1")
    ws2 = await _make_workspace(session, name="WS2")
    s1 = await _make_source(session, workspace_id=ws1.id, title="Source A")
    await _make_source(session, workspace_id=ws2.id, title="Source B")
    await session.commit()

    result = await list_workspace_sources(session, workspace_id=ws1.id)

    assert len(result) == 1
    assert result[0].id == s1.id
    assert result[0].title == "Source A"


async def test_sources_not_found_raises(session):
    with pytest.raises(LookupError):
        await list_workspace_sources(session, workspace_id=uuid.uuid4())


# ── HTTP API endpoint tests ───────────────────────────────────────────────────


async def test_api_quiz_attempts_returns_200(api_client):
    resp = await api_client.post("/api/workspaces", json={"name": "Test WS"})
    ws_id = resp.json()["id"]

    resp = await api_client.get(f"/api/workspaces/{ws_id}/quiz-attempts")

    assert resp.status_code == 200
    assert resp.json()["attempts"] == []


async def test_api_quiz_attempts_404_for_unknown_workspace(api_client):
    resp = await api_client.get(f"/api/workspaces/{uuid.uuid4()}/quiz-attempts")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_api_progress_returns_200(api_client):
    resp = await api_client.post("/api/workspaces", json={"name": "Test WS"})
    ws_id = resp.json()["id"]

    resp = await api_client.get(f"/api/workspaces/{ws_id}/progress")

    assert resp.status_code == 200
    assert resp.json()["trails"] == []


async def test_api_progress_404_for_unknown_workspace(api_client):
    resp = await api_client.get(f"/api/workspaces/{uuid.uuid4()}/progress")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_api_sources_returns_200(api_client):
    resp = await api_client.post("/api/workspaces", json={"name": "Test WS"})
    ws_id = resp.json()["id"]

    resp = await api_client.get(f"/api/workspaces/{ws_id}/sources")

    assert resp.status_code == 200
    assert resp.json()["sources"] == []


async def test_api_sources_404_for_unknown_workspace(api_client):
    resp = await api_client.get(f"/api/workspaces/{uuid.uuid4()}/sources")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ── Enrichment tests ──────────────────────────────────────────────────────────


async def test_quiz_attempt_item_includes_concept_and_trail_titles(session):
    ws = await _make_workspace(session)
    trail = await _make_trail(session, workspace_id=ws.id, title="My Trail")
    concept = await _make_concept(session, trail_id=trail.id, title="My Concept")
    await _make_quiz_attempt(session, concept_id=concept.id)
    await session.commit()

    result = await list_workspace_quiz_attempts(session, workspace_id=ws.id)

    assert len(result) == 1
    item = result[0]
    assert item.concept_title == "My Concept"
    assert item.trail_id == trail.id
    assert item.trail_title == "My Trail"


async def _make_concept_source_link(
    session, *, source_id: uuid.UUID, concept_id: uuid.UUID, relation: str = "primary"
) -> ConceptSourceLink:
    link = ConceptSourceLink(source_id=source_id, concept_id=concept_id, relation=relation)
    session.add(link)
    await session.flush()
    return link


async def test_sources_linked_concepts_populated(session):
    ws = await _make_workspace(session)
    trail = await _make_trail(session, workspace_id=ws.id, title="Trail A")
    concept = await _make_concept(session, trail_id=trail.id, title="Concept A")
    source = await _make_source(session, workspace_id=ws.id, title="Source A")
    await _make_concept_source_link(session, source_id=source.id, concept_id=concept.id, relation="primary")
    await session.commit()

    result = await list_workspace_sources(session, workspace_id=ws.id)

    assert len(result) == 1
    item = result[0]
    assert len(item.linked_concepts) == 1
    link = item.linked_concepts[0]
    assert link.concept_id == concept.id
    assert link.concept_title == "Concept A"
    assert link.trail_id == trail.id
    assert link.trail_title == "Trail A"
    assert link.relation == "primary"


async def test_sources_no_links_returns_empty_linked_concepts(session):
    ws = await _make_workspace(session)
    await _make_source(session, workspace_id=ws.id, title="Orphan Source")
    await session.commit()

    result = await list_workspace_sources(session, workspace_id=ws.id)

    assert len(result) == 1
    assert result[0].linked_concepts == []
