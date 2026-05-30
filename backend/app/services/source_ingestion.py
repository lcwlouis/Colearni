import asyncio
import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.embedding_client import EmbeddingClient
from backend.app.models.source import (  # noqa: F401 (SourceChunk: mapper registration)
    SourceChunk,
    SourceRecord,
    SourceRevision,
)
from backend.app.models.workspace import Workspace
from backend.app.schemas.source import SourceRecordRead, SourceRevisionSummary, SourceUploadResponse
from backend.app.services.chunker import chunk_elements
from backend.app.services.concept_source_links import auto_link_source_to_trail
from backend.app.services.parser import parse_source
from backend.app.settings import settings

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PARSER_NAME = "none"
PARSER_VERSION = "parser-pipeline-v1"

logger = logging.getLogger(__name__)


class SourceUploadError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def upload_private_source(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    filename: str,
    content: bytes,
    storage_root: str,
    title: str | None = None,
    content_type: str | None = None,
    trail_id: uuid.UUID | None = None,
) -> SourceUploadResponse:
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")
    filename = Path(filename).name
    if not filename.strip():
        raise SourceUploadError("Uploaded file must have a filename")
    if not content:
        raise SourceUploadError("Uploaded file must not be empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise SourceUploadError("Uploaded file exceeds the 50 MB limit", status_code=413)

    source = SourceRecord(
        workspace_id=workspace_id,
        origin="user_upload",
        access="private",
        title=(title or "").strip() or filename,
        url=None,
        license=None,
        include_on_public_export=False,
        metadata_json={
            "ingestion_status": "pending_parse",
            "source_kind": "uploaded_file",
            "original_filename": filename,
            "export_policy": "private_upload_never_public",
        },
    )
    session.add(source)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise

    digest = hashlib.sha256(content).hexdigest()
    object_key = _build_object_key(workspace_id, source.id, digest, filename)
    destination: Path | None = None
    try:
        destination = _safe_storage_path(storage_root, object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    except SourceUploadError:
        await session.rollback()
        raise
    except OSError as exc:
        await session.rollback()
        try:
            if destination is not None:
                destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise SourceUploadError("Uploaded source could not be stored", status_code=500) from exc

    revision = SourceRevision(
        workspace_id=workspace_id,
        source_id=source.id,
        revision_number=1,
        object_key=object_key,
        content_hash=f"sha256:{digest}",
        content_type=content_type,
        file_size_bytes=len(content),
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        status="pending_parse",
        error_message=None,
        raw_text=None,
        metadata_json={
            "original_filename": filename,
            "stored_private_object": True,
            "parsing": "pending",
            "chunks_created": 0,
            "embeddings_created": 0,
        },
    )
    session.add(revision)
    await session.flush()

    doc = None
    chunks_created = 0
    embeddings_created = 0
    try:
        doc = await asyncio.to_thread(parse_source, content, content_type or "", filename)
        revision.raw_text = doc.text
        revision.parser_name = doc.parser_name
        revision.status = "parsed"
        revision.error_message = None
    except Exception as exc:
        revision.status = "failed"
        revision.error_message = str(exc)

    if doc is not None:
        chunks = chunk_elements(doc.elements, revision.id, workspace_id, doc.text)
        session.add_all(chunks)
        await session.flush()
        chunks_created = len(chunks)

        if settings.embedding_provider.lower() != "disabled" and chunks:
            # Embeddings are best-effort: a provider/network failure must not
            # discard the parsed source. Retrieval still works via the ILIKE
            # fallback when chunks have no embedding.
            try:
                embedding_client = EmbeddingClient.from_settings(settings)
                vectors = await embedding_client.embed([chunk.text for chunk in chunks])
            except Exception as exc:
                logger.warning(
                    "Embedding generation failed for source %s; storing chunks without "
                    "embeddings (ILIKE fallback still applies): %s",
                    source.id,
                    exc,
                )
                vectors = None
            if vectors is not None:
                for chunk, vector in zip(chunks, vectors, strict=False):
                    chunk.embedding = vector
                embeddings_created = len(vectors)

    if trail_id is not None and doc is not None:
        await auto_link_source_to_trail(session, revision.id, trail_id, workspace_id)

    source.metadata_json = {
        **source.metadata_json,
        "ingestion_status": revision.status,
    }
    revision.metadata_json = {
        **revision.metadata_json,
        "parsing": revision.status,
        "chunks_created": chunks_created,
        "embeddings_created": embeddings_created,
        "canonical_text_stored": doc is not None,
    }

    try:
        await session.commit()
        await session.refresh(source)
        await session.refresh(revision)
    except Exception:
        await session.rollback()
        try:
            if destination is not None:
                destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return _upload_response(source, revision)


async def get_private_source(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
) -> SourceUploadResponse:
    source = await session.scalar(
        select(SourceRecord).where(
            SourceRecord.id == source_id,
            SourceRecord.workspace_id == workspace_id,
        )
    )
    if source is None or source.origin != "user_upload":
        raise LookupError(f"Source {source_id} not found")
    revision = await session.scalar(
        select(SourceRevision)
        .where(
            SourceRevision.source_id == source_id,
            SourceRevision.workspace_id == workspace_id,
        )
        .order_by(SourceRevision.revision_number.desc())
        .limit(1)
    )
    if revision is None:
        raise LookupError(f"Source {source_id} has no revision")
    return _upload_response(source, revision)


def _upload_response(source: SourceRecord, revision: SourceRevision) -> SourceUploadResponse:
    payload = SourceRecordRead.model_validate(source).model_dump()
    payload["revision"] = SourceRevisionSummary.model_validate(revision)
    return SourceUploadResponse.model_validate(payload)


def _build_object_key(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    digest: str,
    filename: str,
) -> str:
    suffix = Path(filename).suffix.lower()
    if len(suffix) > 16 or any(char in suffix for char in ("/", "\\")):
        suffix = ""
    return f"workspaces/{workspace_id}/sources/{source_id}/revisions/1/{digest}{suffix}"


def _safe_storage_path(storage_root: str, object_key: str) -> Path:
    root = _storage_root(storage_root)
    path = (root / object_key).resolve()
    if path != root and root not in path.parents:
        raise SourceUploadError("Invalid private storage object key", status_code=500)
    return path


def _storage_root(storage_root: str) -> Path:
    if not storage_root.strip():
        raise SourceUploadError("Private source storage root is not configured", status_code=500)
    return Path(storage_root).expanduser().resolve()
