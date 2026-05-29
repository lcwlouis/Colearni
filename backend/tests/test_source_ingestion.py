import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.source import SourceChunk, SourceRecord, SourceRevision
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.parser import CanonicalDocument, DocumentElement
from backend.app.services.source_ingestion import SourceUploadError, upload_private_source
from backend.app.settings import settings


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _disable_embedding_by_default():
    """Prevent live embedding API calls in tests that do not mock the client.

    Tests that need embedding behaviour must set settings.embedding_provider
    themselves (and restore it on teardown) — the two existing tests already do
    this via try/finally. Every other test in this module gets "disabled" so
    that no real network calls are made and no dimension-mismatch errors occur
    from a live provider configured in .env.
    """
    original = settings.embedding_provider
    settings.embedding_provider = "disabled"
    yield
    settings.embedding_provider = original


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_client(db_engine, tmp_path):
    sessionmaker = _sessionmaker(db_engine)
    original_root = settings.source_storage_root
    original_embedding_provider = settings.embedding_provider
    settings.source_storage_root = str(tmp_path / "source-storage")
    settings.embedding_provider = "disabled"

    async def override_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    settings.source_storage_root = original_root
    settings.embedding_provider = original_embedding_provider


async def _create_workspace(db_engine, name: str = "Ingestion Workspace") -> uuid.UUID:
    async with _sessionmaker(db_engine)() as session:
        workspace = Workspace(name=name)
        session.add(workspace)
        await session.commit()
        return workspace.id


