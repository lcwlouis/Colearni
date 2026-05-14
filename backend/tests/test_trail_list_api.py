import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_client(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_trail(db_engine) -> tuple[uuid.UUID, uuid.UUID, list[ConceptNode]]:
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        workspace = Workspace(name="Graph Workspace")
        session.add(workspace)
        await session.flush()
        trail = Trail(
            workspace_id=workspace.id,
            title="Linear Algebra",
            topic="Matrices",
            goal="Understand transformations",
            target_depth="apply",
        )
        session.add(trail)
        await session.flush()
        nodes = [
            ConceptNode(
                trail_id=trail.id,
                slug="vectors",
                title="Vectors",
                node_type="concept",
                concept_level="topic",
                difficulty="beginner",
                bloom_level="understand",
                mastery_check_labels=["explain_vectors"],
                metadata_json={},
            ),
            ConceptNode(
                trail_id=trail.id,
                slug="matrices",
                title="Matrices",
                node_type="concept",
                concept_level="topic",
                difficulty="beginner",
                bloom_level="apply",
                mastery_check_labels=["multiply_matrix_vector"],
                metadata_json={},
            ),
        ]
        session.add_all(nodes)
        await session.flush()
        session.add(
            ConceptEdge(
                trail_id=trail.id,
                source_node_id=nodes[0].id,
                target_node_id=nodes[1].id,
                relation_type="prerequisite",
            )
        )
        await session.commit()
        return workspace.id, trail.id, nodes


async def test_list_trails_in_workspace_includes_computed_counts(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_trail(db_engine)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["trails"]) == 1
    assert data["trails"][0]["id"] == str(trail_id)
    assert data["trails"][0]["node_count"] == 2
    assert data["trails"][0]["edge_count"] == 1


async def test_list_trails_missing_workspace_returns_404(api_client):
    resp = await api_client.get(f"/api/workspaces/{uuid.uuid4()}/trails")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_get_trail_detail_returns_graph_and_mastery_summary(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_trail(db_engine)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["trail"]["id"] == str(trail_id)
    assert len(data["graph"]["nodes"]) == 2
    assert len(data["graph"]["edges"]) == 1
    assert data["mastery_summary"] == {
        "total": 2,
        "not_started": 2,
        "learning": 0,
        "needs_review": 0,
        "mastered": 0,
    }


async def test_get_missing_trail_detail_returns_404(api_client, db_engine):
    workspace_id, _, _ = await _seed_trail(db_engine)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_delete_trail_removes_graph_rows(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_trail(db_engine)

    resp = await api_client.delete(f"/api/workspaces/{workspace_id}/trails/{trail_id}")

    assert resp.status_code == 204
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        assert await session.get(Trail, trail_id) is None
        assert list(await session.scalars(select(ConceptNode))) == []
        assert list(await session.scalars(select(ConceptEdge))) == []


async def test_delete_missing_trail_returns_404(api_client, db_engine):
    workspace_id, _, _ = await _seed_trail(db_engine)

    resp = await api_client.delete(f"/api/workspaces/{workspace_id}/trails/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
