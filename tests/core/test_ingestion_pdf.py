"""Unit tests for PDF-specific ingestion behavior."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from adapters.db.documents import DocumentRow
from core.ingestion import IngestionRequest, IngestionValidationError, ingest_text_document
from core.settings import get_settings
from pypdf import PdfWriter


class _FakeSession:
    """Session test double that only tracks commit calls."""

    def __init__(self) -> None:
        self.commit_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1


def _build_text_pdf_bytes(text: str) -> bytes:
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\n"
            "endobj\n"
        ),
        "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    stream = f"BT\n/F1 12 Tf\n72 720 Td\n({text}) Tj\nET\n"
    objects.append(
        f"5 0 obj\n<< /Length {len(stream.encode('latin-1'))} >>\nstream\n"
        f"{stream}endstream\nendobj\n"
    )

    header = "%PDF-1.4\n"
    body = ""
    offsets = [0]
    current = len(header.encode("latin-1"))
    for obj in objects:
        offsets.append(current)
        body += obj
        current += len(obj.encode("latin-1"))

    xref_start = current
    xref = f"xref\n0 {len(offsets)}\n0000000000 65535 f \n"
    xref += "".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    trailer = (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    )
    return (header + body + xref + trailer).encode("latin-1")


def _build_blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _pdf_request(raw_bytes: bytes) -> IngestionRequest:
    return IngestionRequest(
        workspace_id=7,
        uploaded_by_user_id=3,
        raw_bytes=raw_bytes,
        content_type="application/pdf",
        filename="notes.pdf",
        title="PDF Notes",
        source_uri=None,
    )


def test_ingest_extractable_pdf_reuses_chunk_store_pipeline(monkeypatch: Any) -> None:
    """Extractable PDF ingestion should flow through chunking and chunk storage."""
    session = _FakeSession()
    settings = get_settings().model_copy(
        update={"ingest_populate_embeddings": False, "ingest_build_graph": False}
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "domain.ingestion.service.get_document_by_content_hash",
        lambda db, workspace_id, content_hash: None,  # noqa: ARG005
    )

    def _fake_chunker(normalized_text: str) -> list[str]:
        captured["normalized_text"] = normalized_text
        return ["chunk-one", "chunk-two"]

    monkeypatch.setattr("domain.ingestion.service.chunk_text_deterministic", _fake_chunker)

    def _fake_insert_document(
        db: object,  # noqa: ARG001
        *,
        workspace_id: int,
        uploaded_by_user_id: int,  # noqa: ARG001
        title: str,
        source_uri: str | None,
        mime_type: str,
        content_hash: str,
    ) -> DocumentRow:
        captured["mime_type"] = mime_type
        return DocumentRow(
            id=41,
            workspace_id=workspace_id,
            title=title,
            source_uri=source_uri,
            mime_type=mime_type,
            content_hash=content_hash,
        )

    monkeypatch.setattr("domain.ingestion.service.insert_document", _fake_insert_document)

    def _fake_insert_chunks_bulk(
        db: object,
        *,
        workspace_id: int,
        document_id: int,
        chunk_texts: list[str],
    ) -> int:
        captured["workspace_id"] = workspace_id
        captured["document_id"] = document_id
        captured["chunk_texts"] = list(chunk_texts)
        return len(chunk_texts)

    monkeypatch.setattr("domain.ingestion.service.insert_chunks_bulk", _fake_insert_chunks_bulk)

    result = ingest_text_document(
        session,  # type: ignore[arg-type]
        request=_pdf_request(_build_text_pdf_bytes("Linear Algebra PDF")),
        settings=settings,
    )

    assert result.created is True
    assert result.mime_type == "application/pdf"
    assert result.chunk_count == 2
    assert session.commit_calls == 1
    assert captured["normalized_text"] == "Linear Algebra PDF"
    assert captured["mime_type"] == "application/pdf"
    assert captured["workspace_id"] == 7
    assert captured["document_id"] == 41
    assert captured["chunk_texts"] == ["chunk-one", "chunk-two"]


def test_ingest_non_extractable_pdf_fails_with_clear_message(monkeypatch: Any) -> None:
    """Image-only/blank PDFs should fail with the explicit non-extractable message."""
    session = _FakeSession()

    monkeypatch.setattr(
        "domain.ingestion.service.get_document_by_content_hash",
        lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("should fail before DB duplicate checks")
        ),
    )

    with pytest.raises(
        IngestionValidationError,
        match="PDF has no extractable text layer. Only text-extractable PDFs are supported.",
    ):
        ingest_text_document(
            session,  # type: ignore[arg-type]
            request=_pdf_request(_build_blank_pdf_bytes()),
            settings=get_settings().model_copy(
                update={"ingest_populate_embeddings": False, "ingest_build_graph": False}
            ),
        )

    assert session.commit_calls == 0
