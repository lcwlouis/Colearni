import hashlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.source import ConceptSourceLink, SourceRecord, SourceRevision
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_client(db_engine):
    sessionmaker = _sessionmaker(db_engine)

    async def override_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_post_link_creates_concept_source_link_row(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    source_id = await _create_source(db_engine, workspace_id=workspace_id, title="Upload")

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/{source_id}/links",
        json={"concept_id": str(concept_id), "relation": "primary"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source_id"] == str(source_id)
    assert data["concept_id"] == str(concept_id)
    assert data["relation"] == "primary"
    async with _sessionmaker(db_engine)() as session:
        link = await session.get(ConceptSourceLink, uuid.UUID(data["id"]))
    assert link is not None
    assert link.source_id == source_id
    assert link.concept_id == concept_id


async def test_post_link_with_concept_in_different_workspace_returns_404(api_client, db_engine):
    workspace_id, _ = await _create_workspace_concept(db_engine, "One")
    _, other_concept_id = await _create_workspace_concept(db_engine, "Two")
    source_id = await _create_source(db_engine, workspace_id=workspace_id, title="Upload")

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/{source_id}/links",
        json={"concept_id": str(other_concept_id), "relation": "primary"},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_post_link_with_invalid_relation_returns_400(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    source_id = await _create_source(db_engine, workspace_id=workspace_id, title="Upload")

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/{source_id}/links",
        json={"concept_id": str(concept_id), "relation": "invalid"},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


async def test_duplicate_post_returns_409(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    source_id = await _create_source(db_engine, workspace_id=workspace_id, title="Upload")
    payload = {"concept_id": str(concept_id), "relation": "primary"}

    first = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/{source_id}/links",
        json=payload,
    )
    duplicate = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/{source_id}/links",
        json=payload,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == {
        "code": "conflict",
        "message": "link already exists",
        "details": {},
    }


async def test_duplicate_link_triple_is_rejected_by_database(db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    source_id = await _create_source(db_engine, workspace_id=workspace_id, title="Upload")

    async with _sessionmaker(db_engine)() as session:
        session.add_all(
            [
                ConceptSourceLink(source_id=source_id, concept_id=concept_id, relation="primary"),
                ConceptSourceLink(source_id=source_id, concept_id=concept_id, relation="primary"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_get_source_links_returns_all_links_for_source(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    concept_two_id = await _create_concept(db_engine, workspace_id=workspace_id, slug="second")
    source_id = await _create_source(db_engine, workspace_id=workspace_id, title="Upload")
    await _create_link(db_engine, source_id=source_id, concept_id=concept_id, relation="primary")
    await _create_link(
        db_engine,
        source_id=source_id,
        concept_id=concept_two_id,
        relation="reference",
    )

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/sources/{source_id}/links")

    assert resp.status_code == 200
    links = resp.json()["links"]
    assert {(link["concept_id"], link["relation"]) for link in links} == {
        (str(concept_id), "primary"),
        (str(concept_two_id), "reference"),
    }


async def test_get_source_links_for_unknown_source_returns_404(api_client, db_engine):
    workspace_id, _ = await _create_workspace_concept(db_engine)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/sources/{uuid.uuid4()}/links")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_get_concept_sources_returns_public_and_private_sources(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    public_source_id = await _create_source(
        db_engine,
        workspace_id=workspace_id,
        title="Public Research",
        origin="research_agent",
        access="public",
        url="https://example.com/research",
    )
    private_source_id = await _create_source(
        db_engine,
        workspace_id=workspace_id,
        title="Private Upload",
        origin="user_upload",
        access="private",
        revision_status="pending_parse",
    )
    await _create_link(
        db_engine, source_id=public_source_id, concept_id=concept_id, relation="reference"
    )
    await _create_link(
        db_engine, source_id=private_source_id, concept_id=concept_id, relation="primary"
    )

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/concepts/{concept_id}/sources")

    assert resp.status_code == 200
    sources = resp.json()["sources"]
    assert {source["title"] for source in sources} == {"Public Research", "Private Upload"}
    private = next(source for source in sources if source["title"] == "Private Upload")
    public = next(source for source in sources if source["title"] == "Public Research")
    assert private["origin"] == "user_upload"
    assert private["access"] == "private"
    assert private["ingestion_status"] == "pending_parse"
    assert public["origin"] == "research_agent"
    assert public["url"] == "https://example.com/research"
    assert public["ingestion_status"] is None


async def test_get_concept_sources_returns_latest_revision_status(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine)
    source_id = await _create_source(
        db_engine,
        workspace_id=workspace_id,
        title="Private Upload",
        origin="user_upload",
        access="private",
        revision_status="pending_parse",
    )
    await _create_revision(
        db_engine,
        workspace_id=workspace_id,
        source_id=source_id,
        revision_number=2,
        status="parsed",
    )
    await _create_link(db_engine, source_id=source_id, concept_id=concept_id, relation="primary")

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/concepts/{concept_id}/sources")

    assert resp.status_code == 200
    assert resp.json()["sources"][0]["ingestion_status"] == "parsed"


async def test_get_concept_sources_is_scoped_to_workspace(api_client, db_engine):
    workspace_id, concept_id = await _create_workspace_concept(db_engine, "One")
    other_workspace_id, _ = await _create_workspace_concept(db_engine, "Two")
    local_source_id = await _create_source(
        db_engine,
        workspace_id=workspace_id,
        title="Local Source",
    )
    other_source_id = await _create_source(
        db_engine,
        workspace_id=other_workspace_id,
        title="Other Workspace Source",
    )
    await _create_link(
        db_engine,
        source_id=local_source_id,
        concept_id=concept_id,
        relation="primary",
    )
    await _create_link(
        db_engine, source_id=other_source_id, concept_id=concept_id, relation="reference"
    )

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/concepts/{concept_id}/sources")

    assert resp.status_code == 200
    sources = resp.json()["sources"]
    assert [source["title"] for source in sources] == ["Local Source"]


async def _create_workspace_concept(
    db_engine,
    workspace_name: str = "Link Workspace",
) -> tuple[uuid.UUID, uuid.UUID]:
    async with _sessionmaker(db_engine)() as session:
        workspace = Workspace(name=workspace_name)
        session.add(workspace)
        await session.flush()
        trail = Trail(
            workspace_id=workspace.id,
            title=f"{workspace_name} Trail",
            topic="Math",
            goal="Learn",
            target_depth="understand",
        )
        session.add(trail)
        await session.flush()
        concept = ConceptNode(
            trail_id=trail.id,
            slug="vectors",
            title="Vectors",
            node_type="concept",
            concept_level="topic",
            difficulty="beginner",
            bloom_level="understand",
            mastery_check_labels=["explain vectors"],
            metadata_json={},
        )
        session.add(concept)
        await session.commit()
        return workspace.id, concept.id


async def _create_concept(db_engine, *, workspace_id: uuid.UUID, slug: str) -> uuid.UUID:
    async with _sessionmaker(db_engine)() as session:
        trail = await session.scalar(select(Trail).where(Trail.workspace_id == workspace_id))
        concept = ConceptNode(
            trail_id=trail.id,
            slug=slug,
            title=slug.title(),
            node_type="concept",
            concept_level="topic",
            difficulty="beginner",
            bloom_level="understand",
            mastery_check_labels=[f"check {slug}"],
            metadata_json={},
        )
        session.add(concept)
        await session.commit()
        return concept.id


async def _create_source(
    db_engine,
    *,
    workspace_id: uuid.UUID,
    title: str,
    origin: str = "user_upload",
    access: str = "private",
    url: str | None = None,
    revision_status: str | None = None,
) -> uuid.UUID:
    async with _sessionmaker(db_engine)() as session:
        source = SourceRecord(
            workspace_id=workspace_id,
            origin=origin,
            access=access,
            title=title,
            url=url,
            include_on_public_export=origin == "research_agent" and access == "public",
            metadata_json={},
        )
        session.add(source)
        await session.flush()
        if revision_status is not None:
            content = title.encode()
            digest = hashlib.sha256(content).hexdigest()
            session.add(
                SourceRevision(
                    workspace_id=workspace_id,
                    source_id=source.id,
                    revision_number=1,
                    object_key=f"workspaces/{workspace_id}/sources/{source.id}/revisions/1/{digest}.txt",
                    content_hash=f"sha256:{digest}",
                    content_type="text/plain",
                    file_size_bytes=len(content),
                    parser_name="none",
                    parser_version="upload-only-v1",
                    status=revision_status,
                    metadata_json={},
                )
            )
        await session.commit()
        return source.id


async def _create_revision(
    db_engine,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    revision_number: int,
    status: str,
) -> uuid.UUID:
    async with _sessionmaker(db_engine)() as session:
        content = f"{source_id}:{revision_number}".encode()
        digest = hashlib.sha256(content).hexdigest()
        revision = SourceRevision(
            workspace_id=workspace_id,
            source_id=source_id,
            revision_number=revision_number,
            object_key=(
                f"workspaces/{workspace_id}/sources/{source_id}/revisions/"
                f"{revision_number}/{digest}.txt"
            ),
            content_hash=f"sha256:{digest}",
            content_type="text/plain",
            file_size_bytes=len(content),
            parser_name="none",
            parser_version="upload-only-v1",
            status=status,
            metadata_json={},
        )
        session.add(revision)
        await session.commit()
        return revision.id


async def _create_link(
    db_engine,
    *,
    source_id: uuid.UUID,
    concept_id: uuid.UUID,
    relation: str,
) -> uuid.UUID:
    async with _sessionmaker(db_engine)() as session:
        link = ConceptSourceLink(source_id=source_id, concept_id=concept_id, relation=relation)
        session.add(link)
        await session.commit()
        return link.id