async def test_upload_creates_private_source_record(api_client, db_engine):
    workspace_id = await _create_workspace(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/upload",
        files={"file": ("notes.txt", b"private notes", "text/plain")},
        data={"title": "Week 1 Notes"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["origin"] == "user_upload"
    assert data["access"] == "private"
    assert data["title"] == "Week 1 Notes"
    assert data["url"] is None
    assert data["include_on_public_export"] is False
    assert data["metadata_json"]["ingestion_status"] == "parsed"

    async with _sessionmaker(db_engine)() as session:
        source = await session.get(SourceRecord, uuid.UUID(data["id"]))
    assert source is not None
    assert source.workspace_id == workspace_id


async def test_upload_persists_revision_provenance_and_private_object(
    api_client, db_engine, tmp_path
):
    workspace_id = await _create_workspace(db_engine)
    content = b"source bytes"

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/upload",
        files={"file": ("slides.txt", content, "text/plain")},
    )

    assert resp.status_code == 201
    expected_hash = "sha256:" + hashlib.sha256(content).hexdigest()
    response_revision = resp.json()["revision"]
    assert response_revision["revision_number"] == 1
    assert "content_hash" not in response_revision
    assert "object_key" not in response_revision
    assert response_revision["parser_name"] == "plaintext"
    assert response_revision["parser_version"] == "parser-pipeline-v1"
    assert response_revision["status"] == "parsed"
    assert response_revision["file_size_bytes"] == len(content)
    assert response_revision["metadata_json"]["parsing"] == "parsed"

    async with _sessionmaker(db_engine)() as session:
        persisted_revision = await session.get(SourceRevision, uuid.UUID(response_revision["id"]))
    assert persisted_revision.content_hash == expected_hash
    assert persisted_revision.object_key.startswith(f"workspaces/{workspace_id}/sources/")
    assert persisted_revision.raw_text == content.decode()
    object_path = tmp_path / "source-storage" / persisted_revision.object_key
    assert object_path.read_bytes() == content


async def test_upload_private_source_with_pdf_sets_parsed_and_raw_text(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    parsed_doc = CanonicalDocument(
        elements=[DocumentElement(type="paragraph", text="Parsed PDF text")],
        parser_name="pdfplumber",
    )

    async with _sessionmaker(db_engine)() as session:
        with patch("backend.app.services.source_ingestion.parse_source", return_value=parsed_doc):
            response = await upload_private_source(
                session,
                workspace_id=workspace_id,
                filename="notes.pdf",
                content=b"%PDF fake",
                content_type="application/pdf",
                storage_root=str(tmp_path / "source-storage"),
            )

    revision_id = response.revision.id
    assert response.revision.status == "parsed"
    assert response.revision.parser_name == "pdfplumber"
    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, revision_id)
        chunks = list(await session.scalars(select(SourceChunk)))
    assert revision.raw_text == "Parsed PDF text"
    assert len(chunks) == 1


async def test_upload_private_source_with_unsupported_type_sets_failed(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)

    async with _sessionmaker(db_engine)() as session:
        response = await upload_private_source(
            session,
            workspace_id=workspace_id,
            filename="blob.bin",
            content=b"binary",
            content_type="application/octet-stream",
            storage_root=str(tmp_path / "source-storage"),
        )

    assert response.revision.status == "failed"
    assert "Unsupported source format" in response.revision.error_message


async def test_upload_private_source_with_trail_id_calls_auto_linker(db_engine, tmp_path):
    workspace_id, trail_id = await _create_workspace_trail(db_engine)
    parsed_doc = CanonicalDocument(
        elements=[DocumentElement(type="paragraph", text="Vectors are useful")],
        parser_name="plaintext",
    )

    async with _sessionmaker(db_engine)() as session:
        with (
            patch("backend.app.services.source_ingestion.parse_source", return_value=parsed_doc),
            patch(
                "backend.app.services.source_ingestion.auto_link_source_to_trail",
                new=AsyncMock(),
            ) as auto_link,
        ):
            response = await upload_private_source(
                session,
                workspace_id=workspace_id,
                filename="notes.txt",
                content=b"text",
                content_type="text/plain",
                trail_id=trail_id,
                storage_root=str(tmp_path / "source-storage"),
            )

    assert auto_link.await_count == 1
    _, revision_id, called_trail_id, called_workspace_id = auto_link.await_args.args
    assert revision_id == response.revision.id
    assert called_trail_id == trail_id
    assert called_workspace_id == workspace_id


async def test_upload_private_source_calls_embedding_when_provider_configured(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    original_provider = settings.embedding_provider
    settings.embedding_provider = "openai"
    fake_client = MagicMock()
    fake_client.embed = AsyncMock(return_value=[[0.1] * settings.embedding_dim])
    try:
        async with _sessionmaker(db_engine)() as session:
            with patch(
                "backend.app.services.source_ingestion.EmbeddingClient.from_settings",
                return_value=fake_client,
            ):
                await upload_private_source(
                    session,
                    workspace_id=workspace_id,
                    filename="notes.txt",
                    content=b"embed me",
                    content_type="text/plain",
                    storage_root=str(tmp_path / "source-storage"),
                )
    finally:
        settings.embedding_provider = original_provider

    fake_client.embed.assert_awaited_once_with(["embed me"])


async def test_upload_private_source_survives_embedding_failure(db_engine, tmp_path):
    """An embedding/provider failure must not abort the upload or orphan the file."""
    workspace_id = await _create_workspace(db_engine)
    original_provider = settings.embedding_provider
    settings.embedding_provider = "openai"
    fake_client = MagicMock()
    fake_client.embed = AsyncMock(side_effect=RuntimeError("provider exploded"))
    try:
        async with _sessionmaker(db_engine)() as session:
            with patch(
                "backend.app.services.source_ingestion.EmbeddingClient.from_settings",
                return_value=fake_client,
            ):
                response = await upload_private_source(
                    session,
                    workspace_id=workspace_id,
                    filename="notes.txt",
                    content=b"embed me",
                    content_type="text/plain",
                    storage_root=str(tmp_path / "source-storage"),
                )
    finally:
        settings.embedding_provider = original_provider

    # Source is parsed and stored; embeddings are simply absent (ILIKE fallback).
    assert response.revision.status == "parsed"
    assert response.revision.metadata_json["chunks_created"] >= 1
    assert response.revision.metadata_json["embeddings_created"] == 0


async def test_upload_private_source_skips_embedding_when_provider_disabled(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    original_provider = settings.embedding_provider
    settings.embedding_provider = "disabled"
    try:
        async with _sessionmaker(db_engine)() as session:
            with patch(
                "backend.app.services.source_ingestion.EmbeddingClient.from_settings"
            ) as factory:
                await upload_private_source(
                    session,
                    workspace_id=workspace_id,
                    filename="notes.txt",
                    content=b"do not embed",
                    content_type="text/plain",
                    storage_root=str(tmp_path / "source-storage"),
                )
    finally:
        settings.embedding_provider = original_provider

    factory.assert_not_called()


async def test_source_revision_append_only_keys_are_unique(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    async with _sessionmaker(db_engine)() as session:
        created = await upload_private_source(
            session,
            workspace_id=workspace_id,
            filename="notes.txt",
            content=b"first revision",
            content_type="text/plain",
            storage_root=str(tmp_path / "source-storage"),
        )
        original = await session.get(SourceRevision, created.revision.id)
        original_hash = original.content_hash
        session.add(
            SourceRevision(
                workspace_id=workspace_id,
                source_id=created.id,
                revision_number=1,
                object_key="workspaces/duplicate/revision.txt",
                content_hash="sha256:" + hashlib.sha256(b"duplicate").hexdigest(),
                content_type="text/plain",
                file_size_bytes=len(b"duplicate"),
                parser_name="none",
                parser_version="upload-only-v1",
                status="pending_parse",
                metadata_json={"original_filename": "notes.txt"},
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        assert revision.content_hash == original_hash
        assert revision.status == "parsed"


async def test_creating_new_revision_does_not_mutate_prior_revision(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    async with _sessionmaker(db_engine)() as session:
        created = await upload_private_source(
            session,
            workspace_id=workspace_id,
            filename="notes.txt",
            content=b"first revision",
            content_type="text/plain",
            storage_root=str(tmp_path / "source-storage"),
        )
        first_revision_id = created.revision.id
        source_id = created.id
        first_revision = await session.get(SourceRevision, first_revision_id)
        first_revision_hash = first_revision.content_hash
        second_content = b"second revision"
        session.add(
            SourceRevision(
                workspace_id=workspace_id,
                source_id=source_id,
                revision_number=2,
                object_key=f"workspaces/{workspace_id}/sources/{source_id}/revisions/2/file.txt",
                content_hash="sha256:" + hashlib.sha256(second_content).hexdigest(),
                content_type="text/plain",
                file_size_bytes=len(second_content),
                parser_name="none",
                parser_version="upload-only-v1",
                status="pending_parse",
                metadata_json={"original_filename": "notes.txt"},
            )
        )
        await session.commit()

    async with _sessionmaker(db_engine)() as session:
        revisions = list(
            await session.scalars(
                select(SourceRevision)
                .where(SourceRevision.source_id == source_id)
                .order_by(SourceRevision.revision_number)
            )
        )
    assert [revision.revision_number for revision in revisions] == [1, 2]
    assert revisions[0].id == first_revision_id
    assert revisions[0].content_hash == first_revision_hash
    assert revisions[0].file_size_bytes == len(b"first revision")


async def test_source_revision_status_update_does_not_raise(db_engine, tmp_path):
    created = await _upload_for_revision_guard(db_engine, tmp_path)
    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        revision.status = "parsed"
        await session.commit()

    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        assert revision.status == "parsed"


async def test_source_revision_error_message_update_does_not_raise(db_engine, tmp_path):
    created = await _upload_for_revision_guard(db_engine, tmp_path)
    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        revision.status = "failed"
        revision.error_message = "Parser failed"
        await session.commit()

    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        assert revision.error_message == "Parser failed"


async def test_source_revision_object_key_update_raises(db_engine, tmp_path):
    created = await _upload_for_revision_guard(db_engine, tmp_path)
    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        revision.object_key = "workspaces/changed/object.txt"
        with pytest.raises(ValueError, match="object_key"):
            await session.commit()


async def test_source_revision_content_hash_update_raises(db_engine, tmp_path):
    created = await _upload_for_revision_guard(db_engine, tmp_path)
    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        revision.content_hash = "sha256:" + hashlib.sha256(b"changed").hexdigest()
        with pytest.raises(ValueError, match="content_hash"):
            await session.commit()


async def test_source_revision_revision_number_update_raises(db_engine, tmp_path):
    created = await _upload_for_revision_guard(db_engine, tmp_path)
    async with _sessionmaker(db_engine)() as session:
        revision = await session.get(SourceRevision, created.revision.id)
        revision.revision_number = 2
        with pytest.raises(ValueError, match="revision_number"):
            await session.commit()


async def test_invalid_upload_does_not_create_source(api_client, db_engine):
    workspace_id = await _create_workspace(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    async with _sessionmaker(db_engine)() as session:
        sources = list(await session.scalars(select(SourceRecord)))
        revisions = list(await session.scalars(select(SourceRevision)))
    assert sources == []
    assert revisions == []


async def test_storage_failure_rolls_back_public_state(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    blocked_root = tmp_path / "storage-file"
    blocked_root.write_text("not a directory")

    async with _sessionmaker(db_engine)() as session:
        with pytest.raises(SourceUploadError, match="could not be stored"):
            await upload_private_source(
                session,
                workspace_id=workspace_id,
                filename="notes.txt",
                content=b"private",
                storage_root=str(blocked_root),
            )

    async with _sessionmaker(db_engine)() as session:
        sources = list(await session.scalars(select(SourceRecord)))
        revisions = list(await session.scalars(select(SourceRevision)))
    assert sources == []
    assert revisions == []


async def test_storage_failure_route_returns_safe_error(api_client, db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    blocked_root = tmp_path / "storage-file"
    blocked_root.write_text("not a directory")
    original_root = settings.source_storage_root
    settings.source_storage_root = str(blocked_root)
    try:
        resp = await api_client.post(
            f"/api/workspaces/{workspace_id}/sources/upload",
            files={"file": ("notes.txt", b"private", "text/plain")},
        )
    finally:
        settings.source_storage_root = original_root

    assert resp.status_code == 500
    assert resp.json()["error"] == {
        "code": "storage_error",
        "message": "Uploaded source could not be stored",
        "details": {},
    }
    async with _sessionmaker(db_engine)() as session:
        sources = list(await session.scalars(select(SourceRecord)))
        revisions = list(await session.scalars(select(SourceRevision)))
    assert sources == []
    assert revisions == []


async def test_source_read_is_workspace_scoped(api_client, db_engine):
    workspace_id = await _create_workspace(db_engine, "First Workspace")
    other_workspace_id = await _create_workspace(db_engine, "Other Workspace")
    upload = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/upload",
        files={"file": ("notes.txt", b"private notes", "text/plain")},
    )
    source_id = upload.json()["id"]

    resp = await api_client.get(f"/api/workspaces/{other_workspace_id}/sources/{source_id}")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_source_read_does_not_expose_public_source_without_revision(api_client, db_engine):
    workspace_id = await _create_workspace(db_engine)
    async with _sessionmaker(db_engine)() as session:
        source = SourceRecord(
            workspace_id=workspace_id,
            origin="research_agent",
            access="public",
            title="Public Link",
            url="https://example.com",
            include_on_public_export=True,
            metadata_json={},
        )
        session.add(source)
        await session.commit()
        source_id = source.id

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/sources/{source_id}")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_source_read_does_not_expose_raw_private_text(api_client, db_engine):
    workspace_id = await _create_workspace(db_engine)
    secret = b"SECRET SOURCE TEXT"
    upload = await api_client.post(
        f"/api/workspaces/{workspace_id}/sources/upload",
        files={"file": ("notes.txt", secret, "text/plain")},
    )

    resp = await api_client.get(f"/api/workspaces/{workspace_id}/sources/{upload.json()['id']}")

    assert resp.status_code == 200
    assert secret.decode() not in resp.text
    assert "raw_text" not in resp.text
    assert "object_key" not in resp.text
    assert "content_hash" not in resp.text


async def _upload_for_revision_guard(db_engine, tmp_path):
    workspace_id = await _create_workspace(db_engine)
    async with _sessionmaker(db_engine)() as session:
        return await upload_private_source(
            session,
            workspace_id=workspace_id,
            filename="notes.txt",
            content=b"revision guard",
            content_type="text/plain",
            storage_root=str(tmp_path / "source-storage"),
        )


async def _create_workspace_trail(db_engine) -> tuple[uuid.UUID, uuid.UUID]:
    async with _sessionmaker(db_engine)() as session:
        workspace = Workspace(name="Trail Workspace")
        session.add(workspace)
        await session.flush()
        trail = Trail(
            workspace_id=workspace.id,
            title="Linear Algebra",
            topic="Linear Algebra",
            goal="Learn vectors",
            target_depth="understand",
        )
        session.add(trail)
        await session.flush()
        session.add(
            ConceptNode(
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
        )
        await session.commit()
        return workspace.id, trail.id
