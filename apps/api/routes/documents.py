"""Document upload route definitions.

.. deprecated::
    This route (``/api/documents/upload``) is superseded by
    ``/api/workspaces/{ws_id}/knowledge-base/documents/upload`` in ``knowledge_base.py``.
    It remains for backward compatibility and will be removed in a future release.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from adapters.db.dependencies import get_db_session
from adapters.parsers.text import UnsupportedTextDocumentError
from core.ingestion import IngestionRequest, IngestionValidationError
from domain.knowledge_base.upload_flow import execute_upload
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentUploadResponse(BaseModel):
    """API response for document upload."""

    document_id: int
    workspace_id: int
    title: str
    mime_type: str
    content_hash: str
    chunk_count: int
    created: bool


@dataclass(frozen=True)
class UploadPayload:
    """Parsed transport-level upload payload."""

    raw_bytes: bytes
    filename: str | None
    content_type: str | None
    title: str | None
    source_uri: str | None


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    workspace_id: Annotated[int, Query(gt=0)],
    uploaded_by_user_id: Annotated[int, Query(gt=0)],
    title: Annotated[str | None, Query()] = None,
    source_uri: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db_session),
) -> DocumentUploadResponse | JSONResponse:
    """Upload .md/.txt/.pdf content via multipart or raw body.

    .. deprecated:: Use ``POST /api/workspaces/{ws_id}/knowledge-base/documents/upload`` instead.
    """
    payload = await _read_upload_payload(request)
    ingestion_request = IngestionRequest(
        workspace_id=workspace_id,
        uploaded_by_user_id=uploaded_by_user_id,
        raw_bytes=payload.raw_bytes,
        content_type=payload.content_type,
        filename=payload.filename,
        title=title or payload.title,
        source_uri=source_uri or payload.source_uri,
    )

    try:
        result = execute_upload(
            db, background_tasks, request=ingestion_request, app_state=request.app.state,
        )
    except UnsupportedTextDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except IngestionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    response = DocumentUploadResponse(
        document_id=result.document_id,
        workspace_id=result.workspace_id,
        title=result.title,
        mime_type=result.mime_type,
        content_hash=result.content_hash,
        chunk_count=result.chunk_count,
        created=result.created,
    )
    if result.created:
        return response
    return JSONResponse(status_code=status.HTTP_200_OK, content=response.model_dump(mode="json"))


async def _read_upload_payload(request: Request) -> UploadPayload:
    content_type = request.headers.get("content-type", "")
    canonical_content_type = _canonical_content_type(content_type)

    if canonical_content_type == "multipart/form-data":
        form = await request.form()
        file_part = form.get("file")
        if file_part is None or not hasattr(file_part, "read"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multipart requests must include a file part named 'file'.",
            )
        raw_bytes = await file_part.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded file is empty.",
            )
        payload_content_type = _extract_optional_string(file_part, "content_type")
        payload_filename = _extract_optional_string(file_part, "filename")
        return UploadPayload(
            raw_bytes=raw_bytes,
            filename=payload_filename,
            content_type=payload_content_type,
            title=_extract_optional_form_string(form, "title"),
            source_uri=_extract_optional_form_string(form, "source_uri"),
        )

    raw_bytes = await request.body()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Raw body is empty.",
        )
    return UploadPayload(
        raw_bytes=raw_bytes,
        filename=None,
        content_type=canonical_content_type,
        title=None,
        source_uri=None,
    )


def _canonical_content_type(content_type: str) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", maxsplit=1)[0].strip().lower()


def _extract_optional_form_string(form: Any, key: str) -> str | None:
    raw_value = form.get(key)
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _extract_optional_string(obj: Any, attr: str) -> str | None:
    raw_value = getattr(obj, attr, None)
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None
