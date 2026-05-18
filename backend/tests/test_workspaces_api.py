import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode  # noqa: F401
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail  # noqa: F401
from backend.app.models.workspace import Workspace
from backend.app.services.workspaces import DEFAULT_WORKSPACE_NAME, ensure_default_workspace


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


@pytest.fixture
async def db_session(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


# ── ensure_default_workspace service tests ────────────────────────────────────


async def test_ensure_default_workspace_creates_workspace_when_none_exists(db_session):
    workspace = await ensure_default_workspace(db_session)

    assert workspace.id is not None
    assert workspace.name == DEFAULT_WORKSPACE_NAME


async def test_ensure_default_workspace_is_idempotent(db_session):
    first = await ensure_default_workspace(db_session)
    second = await ensure_default_workspace(db_session)

    assert first.id == second.id


async def test_ensure_default_workspace_does_not_create_duplicate(db_session):
    await ensure_default_workspace(db_session)
    await ensure_default_workspace(db_session)

    count = await db_session.scalar(select(func.count()).select_from(Workspace))
    assert count == 1


# ── HTTP API tests ────────────────────────────────────────────────────────────


async def test_create_workspace_returns_201(api_client):
    resp = await api_client.post("/api/workspaces", json={"name": "My Workspace"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Workspace"
    assert data["id"]
    assert data["created_at"]


async def test_list_workspaces_returns_created_rows(api_client):
    await api_client.post("/api/workspaces", json={"name": "First"})
    await api_client.post("/api/workspaces", json={"name": "Second"})

    resp = await api_client.get("/api/workspaces")

    assert resp.status_code == 200
    assert [workspace["name"] for workspace in resp.json()["workspaces"]] == [
        "First",
        "Second",
    ]


async def test_get_workspace_returns_row(api_client):
    created = await api_client.post("/api/workspaces", json={"name": "Focused"})
    workspace_id = created.json()["id"]

    resp = await api_client.get(f"/api/workspaces/{workspace_id}")

    assert resp.status_code == 200
    assert resp.json()["id"] == workspace_id
    assert resp.json()["name"] == "Focused"


async def test_get_missing_workspace_returns_error_envelope(api_client):
    resp = await api_client.get(f"/api/workspaces/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
