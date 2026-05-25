import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.mastery import MasteryRecord
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.mastery import MasteryState
from backend.app.services.recommendation import get_next_concept_for_trail, recommend_next_concept


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def api_client(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def test_single_not_started_concept_no_prerequisites_is_recommended():
    concept = _node("vectors", "Vectors")

    result = recommend_next_concept(
        concepts=[concept],
        edges=[],
        mastery_map={concept.id: _state(concept, "not_started")},
    )

    assert result.concept == concept
    assert result.all_mastered is False
    assert result.reason


def test_prerequisite_satisfied_candidate_beats_unsatisfied_candidate():
    ready = _node("matrices", "Matrices")
    blocked = _node("eigenvectors", "Eigenvectors")
    mastered_prerequisite = _node("vectors", "Vectors")
    unstarted_prerequisite = _node("linear-maps", "Linear Maps")
    edges = [
        _edge(mastered_prerequisite, ready, "prerequisite"),
        _edge(unstarted_prerequisite, blocked, "prerequisite"),
    ]
    mastery_map = {
        ready.id: _state(ready, "not_started"),
        blocked.id: _state(blocked, "not_started"),
        mastered_prerequisite.id: _state(mastered_prerequisite, "mastered"),
        unstarted_prerequisite.id: _state(unstarted_prerequisite, "not_started"),
    }

    result = recommend_next_concept(
        concepts=[ready, blocked],
        edges=edges,
        mastery_map=mastery_map,
    )

    assert result.concept == ready


def test_needs_review_beats_not_started_when_prerequisites_satisfied():
    review = _node("dot-products", "Dot Products")
    fresh = _node("matrices", "Matrices")

    result = recommend_next_concept(
        concepts=[fresh, review],
        edges=[],
        mastery_map={
            fresh.id: _state(fresh, "not_started"),
            review.id: _state(review, "needs_review"),
        },
    )

    assert result.concept == review


def test_topic_beats_umbrella_when_otherwise_tied():
    topic = _node("vectors", "Vectors", concept_level="topic")
    umbrella = _node("linear-algebra", "Linear Algebra", concept_level="umbrella")

    result = recommend_next_concept(
        concepts=[umbrella, topic],
        edges=[],
        mastery_map={
            umbrella.id: _state(umbrella, "not_started"),
            topic.id: _state(topic, "not_started"),
        },
    )

    assert result.concept == topic


def test_beginner_beats_advanced_for_same_level_and_status():
    beginner = _node("vectors", "Vectors", difficulty="beginner")
    advanced = _node("eigenvectors", "Eigenvectors", difficulty="advanced")

    result = recommend_next_concept(
        concepts=[advanced, beginner],
        edges=[],
        mastery_map={
            advanced.id: _state(advanced, "not_started"),
            beginner.id: _state(beginner, "not_started"),
        },
    )

    assert result.concept == beginner


def test_all_mastered_returns_no_concept_and_review_reason():
    concept = _node("vectors", "Vectors")

    result = recommend_next_concept(
        concepts=[concept],
        edges=[],
        mastery_map={concept.id: _state(concept, "mastered")},
    )

    assert result.concept is None
    assert result.all_mastered is True
    assert "mastered" in result.reason


async def test_empty_trail_returns_no_concepts_reason(db_session: AsyncSession):
    workspace, trail, _ = await _seed_trail(db_session, concept_specs=[])

    result = await get_next_concept_for_trail(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
    )

    assert result.concept is None
    assert result.all_mastered is False
    assert "No concepts" in result.reason


def test_recommendation_is_deterministic_for_identical_inputs():
    alpha = _node("alpha", "Alpha")
    beta = _node("beta", "Beta")
    mastery_map = {
        beta.id: _state(beta, "not_started"),
        alpha.id: _state(alpha, "not_started"),
    }

    first = recommend_next_concept(concepts=[beta, alpha], edges=[], mastery_map=mastery_map)
    second = recommend_next_concept(concepts=[beta, alpha], edges=[], mastery_map=mastery_map)

    assert first.concept == second.concept == alpha


async def test_next_concept_route_returns_expected_concept(
    db_session: AsyncSession,
    api_client: AsyncClient,
):
    workspace, trail, nodes = await _seed_trail(
        db_session,
        concept_specs=[
            ("vectors", "Vectors", "topic", "beginner"),
            ("matrices", "Matrices", "topic", "beginner"),
        ],
    )
    await _add_mastery(db_session, workspace, nodes["vectors"], "mastered")
    db_session.add(_edge(nodes["vectors"], nodes["matrices"], "prerequisite"))
    await db_session.commit()

    response = await api_client.get(f"/api/workspaces/{workspace.id}/trails/{trail.id}/next")

    assert response.status_code == 200
    assert response.json()["concept_id"] == str(nodes["matrices"].id)


async def test_next_concept_route_unknown_trail_returns_404(
    db_session: AsyncSession,
    api_client: AsyncClient,
):
    workspace, _, _ = await _seed_trail(db_session)
    await db_session.commit()

    response = await api_client.get(f"/api/workspaces/{workspace.id}/trails/{uuid.uuid4()}/next")

    assert response.status_code == 404


async def test_next_concept_route_other_workspace_trail_returns_404(
    db_session: AsyncSession,
    api_client: AsyncClient,
):
    _, trail, _ = await _seed_trail(db_session)
    other_workspace = Workspace(name="Other Workspace")
    db_session.add(other_workspace)
    await db_session.commit()

    response = await api_client.get(
        f"/api/workspaces/{other_workspace.id}/trails/{trail.id}/next"
    )

    assert response.status_code == 404


async def _seed_trail(
    session: AsyncSession,
    *,
    concept_specs: list[tuple[str, str, str, str]] | None = None,
) -> tuple[Workspace, Trail, dict[str, ConceptNode]]:
    workspace = Workspace(name="Recommendation Workspace")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Linear Algebra",
        topic="Linear Algebra",
        goal="Learn for ML",
        target_depth="understand",
    )
    session.add(trail)
    await session.flush()
    specs = concept_specs if concept_specs is not None else [
        ("vectors", "Vectors", "topic", "beginner")
    ]
    nodes = {
        slug: ConceptNode(
            trail_id=trail.id,
            slug=slug,
            title=title,
            node_type="concept",
            concept_level=level,
            difficulty=difficulty,
            bloom_level="understand",
            mastery_check_labels=[f"check_{slug}"],
            metadata_json={},
        )
        for slug, title, level, difficulty in specs
    }
    session.add_all(nodes.values())
    await session.flush()
    return workspace, trail, nodes


