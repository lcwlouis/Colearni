import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.concepts import (
    get_primer_generator,
    get_quiz_generator,
    get_quiz_grader,
    get_session_factory,
)
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.mastery import MasteryRecord, QuizAttempt
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.concept import ConceptPrimerOutput, PrimerKeyTerm
from backend.app.schemas.mastery import PerQuestionEvaluation, QuizEvaluation, QuizQuestion


class _FakeQuizGenerator:
    async def generate(
        self,
        *,
        concept: ConceptNode,
        quiz_type: str,
        prior_quiz_context: str = "",
    ):
        return [
            QuizQuestion(
                id="q1",
                type="multiple_choice",
                prompt=f"Explain {concept.title}.",
                mastery_label=concept.mastery_check_labels[0],
                difficulty="light",
                options=["Correct option", "Distractor", "Another distractor"],
            ),
            QuizQuestion(
                id="q2",
                type="short_answer",
                prompt=f"Apply {concept.title}.",
                mastery_label=concept.mastery_check_labels[0],
                difficulty="standard",
            ),
        ]


class _FakeQuizGrader:
    def __init__(self, score: float):
        self.score = score

    async def grade(self, *, concept: ConceptNode, questions, answers):
        return QuizEvaluation(
            score=self.score,
            passed=self.score >= 0.7,
            per_question=[
                PerQuestionEvaluation(
                    question_id=question.id,
                    score=self.score,
                    feedback=f"Feedback for {question.id}",
                )
                for question in questions
            ],
            overall_feedback=f"Overall feedback for {concept.title}",
        )


class _FakePrimerGenerator:
    def __init__(self):
        self.calls = 0

    def _output(self, concept):
        return ConceptPrimerOutput(
            overview=f"Orientation for {concept.title}.",
            key_terms=[
                PrimerKeyTerm(term="Term A", definition="Definition A."),
                PrimerKeyTerm(term="Term B", definition="Definition B."),
                PrimerKeyTerm(term="Term C", definition="Definition C."),
            ],
            sample_questions=[
                "Walk me through this concept.",
                "Give me one hint to start.",
                "Check my understanding.",
            ],
        )

    async def generate(self, *, concept: ConceptNode, trail: Trail, neighbour_context: dict):
        self.calls += 1
        return self._output(concept)

    async def generate_stream(self, *, concept: ConceptNode, trail: Trail, neighbour_context: dict):
        self.calls += 1
        payload = json.dumps(self._output(concept).model_dump(mode="json"))
        # Reasoning streams ahead of the output, as reasoning models do.
        yield ("thinking", "Considering the concept's neighbours...")
        mid = len(payload) // 2
        yield ("token", payload[:mid])
        yield ("token", payload[mid:])


@pytest.fixture
async def db_engine(tmp_path):
    # File-backed SQLite so the detached primer background task can open its own
    # connection concurrently with the request session (a single shared
    # in-memory connection cannot serialize the two). Production uses Postgres
    # with separate pooled connections.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'concepts.db'}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_client(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Detached primer generation builds its own session from this factory; bind
    # it to the in-memory test engine so the background task and reads agree.
    app.dependency_overrides[get_session_factory] = lambda: async_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_concept_graph(db_engine) -> tuple[uuid.UUID, uuid.UUID, dict[str, uuid.UUID]]:
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        workspace = Workspace(name="Concept Workspace")
        session.add(workspace)
        await session.flush()
        trail = Trail(
            workspace_id=workspace.id,
            title="Networking",
            topic="Networks",
            goal="Understand routing",
            target_depth="apply",
        )
        session.add(trail)
        await session.flush()
        node_specs = [
            ("internet", "Internet", "umbrella"),
            ("ip", "IP Addressing", "topic"),
            ("routing", "Routing", "topic"),
            ("subnetting", "Subnetting", "subtopic"),
            ("packet-switching", "Packet Switching", "subtopic"),
        ]
        nodes = {
            slug: ConceptNode(
                trail_id=trail.id,
                slug=slug,
                title=title,
                node_type="concept",
                concept_level=level,
                difficulty="beginner",
                bloom_level="understand",
                mastery_check_labels=[f"check_{slug}"],
                metadata_json={},
            )
            for slug, title, level in node_specs
        }
        session.add_all(nodes.values())
        await session.flush()
        session.add_all(
            [
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["ip"].id,
                    target_node_id=nodes["routing"].id,
                    relation_type="prerequisite",
                ),
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["routing"].id,
                    target_node_id=nodes["subnetting"].id,
                    relation_type="contains",
                ),
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["internet"].id,
                    target_node_id=nodes["routing"].id,
                    relation_type="contains",
                ),
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["routing"].id,
                    target_node_id=nodes["packet-switching"].id,
                    relation_type="application",
                ),
            ]
        )
        await session.commit()
        return workspace.id, trail.id, {slug: node.id for slug, node in nodes.items()}


