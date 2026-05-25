import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.source import SourceRecord, SourceRevision
from backend.app.models.workspace import Workspace
from backend.app.schemas.source import SourceRecordRead, SourceRevisionSummary, SourceUploadResponse

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PARSER_NAME = "none"
PARSER_VERSION = "upload-only-v1"


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
            if "destination" in locals():
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
        metadata_json={
            "original_filename": filename,
            "stored_private_object": True,
            "parsing": "deferred",
            "chunks_created": 0,
            "embeddings_created": 0,
        },
    )
    session.add(revision)

    try:
        await session.commit()
        await session.refresh(source)
        await session.refresh(revision)
    except Exception:
        await session.rollback()
        try:
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
