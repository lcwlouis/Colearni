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


def _minimal_graph_json(topic: str = "Math") -> str:
    """Valid 10-node, 9-edge concept graph for use in tests."""
    subtopics = [
        ("arithmetic", "Arithmetic"),
        ("algebra", "Algebra"),
        ("geometry", "Geometry"),
        ("statistics", "Statistics"),
        ("calculus", "Calculus"),
        ("number-theory", "Number Theory"),
        ("logic", "Logic"),
        ("set-theory", "Set Theory"),
        ("probability", "Probability"),
    ]
    nodes = [
        {
            "slug": "math-root",
            "title": topic,
            "node_type": "concept",
            "concept_level": "umbrella",
            "difficulty": "beginner",
            "bloom_level": "understand",
            "mastery_check_labels": [],
            "metadata_json": {},
        }
    ] + [
        {
            "slug": slug,
            "title": title,
            "node_type": "concept",
            "concept_level": "topic",
            "difficulty": "beginner",
            "bloom_level": "remember",
            "mastery_check_labels": [],
            "metadata_json": {},
        }
        for slug, title in subtopics
    ]
    edges = [
        {"source_slug": "math-root", "target_slug": slug, "relation_type": "contains"}
        for slug, _ in subtopics
    ]
    return json.dumps({"nodes": nodes, "edges": edges})


class FakeGenerator:
    def __init__(
        self,
        json_str: str,
        repair_json_str: str | None = None,
        *,
        raise_on_generate: bool = False,
    ):
        self._json = json_str
        self._repair = repair_json_str
        self._raise_on_generate = raise_on_generate
        self.repair_called = False

    async def generate(self, topic: str, goal: str, target_depth: str) -> str:
        if self._raise_on_generate:
            raise RuntimeError("Provider connection failed")
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
    assert data["trail"]["node_count"] == 10
    assert data["trail"]["edge_count"] == 9
    assert len(data["graph"]["nodes"]) == 10
    assert len(data["graph"]["edges"]) == 9


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
    assert resp.json()["error"]["code"] == "not_found"


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
        assert resp.json()["error"]["code"] == "llm_error"
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


async def test_generate_raises_returns_500_llm_error(db_engine):
    """If generator.generate() raises, route returns 500 with error.code == 'llm_error'."""
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    async with async_session() as session:
        ws = Workspace(name="Raising WS")
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        ws_id = ws.id

    raising_gen = FakeGenerator(_minimal_graph_json(), raise_on_generate=True)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_graph_generator] = lambda: raising_gen

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/workspaces/{ws_id}/trails/generate",
                json={"topic": "Math", "goal": "Learn", "target_depth": "understand"},
            )
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "llm_error"
    finally:
        app.dependency_overrides.clear()
