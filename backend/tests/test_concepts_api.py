import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
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
    assert data["mastery"] is None
    assert data["sources"] == []


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
