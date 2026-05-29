import hashlib
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.conversation import Conversation, ConversationTurn
from backend.app.models.mastery import MasteryRecord, QuizAttempt, QuizDraft
from backend.app.models.source import ConceptSourceLink, SourceChunk, SourceRecord, SourceRevision
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


async def _create_workspace(db_engine, name: str = "Export Workspace") -> uuid.UUID:
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        workspace = Workspace(name=name)
        session.add(workspace)
        await session.commit()
        return workspace.id


async def _seed_trail(db_engine) -> tuple[uuid.UUID, uuid.UUID, dict[str, uuid.UUID]]:
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        workspace = Workspace(name="Export Workspace")
        session.add(workspace)
        await session.flush()
        trail = Trail(
            workspace_id=workspace.id,
            title="Linear Algebra",
            topic="Linear Algebra",
            goal="Understand vector spaces",
            target_depth="apply",
        )
        session.add(trail)
        await session.flush()
        nodes = {
            "linear-algebra": ConceptNode(
                trail_id=trail.id,
                slug="linear-algebra",
                title="Linear Algebra",
                node_type="concept",
                concept_level="umbrella",
                difficulty="beginner",
                bloom_level="understand",
                mastery_check_labels=["map_the_topic"],
                metadata_json={"raw_text": "CONCEPT SECRET"},
            ),
            "vectors": ConceptNode(
                trail_id=trail.id,
                slug="vectors",
                title="Vectors",
                node_type="concept",
                concept_level="topic",
                difficulty="beginner",
                bloom_level="understand",
                mastery_check_labels=["explain_vectors"],
                metadata_json={"private_notes": "HIDDEN CONCEPT NOTE"},
            ),
            "matrices": ConceptNode(
                trail_id=trail.id,
                slug="matrices",
                title="Matrices",
                node_type="concept",
                concept_level="topic",
                difficulty="beginner",
                bloom_level="apply",
                mastery_check_labels=["multiply_matrix_vector"],
                metadata_json={"learning_objectives": ["DO NOT EXPORT"]},
            ),
        }
        session.add_all(nodes.values())
        await session.flush()
        session.add_all(
            [
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["linear-algebra"].id,
                    target_node_id=nodes["vectors"].id,
                    relation_type="contains",
                ),
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["linear-algebra"].id,
                    target_node_id=nodes["matrices"].id,
                    relation_type="contains",
                ),
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=nodes["vectors"].id,
                    target_node_id=nodes["matrices"].id,
                    relation_type="prerequisite",
                ),
            ]
        )
        await session.commit()
        return workspace.id, trail.id, {slug: node.id for slug, node in nodes.items()}


async def _add_source(
    db_engine,
    workspace_id: uuid.UUID,
    *,
    origin: str = "research_agent",
    access: str = "public",
    title: str = "Source",
    url: str | None = "https://example.com/source",
    license_: str | None = "CC-BY",
    include_on_public_export: bool = False,
    metadata_json: dict | None = None,
) -> uuid.UUID:
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        source = SourceRecord(
            workspace_id=workspace_id,
            origin=origin,
            access=access,
            title=title,
            url=url,
            license=license_,
            include_on_public_export=include_on_public_export,
            metadata_json=metadata_json or {},
        )
        session.add(source)
        await session.commit()
        return source.id


async def _link_source(
    db_engine,
    concept_id: uuid.UUID,
    source_id: uuid.UUID,
    relation: str = "reference",
) -> None:
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        session.add(
            ConceptSourceLink(concept_id=concept_id, source_id=source_id, relation=relation)
        )
        await session.commit()


async def test_export_trail_pack_happy_path(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    source_id = await _add_source(
        db_engine,
        workspace_id,
        title="MIT OCW Linear Algebra",
        url="https://example.com/mit-ocw",
        include_on_public_export=True,
        metadata_json={"raw_text": "SOURCE SECRET"},
    )
    await _link_source(db_engine, concepts["vectors"], source_id)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pack"]["manifest"] == {
        "id": "linear-algebra",
        "title": "Linear Algebra",
        "topic": "Linear Algebra",
        "goal": "Understand vector spaces",
        "target_depth": "apply",
        "version": "1.0.0",
        "pack_type": "structure",
        "content_included": False,
        "hydration_supported": True,
    }
    assert data["pack"]["research_trace"] == {}
    assert data["pack"]["graph"]["nodes"][0]["difficulty"] == "beginner"
    assert data["pack"]["graph"]["nodes"][0]["bloom_level"] == "understand"
    assert data["pack"]["concepts"]["linear-algebra"]["children"] == ["matrices", "vectors"]
    assert data["pack"]["concepts"]["matrices"]["prerequisites"] == ["vectors"]
    assert data["pack"]["concepts"]["vectors"]["source_refs"] == [
        {"source_id": str(source_id), "relation": "reference"}
    ]
    assert data["pack"]["concepts"]["vectors"]["learning_objectives"] == []
    assert data["pack"]["concepts"]["vectors"]["hydration_required"] is True
    assert data["pack"]["sources"] == [
        {
            "id": str(source_id),
            "title": "MIT OCW Linear Algebra",
            "url": "https://example.com/mit-ocw",
            "origin": "research_agent",
            "access": "public",
            "license": "CC-BY",
            "include_on_public_export": True,
            "content_included": False,
        }
    ]
    assert data["report"] == {
        "included": {
            "concepts": 3,
            "edges": 3,
            "source_links": 1,
            "has_research_trace": False,
        },
        "excluded": {
            "uploaded_files": 0,
            "source_revisions": 0,
            "chunks": 0,
            "embeddings": 0,
            "private_notes": 0,
            "mastery_records": False,
        },
    }


