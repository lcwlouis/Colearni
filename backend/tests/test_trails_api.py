"""API-level integration tests for POST /api/workspaces/{workspace_id}/trails/generate."""

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.trails import get_graph_generator
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode  # noqa: F401
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail  # noqa: F401
from backend.app.models.workspace import Workspace


def _minimal_graph_json() -> str:
    return json.dumps(
        {
            "nodes": [
                {
                    "slug": "math-root",
                    "title": "Mathematics",
                    "node_type": "concept",
                    "concept_level": "umbrella",
                    "difficulty": "beginner",
                    "bloom_level": "understand",
                    "mastery_check_labels": [],
                    "metadata_json": {},
                },
                {
                    "slug": "addition",
                    "title": "Addition",
                    "node_type": "concept",
                    "concept_level": "topic",
                    "difficulty": "beginner",
                    "bloom_level": "remember",
                    "mastery_check_labels": [],
                    "metadata_json": {},
                },
                {
                    "slug": "subtraction",
                    "title": "Subtraction",
                    "node_type": "concept",
                    "concept_level": "topic",
                    "difficulty": "beginner",
                    "bloom_level": "remember",
                    "mastery_check_labels": [],
                    "metadata_json": {},
                },
            ],
            "edges": [
                {"source_slug": "math-root", "target_slug": "addition", "relation_type": "contains"},  # noqa: E501
                {"source_slug": "math-root", "target_slug": "subtraction", "relation_type": "contains"},  # noqa: E501
            ],
        }
    )


class FakeGenerator:
    def __init__(self, json_str: str, repair_json_str: str | None = None):
        self._json = json_str
        self._repair = repair_json_str
        self.repair_called = False

    async def generate(self, topic: str, goal: str, target_depth: str) -> str:
        return self._json

    async def repair(self, raw_json: str, error: str) -> str:
        self.repair_called = True
        return self._repair if self._repair is not None else self._json


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_client(db_engine):
    """ASGI client with in-memory SQLite DB and a fake graph generator."""
    engine = db_engine
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    fake_gen = FakeGenerator(_minimal_graph_json())

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_graph_generator] = lambda: fake_gen

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, fake_gen, engine

    app.dependency_overrides.clear()


@pytest.fixture
async def workspace_id(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        ws = Workspace(name="Test Workspace")
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        return ws.id


async def test_create_trail_returns_nodes_and_edges(api_client, workspace_id):
    ac, _, _ = api_client
    resp = await ac.post(
        f"/api/workspaces/{workspace_id}/trails/generate",
        json={"topic": "Math", "goal": "Learn basics", "target_depth": "understand"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["trail"]["topic"] == "Math"
    assert data["trail"]["node_count"] == 3
    assert data["trail"]["edge_count"] == 2
    assert len(data["graph"]["nodes"]) == 3
    assert len(data["graph"]["edges"]) == 2


async def test_workspace_id_in_body_rejected(api_client, workspace_id):
    """workspace_id must come from URL path only — body must not accept it."""
    ac, _, _ = api_client
    resp = await ac.post(
        f"/api/workspaces/{workspace_id}/trails/generate",
        json={
            "topic": "Math",
            "goal": "Learn",
            "target_depth": "understand",
            "workspace_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422


async def test_invalid_target_depth_rejected(api_client, workspace_id):
    ac, _, _ = api_client
    resp = await ac.post(
        f"/api/workspaces/{workspace_id}/trails/generate",
        json={"topic": "Math", "goal": "Learn", "target_depth": "not-a-bloom-level"},
    )
    assert resp.status_code == 422


async def test_missing_workspace_returns_404(api_client):
    ac, _, _ = api_client
    resp = await ac.post(
        f"/api/workspaces/{uuid.uuid4()}/trails/generate",
        json={"topic": "Math", "goal": "Learn", "target_depth": "understand"},
    )
    assert resp.status_code == 404


async def test_llm_error_returns_500(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    # Insert workspace first
    async with async_session() as session:
        ws = Workspace(name="Error WS")
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        ws_id = ws.id

    bad_gen = FakeGenerator(json_str="bad json", repair_json_str="also bad")
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_graph_generator] = lambda: bad_gen

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/workspaces/{ws_id}/trails/generate",
                json={"topic": "Math", "goal": "Learn", "target_depth": "understand"},
            )
        assert resp.status_code == 500
        assert resp.json()["detail"]["code"] == "llm_error"
    finally:
        app.dependency_overrides.clear()


async def test_repair_triggered_on_first_bad_response(api_client, workspace_id):
    """When generate() returns bad JSON, repair() is called and used."""
    ac, fake_gen, engine = api_client
    # Override the generator with one that fails first, then repairs
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    repairing_gen = FakeGenerator(
        json_str="not json",
        repair_json_str=_minimal_graph_json(),
    )
    app.dependency_overrides[get_graph_generator] = lambda: repairing_gen

    resp = await ac.post(
        f"/api/workspaces/{workspace_id}/trails/generate",
        json={"topic": "Math", "goal": "Learn", "target_depth": "understand"},
    )
    assert resp.status_code == 201
    assert repairing_gen.repair_called
