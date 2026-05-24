import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.research import TrailResearchTrace
from backend.app.models.source import ConceptSourceLink, SourceRecord
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


async def _create_workspace(db_engine, name: str = "Import Workspace") -> uuid.UUID:
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        workspace = Workspace(name=name)
        session.add(workspace)
        await session.commit()
        return workspace.id


async def _seed_exportable_trail(db_engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        workspace = Workspace(name="Source Workspace")
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
        vectors = ConceptNode(
            trail_id=trail.id,
            slug="vectors",
            title="Vectors",
            node_type="concept",
            concept_level="topic",
            difficulty="beginner",
            bloom_level="understand",
            mastery_check_labels=["explain_vectors"],
            metadata_json={"raw_text": "CONCEPT SECRET"},
        )
        matrices = ConceptNode(
            trail_id=trail.id,
            slug="matrices",
            title="Matrices",
            node_type="concept",
            concept_level="topic",
            difficulty="intermediate",
            bloom_level="apply",
            mastery_check_labels=["multiply_matrix_vector"],
            metadata_json={"private_notes": "HIDDEN NOTE"},
        )
        session.add_all([vectors, matrices])
        await session.flush()
        source = SourceRecord(
            workspace_id=workspace.id,
            origin="research_agent",
            access="public",
            title="MIT OCW Linear Algebra",
            url="https://example.com/mit-ocw",
            license="CC-BY",
            include_on_public_export=True,
            metadata_json={"raw_text": "SOURCE SECRET"},
        )
        session.add(source)
        await session.flush()
        session.add_all(
            [
                ConceptEdge(
                    trail_id=trail.id,
                    source_node_id=vectors.id,
                    target_node_id=matrices.id,
                    relation_type="prerequisite",
                ),
                ConceptSourceLink(concept_id=vectors.id, source_id=source.id, relation="reference"),
            ]
        )
        await session.commit()
        return workspace.id, trail.id, source.id


async def _export(api_client, workspace_id: uuid.UUID, trail_id: uuid.UUID) -> dict:
    resp = await api_client.get(f"/api/workspaces/{workspace_id}/trails/{trail_id}/export")
    assert resp.status_code == 200
    return resp.json()


async def test_import_export_wrapper_happy_path(api_client, db_engine):
    source_workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    exported = await _export(api_client, source_workspace_id, trail_id)
    target_workspace_id = await _create_workspace(db_engine, "Target Workspace")

    resp = await api_client.post(
        f"/api/workspaces/{target_workspace_id}/trail-packs/import",
        json=exported,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["trail"]["id"] != str(trail_id)
    assert data["trail"]["topic"] == "Linear Algebra"
    assert data["trail"]["goal"] == "Understand vector spaces"
    assert data["trail"]["target_depth"] == "apply"
    assert data["report"] == {
        "trail_id": data["trail"]["id"],
        "concepts_imported": 2,
        "edges_imported": 1,
        "sources_available": 1,
        "sources_missing": 0,
        "hydration_required": True,
        "warnings": [],
    }

    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        imported_nodes = list(
            await session.scalars(
                select(ConceptNode).where(ConceptNode.trail_id == uuid.UUID(data["trail"]["id"]))
            )
        )
        imported_sources = list(
            await session.scalars(
                select(SourceRecord).where(SourceRecord.workspace_id == target_workspace_id)
            )
        )
        imported_links = list(
            await session.scalars(
                select(ConceptSourceLink).where(
                    ConceptSourceLink.concept_id.in_([node.id for node in imported_nodes])
                )
            )
        )

    assert {node.slug for node in imported_nodes} == {"vectors", "matrices"}
    assert {node.difficulty for node in imported_nodes} == {"beginner", "intermediate"}
    assert {node.bloom_level for node in imported_nodes} == {"understand", "apply"}
    assert len(imported_sources) == 1
    assert imported_sources[0].id != uuid.UUID(exported["pack"]["sources"][0]["id"])
    assert imported_sources[0].metadata_json == {
        "imported_pack_source_id": exported["pack"]["sources"][0]["id"]
    }
    assert len(imported_links) == 1


async def test_round_trip_across_workspaces_avoids_id_collisions(api_client, db_engine):
    source_workspace_id, trail_id, source_id = await _seed_exportable_trail(db_engine)
    exported = await _export(api_client, source_workspace_id, trail_id)
    target_workspace_id = await _create_workspace(db_engine, "Other Workspace")

    resp = await api_client.post(
        f"/api/workspaces/{target_workspace_id}/trail-packs/import",
        json=exported,
    )

    assert resp.status_code == 201
    imported_trail_id = uuid.UUID(resp.json()["trail"]["id"])
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        imported_source = (
            await session.scalars(
                select(SourceRecord).where(SourceRecord.workspace_id == target_workspace_id)
            )
        ).one()
        imported_nodes = list(
            await session.scalars(
                select(ConceptNode).where(ConceptNode.trail_id == imported_trail_id)
            )
        )

    assert imported_source.id != source_id
    assert imported_source.workspace_id == target_workspace_id
    assert all(node.trail_id == imported_trail_id for node in imported_nodes)


async def test_import_accepts_raw_pack_payload(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    exported = await _export(api_client, workspace_id, trail_id)
    target_workspace_id = await _create_workspace(db_engine, "Raw Pack Target")

    resp = await api_client.post(
        f"/api/workspaces/{target_workspace_id}/trail-packs/import",
        json=exported["pack"],
    )

    assert resp.status_code == 201
    assert resp.json()["report"]["concepts_imported"] == 2


async def test_import_rejects_malformed_json(api_client, db_engine):
    workspace_id = await _create_workspace(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        content="{not-json",
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"


async def test_import_rejects_duplicate_node_ids(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack["graph"]["nodes"].append(dict(pack["graph"]["nodes"][0]))

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    assert "Duplicate" in resp.json()["error"]["message"]


async def test_import_rejects_unknown_edge_refs(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack["graph"]["edges"][0]["source"] = "missing"

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    assert "unknown source" in resp.json()["error"]["message"]


async def test_import_rejects_unknown_concept_level(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack["graph"]["nodes"][0]["concept_level"] = "mystery"

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    assert "concept_level" in resp.json()["error"]["message"]


async def test_import_rejects_missing_concept_payload_for_graph_node(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack["concepts"].pop("matrices")

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    assert "Missing concept payloads" in resp.json()["error"]["message"]
    assert "matrices" in resp.json()["error"]["message"]


@pytest.mark.parametrize("unsafe_field", ["chunks", "embeddings", "private_notes", "mastery"])
async def test_import_rejects_unsafe_fields(api_client, db_engine, unsafe_field):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack[unsafe_field] = []

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    assert "Unsafe Trail Pack field" in resp.json()["error"]["message"]


@pytest.mark.parametrize(
    "source_patch",
    [
        {"origin": "user_upload", "access": "public"},
        {"origin": "research_agent", "access": "private"},
        {"origin": "manual", "access": "public"},
    ],
)
async def test_import_rejects_unsafe_sources(api_client, db_engine, source_patch):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack["sources"][0].update(source_patch)

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 400
    assert "Unsafe source rejected" in resp.json()["error"]["message"]


async def test_import_reports_missing_sources(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    missing_id = pack["sources"][0]["id"]
    pack["sources"] = []

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 201
    assert resp.json()["report"]["sources_available"] == 0
    assert resp.json()["report"]["sources_missing"] == 1
    assert missing_id in resp.json()["report"]["warnings"][0]


async def test_import_older_pack_defaults_missing_round_trip_fields(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    for field in ["topic", "goal", "target_depth"]:
        pack["manifest"].pop(field)
    for node in pack["graph"]["nodes"]:
        node.pop("difficulty")
        node.pop("bloom_level")

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["trail"]["topic"] == "Linear Algebra"
    assert data["trail"]["goal"] == "Imported from Trail Pack"
    assert data["trail"]["target_depth"] == "understand"
    assert {node["difficulty"] for node in data["graph"]["nodes"]} == {"beginner"}
    assert {node["bloom_level"] for node in data["graph"]["nodes"]} == {"understand"}
    assert len(data["report"]["warnings"]) == 5


async def test_reimport_same_pack_creates_separate_trails(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    exported = await _export(api_client, workspace_id, trail_id)

    first = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=exported,
    )
    second = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=exported,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["trail"]["id"] != second.json()["trail"]["id"]


async def test_import_preserves_research_trace_and_get_research(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    pack = (await _export(api_client, workspace_id, trail_id))["pack"]
    pack["research_trace"] = {
        "topic": "Vectors",
        "generated_by": "external_research_agent",
        "queries": ["vectors beginner explanation"],
        "selected_public_sources": [
            {
                "source_id": pack["sources"][0]["id"],
                "reason": "clear introductory explanation",
            }
        ],
        "excluded_sources": [{"title": "Private PDF", "reason": "private_upload"}],
    }

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=pack,
    )
    research = await api_client.get(
        f"/api/workspaces/{workspace_id}/trails/{resp.json()['trail']['id']}/research"
    )

    assert resp.status_code == 201
    assert research.status_code == 200
    assert research.json()["trace"]["queries"] == ["vectors beginner explanation"]
    assert research.json()["trace"]["selected_public_sources"][0]["reason"] == (
        "clear introductory explanation"
    )
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        stored = list(await session.scalars(select(TrailResearchTrace)))
    assert len(stored) == 1


async def test_hydration_placeholders_stay_private_and_export_safe(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    imported = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=await _export(api_client, workspace_id, trail_id),
    )
    imported_trail_id = uuid.UUID(imported.json()["trail"]["id"])

    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        imported_sources = list(
            await session.scalars(
                select(SourceRecord).where(SourceRecord.workspace_id == workspace_id)
            )
        )
        imported_source = next(
            source
            for source in imported_sources
            if source.metadata_json.get("imported_pack_source_id")
        )
        imported_concept = (
            await session.scalars(
                select(ConceptNode).where(ConceptNode.trail_id == imported_trail_id)
            )
        ).first()

    hydration = await api_client.post(
        f"/api/workspaces/{workspace_id}/trails/{imported_trail_id}/hydrate",
        json={"concept_id": str(imported_concept.id), "source_ids": [str(imported_source.id)]},
    )
    exported = await _export(api_client, workspace_id, imported_trail_id)

    assert hydration.status_code == 200
    assert hydration.json()["private_records_created"] == 1
    assert "Hydration placeholder" not in str(exported["pack"])
    assert len(exported["pack"]["sources"]) == 1
    async with sessionmaker() as session:
        private_sources = list(
            await session.scalars(
                select(SourceRecord).where(
                    SourceRecord.workspace_id == workspace_id,
                    SourceRecord.access == "private",
                )
            )
        )
    assert len(private_sources) == 1
    assert private_sources[0].include_on_public_export is False


async def test_hydration_skips_public_source_from_other_trail(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        target_concept = (
            await session.scalars(select(ConceptNode).where(ConceptNode.trail_id == trail_id))
        ).first()
        other_trail = Trail(
            workspace_id=workspace_id,
            title="Other Trail",
            topic="Other Topic",
            goal="Learn something else",
            target_depth="understand",
        )
        session.add(other_trail)
        await session.flush()
        other_concept = ConceptNode(
            trail_id=other_trail.id,
            slug="other-concept",
            title="Other Concept",
            node_type="concept",
            concept_level="topic",
            difficulty="beginner",
            bloom_level="understand",
            mastery_check_labels=[],
            metadata_json={},
        )
        other_source = SourceRecord(
            workspace_id=workspace_id,
            origin="research_agent",
            access="public",
            title="Other Trail Public Source",
            url="https://example.com/other",
            license="CC-BY",
            include_on_public_export=True,
            metadata_json={},
        )
        session.add_all([other_concept, other_source])
        await session.flush()
        session.add(
            ConceptSourceLink(
                concept_id=other_concept.id,
                source_id=other_source.id,
                relation="reference",
            )
        )
        await session.commit()
        target_concept_id = target_concept.id
        other_source_id = other_source.id

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/hydrate",
        json={"concept_id": str(target_concept_id), "source_ids": [str(other_source_id)]},
    )

    assert resp.status_code == 200
    assert resp.json()["private_records_created"] == 0
    assert resp.json()["skipped_sources"] == [
        {"source_id": str(other_source_id), "reason": "source_not_in_trail"}
    ]


async def test_hydration_records_source_and_model_knowledge_intent(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)
    imported = await api_client.post(
        f"/api/workspaces/{workspace_id}/trail-packs/import",
        json=await _export(api_client, workspace_id, trail_id),
    )
    imported_trail_id = uuid.UUID(imported.json()["trail"]["id"])

    sessionmaker = _sessionmaker(db_engine)
    async with sessionmaker() as session:
        imported_source = next(
            source
            for source in await session.scalars(
                select(SourceRecord).where(SourceRecord.workspace_id == workspace_id)
            )
            if source.metadata_json.get("imported_pack_source_id")
        )
        imported_concept = (
            await session.scalars(
                select(ConceptNode).where(ConceptNode.trail_id == imported_trail_id)
            )
        ).first()

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trails/{imported_trail_id}/hydrate",
        json={
            "concept_id": str(imported_concept.id),
            "source_ids": [str(imported_source.id)],
            "use_model_knowledge": True,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["private_records_created"] == 2
    async with sessionmaker() as session:
        private_sources = list(
            await session.scalars(
                select(SourceRecord).where(
                    SourceRecord.workspace_id == workspace_id,
                    SourceRecord.access == "private",
                )
            )
        )
    assert len(private_sources) == 2
    assert {source.include_on_public_export for source in private_sources} == {False}
    assert any(source.metadata_json.get("original_source_id") for source in private_sources)
    assert any(
        source.metadata_json.get("use_model_knowledge")
        and not source.metadata_json.get("original_source_id")
        for source in private_sources
    )


async def test_import_missing_workspace_returns_error_envelope(api_client):
    resp = await api_client.post(
        f"/api/workspaces/{uuid.uuid4()}/trail-packs/import",
        json={},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_hydration_missing_concept_returns_error_envelope(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/hydrate",
        json={"concept_id": str(uuid.uuid4()), "use_model_knowledge": True},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_hydration_empty_request_returns_invalid_input_envelope(api_client, db_engine):
    workspace_id, trail_id, _ = await _seed_exportable_trail(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/trails/{trail_id}/hydrate",
        json={},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