async def _add_mastery(
    session: AsyncSession,
    workspace: Workspace,
    concept: ConceptNode,
    status: str,
) -> None:
    session.add(
        MasteryRecord(
            workspace_id=workspace.id,
            concept_id=concept.id,
            status=status,
            bloom_level=concept.bloom_level,
            score=1.0 if status == "mastered" else 0.5,
        )
    )
    await session.flush()


def _node(
    slug: str,
    title: str,
    *,
    concept_level: str = "topic",
    difficulty: str = "beginner",
) -> ConceptNode:
    return ConceptNode(
        id=uuid.uuid4(),
        trail_id=uuid.uuid4(),
        slug=slug,
        title=title,
        node_type="concept",
        concept_level=concept_level,
        difficulty=difficulty,
        bloom_level="understand",
        mastery_check_labels=[f"check_{slug}"],
        metadata_json={},
    )


def _edge(source: ConceptNode, target: ConceptNode, relation_type: str) -> ConceptEdge:
    return ConceptEdge(
        trail_id=target.trail_id,
        source_node_id=source.id,
        target_node_id=target.id,
        relation_type=relation_type,
    )


def _state(concept: ConceptNode, status: str) -> MasteryState:
    return MasteryState(
        id=None,
        workspace_id=uuid.uuid4(),
        concept_id=concept.id,
        status=status,
        bloom_level=concept.bloom_level,
        score=0.0,
        updated_at=None,
    )