async def test_get_concept_detail_populates_edge_groups(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["concept"]["title"] == "Routing"
    assert [node["title"] for node in data["prerequisites"]] == ["IP Addressing"]
    assert [node["title"] for node in data["contained_nodes"]] == ["Subnetting"]
    assert [node["title"] for node in data["containing_nodes"]] == ["Internet"]
    assert [node["title"] for node in data["related"]] == ["Packet Switching"]
    assert data["mastery"]["status"] == "not_started"
    assert data["mastery"]["score"] == 0.0
    assert data["sources"] == []


async def test_get_concept_detail_returns_real_mastery(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        session.add(
            MasteryRecord(
                workspace_id=workspace_id,
                concept_id=ids["routing"],
                status="needs_review",
                bloom_level="understand",
                score=0.6,
            )
        )
        await session.commit()

    resp = await api_client.get(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mastery"]["status"] == "needs_review"
    assert data["mastery"]["score"] == pytest.approx(0.6)


async def test_level_up_route_returns_generated_quiz(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    app.dependency_overrides[get_quiz_generator] = lambda: _FakeQuizGenerator()

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/level-up"
        )
    finally:
        app.dependency_overrides.pop(get_quiz_generator, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["quiz_type"] == "level_up"
    assert [question["id"] for question in data["questions"]] == ["q1", "q2"]


async def test_level_up_route_reuses_draft_unless_force_new(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    generator = _FakeQuizGenerator()
    app.dependency_overrides[get_quiz_generator] = lambda: generator

    try:
        first = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/level-up"
        )
        second = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/level-up"
        )
        fresh = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/level-up",
            json={"force_new": True},
        )
    finally:
        app.dependency_overrides.pop(get_quiz_generator, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert fresh.status_code == 200
    assert second.json()["questions"] == first.json()["questions"]


async def test_practice_route_returns_generated_quiz(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    app.dependency_overrides[get_quiz_generator] = lambda: _FakeQuizGenerator()

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/practice"
        )
    finally:
        app.dependency_overrides.pop(get_quiz_generator, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["quiz_type"] == "practice"
    assert [question["id"] for question in data["questions"]] == ["q1", "q2"]


async def test_level_up_grade_pass_updates_mastered_and_stores_attempt(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    app.dependency_overrides[get_quiz_grader] = lambda: _FakeQuizGrader(0.85)

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/grade",
            json={
                "questions": [
                    {
                        "id": "q1",
                        "type": "short_answer",
                        "prompt": "Explain routing.",
                        "mastery_label": "check_routing",
                    },
                    {
                        "id": "q2",
                        "type": "long_answer",
                        "prompt": "Apply routing.",
                        "mastery_label": "check_routing",
                    },
                ],
                "answers": [
                    {"question_id": "q1", "answer": "Routing decides where packets go."},
                    {"question_id": "q2", "answer": "Routers forward packets hop by hop."},
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(get_quiz_grader, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["passed"] is True
    assert data["mastery_status"] == "mastered"

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        record = await session.scalar(
            select(MasteryRecord).where(MasteryRecord.concept_id == ids["routing"])
        )
        attempt = await session.scalar(select(QuizAttempt))
    assert record is not None
    assert record.status == "mastered"
    assert attempt is not None
    assert attempt.quiz_type == "level_up"


async def test_level_up_grade_fail_updates_needs_review(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    app.dependency_overrides[get_quiz_grader] = lambda: _FakeQuizGrader(0.4)

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/grade",
            json={
                "questions": [
                    {
                        "id": "q1",
                        "type": "short_answer",
                        "prompt": "Explain routing.",
                        "mastery_label": "check_routing",
                    }
                ],
                "answers": [{"question_id": "q1", "answer": "Not sure."}],
            },
        )
    finally:
        app.dependency_overrides.pop(get_quiz_grader, None)

    assert resp.status_code == 200
    assert resp.json()["mastery_status"] == "needs_review"


async def test_practice_grade_does_not_update_mastery(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    app.dependency_overrides[get_quiz_grader] = lambda: _FakeQuizGrader(0.95)

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/practice/grade",
            json={
                "questions": [
                    {
                        "id": "q1",
                        "type": "short_answer",
                        "prompt": "Explain routing.",
                        "mastery_label": "check_routing",
                    }
                ],
                "answers": [{"question_id": "q1", "answer": "Routing forwards packets."}],
            },
        )
    finally:
        app.dependency_overrides.pop(get_quiz_grader, None)

    assert resp.status_code == 200
    assert resp.json()["mastery_status"] == "not_started"

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        record = await session.scalar(
            select(MasteryRecord).where(MasteryRecord.concept_id == ids["routing"])
        )
        attempt = await session.scalar(select(QuizAttempt))
    assert record is None
    assert attempt is not None
    assert attempt.quiz_type == "practice"


async def test_get_missing_concept_returns_404(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_concept_graph(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{uuid.uuid4()}"
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_get_concept_wrong_workspace_returns_404(api_client, db_engine):
    _, trail_id, ids = await _seed_concept_graph(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{uuid.uuid4()}/trails/{trail_id}/concepts/{ids['routing']}"
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_concept_detail_omits_primer_until_generated(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}"
    )

    assert resp.status_code == 200
    assert resp.json()["primer"] is None


async def test_primer_route_generates_and_surfaces_in_detail(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    generator = _FakePrimerGenerator()
    app.dependency_overrides[get_primer_generator] = lambda: generator

    try:
        first = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/primer"
        )
        # Second call must be served from cache without re-invoking the generator.
        second = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/primer"
        )
        detail = await api_client.get(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}"
        )
    finally:
        app.dependency_overrides.pop(get_primer_generator, None)

    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body["overview"] == "Orientation for Routing."
    assert [term["term"] for term in body["key_terms"]] == ["Term A", "Term B", "Term C"]
    assert second.json() == body
    assert generator.calls == 1

    assert detail.status_code == 200
    primer = detail.json()["primer"]
    assert primer is not None
    assert primer["overview"] == "Orientation for Routing."


async def test_primer_route_force_new_regenerates(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    generator = _FakePrimerGenerator()
    app.dependency_overrides[get_primer_generator] = lambda: generator

    try:
        await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/primer"
        )
        forced = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/primer",
            json={"force_new": True},
        )
    finally:
        app.dependency_overrides.pop(get_primer_generator, None)

    assert forced.status_code == 200
    assert generator.calls == 2


async def test_primer_route_missing_concept_returns_404(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_concept_graph(db_engine)
    app.dependency_overrides[get_primer_generator] = lambda: _FakePrimerGenerator()

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{uuid.uuid4()}/primer"
        )
    finally:
        app.dependency_overrides.pop(get_primer_generator, None)

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_primer_stream_route_emits_status_token_done(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    generator = _FakePrimerGenerator()
    app.dependency_overrides[get_primer_generator] = lambda: generator

    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}"
            f"/concepts/{ids['routing']}/primer/stream"
        )
    finally:
        app.dependency_overrides.pop(get_primer_generator, None)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "event: status" in body
    assert "event: thinking" in body
    assert "event: token" in body
    assert "event: done" in body
    assert body.index("event: status") < body.index("event: thinking")
    assert body.index("event: thinking") < body.index("event: token") < body.index("event: done")
    assert generator.calls == 1


async def test_primer_stream_route_cache_hit_emits_only_done(api_client, db_engine):
    workspace_id, trail_id, ids = await _seed_concept_graph(db_engine)
    generator = _FakePrimerGenerator()
    app.dependency_overrides[get_primer_generator] = lambda: generator

    try:
        # Prime the cache via the non-stream route.
        await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{ids['routing']}/primer"
        )
        calls_before = generator.calls
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/trails/{trail_id}"
            f"/concepts/{ids['routing']}/primer/stream"
        )
    finally:
        app.dependency_overrides.pop(get_primer_generator, None)

    assert resp.status_code == 200
    body = resp.text
    assert "event: done" in body
    assert "event: status" not in body
    assert "event: token" not in body
    # Cache hit => no extra model call.
    assert generator.calls == calls_before