async def test_export_excludes_user_upload_sources(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    source_id = await _add_source(
        db_engine,
        workspace_id,
        origin="user_upload",
        access="public",
        title="Uploaded Notes",
        url=None,
        include_on_public_export=True,
    )
    await _link_source(db_engine, concepts["vectors"], source_id)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pack"]["sources"] == []
    assert data["pack"]["concepts"]["vectors"]["source_refs"] == []
    assert data["report"]["included"]["source_links"] == 0
    assert data["report"]["excluded"]["uploaded_files"] == 1


async def test_export_excludes_uploaded_source_revisions(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    content = b"PRIVATE UPLOADED CONTENT"
    source_id = await _add_source(
        db_engine,
        workspace_id,
        origin="user_upload",
        access="private",
        title="Uploaded Notes",
        url=None,
        include_on_public_export=False,
    )
    await _link_source(db_engine, concepts["vectors"], source_id)

    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        session.add(
            revision := SourceRevision(
                workspace_id=workspace_id,
                source_id=source_id,
                revision_number=1,
                object_key=f"workspaces/{workspace_id}/sources/{source_id}/revisions/1/file.txt",
                content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
                content_type="text/plain",
                file_size_bytes=len(content),
                parser_name="none",
                parser_version="upload-only-v1",
                status="pending_parse",
                raw_text=content.decode(),
                metadata_json={"raw_text": content.decode()},
            )
        )
        await session.flush()
        session.add(
            SourceChunk(
                source_revision_id=revision.id,
                workspace_id=workspace_id,
                chunk_index=0,
                text="PRIVATE CHUNK CONTENT",
                char_start=0,
                char_end=len("PRIVATE CHUNK CONTENT"),
                line_start=1,
                line_end=1,
                section_heading=None,
                embedding=[0.1] * 1536,
            )
        )
        await session.commit()

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pack"]["sources"] == []
    assert "PRIVATE UPLOADED CONTENT" not in resp.text
    assert "PRIVATE CHUNK CONTENT" not in resp.text
    assert "source_revisions" not in json.dumps(data["pack"])
    export_json = json.dumps(data["pack"])
    assert "source_chunks" not in export_json
    assert "embedding" not in export_json
    assert data["report"]["excluded"]["uploaded_files"] == 1
    assert data["report"]["excluded"]["source_revisions"] == 1
    assert data["report"]["excluded"]["chunks"] == 1
    assert data["report"]["excluded"]["embeddings"] == 1


async def test_export_excludes_public_research_source_without_export_flag(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    source_id = await _add_source(
        db_engine,
        workspace_id,
        title="Public Research Source",
        include_on_public_export=False,
    )
    await _link_source(db_engine, concepts["vectors"], source_id)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pack"]["sources"] == []
    assert data["pack"]["concepts"]["vectors"]["source_refs"] == []
    assert data["report"]["included"]["source_links"] == 0
    assert data["report"]["excluded"]["uploaded_files"] == 0


async def test_export_excludes_non_public_and_non_research_sources(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    blocked_sources = [
        await _add_source(
            db_engine,
            workspace_id,
            access="private",
            title="Private Research Source",
            include_on_public_export=True,
        ),
        await _add_source(
            db_engine,
            workspace_id,
            access="restricted",
            title="Restricted Research Source",
            include_on_public_export=True,
        ),
        await _add_source(
            db_engine,
            workspace_id,
            access="unknown",
            title="Unknown Access Research Source",
            include_on_public_export=True,
        ),
        await _add_source(
            db_engine,
            workspace_id,
            origin="manual",
            access="public",
            title="Manual Public Source",
            include_on_public_export=True,
        ),
    ]
    for source_id in blocked_sources:
        await _link_source(db_engine, concepts["vectors"], source_id)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    assert resp.json()["pack"]["sources"] == []
    assert resp.json()["pack"]["concepts"]["vectors"]["source_refs"] == []


async def test_export_excludes_cross_workspace_sources(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    other_workspace_id = await _create_workspace(db_engine, name="Other Workspace")
    source_id = await _add_source(
        db_engine,
        other_workspace_id,
        title="Other Workspace Public Source",
        include_on_public_export=True,
    )
    await _link_source(db_engine, concepts["vectors"], source_id)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    assert resp.json()["pack"]["sources"] == []
    assert resp.json()["pack"]["concepts"]["vectors"]["source_refs"] == []


async def test_export_uses_whitelist_serialization(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    source_id = await _add_source(
        db_engine,
        workspace_id,
        title="Safe Public Source",
        include_on_public_export=True,
        metadata_json={"raw_text": "SOURCE SECRET", "embedding": [0.1, 0.2]},
    )
    await _link_source(db_engine, concepts["vectors"], source_id)

    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        session.add(MasteryRecord(
            workspace_id=workspace_id,
            concept_id=concepts["vectors"],
            status="mastered",
            bloom_level="understand",
            score=0.9,
        ))
        conversation = Conversation(
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concepts["vectors"],
        )
        session.add(conversation)
        await session.flush()
        session.add(ConversationTurn(
            conversation_id=conversation.id,
            role="assistant",
            kind="visible",
            content="CHAT HISTORY SECRET",
            mode="socratic",
            turn_index=0,
        ))
        session.add(QuizAttempt(
            concept_id=concepts["vectors"],
            quiz_type="practice",
            questions_json=[{"id": "q1", "prompt": "ATTEMPT SECRET"}],
            answers_json=[{"question_id": "q1", "answer": "secret"}],
            evaluator_feedback="ATTEMPT SECRET",
            passed=True,
            score=1.0,
        ))
        session.add(QuizDraft(
            concept_id=concepts["vectors"],
            quiz_type="practice",
            questions_json=[{"id": "q1", "prompt": "DRAFT SECRET"}],
        ))
        await session.commit()

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    pack_json = json.dumps(resp.json()["pack"])
    full_json = resp.text
    for forbidden in [
        "CONCEPT SECRET",
        "HIDDEN CONCEPT NOTE",
        "DO NOT EXPORT",
        "SOURCE SECRET",
        "CHAT HISTORY SECRET",
        "ATTEMPT SECRET",
        "DRAFT SECRET",
    ]:
        assert forbidden not in full_json
    for forbidden_key in [
        "metadata_json",
        '"mastery":',
        "quiz_attempts",
        "quiz_drafts",
        '"embedding":',
    ]:
        assert forbidden_key not in pack_json
    assert resp.json()["report"]["excluded"]["mastery_records"] is True


async def test_export_report_counts_safe_links_and_excluded_mastery(api_client, db_engine):
    workspace_id, trail_id, concepts = await _seed_trail(db_engine)
    source_id = await _add_source(
        db_engine,
        workspace_id,
        title="Reusable Public Source",
        include_on_public_export=True,
    )
    upload_id = await _add_source(
        db_engine,
        workspace_id,
        origin="user_upload",
        access="private",
        title="Private Upload",
    )
    await _link_source(db_engine, concepts["vectors"], source_id)
    await _link_source(db_engine, concepts["matrices"], source_id, relation="explains")
    await _link_source(db_engine, concepts["vectors"], upload_id)

    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        session.add(MasteryRecord(
            workspace_id=workspace_id,
            concept_id=concepts["matrices"],
            status="learning",
            bloom_level="apply",
            score=0.3,
        ))
        await session.commit()

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")

    assert resp.status_code == 200
    assert resp.json()["report"] == {
        "included": {
            "concepts": 3,
            "edges": 3,
            "source_links": 2,
            "has_research_trace": False,
        },
        "excluded": {
            "uploaded_files": 1,
            "source_revisions": 0,
            "chunks": 0,
            "embeddings": 0,
            "private_notes": 0,
            "mastery_records": True,
        },
    }


async def test_export_missing_trail_returns_not_found_envelope(api_client, db_engine):
    workspace_id, _, _ = await _seed_trail(db_engine)

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{uuid.uuid4()}/export")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_export_missing_workspace_returns_not_found_envelope(api_client):
    resp = await api_client.get(
        f"/api/workspaces/{uuid.uuid4()}/trails/{uuid.uuid4()}/export"
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_export_invalid_format_returns_error_envelope(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_trail(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/export?format=yaml"
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
