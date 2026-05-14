import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode  # noqa: F401
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail  # noqa: F401


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
