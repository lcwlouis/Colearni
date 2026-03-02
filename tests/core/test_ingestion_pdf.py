"""Unit tests for PDF-specific ingestion behavior."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from adapters.db.documents import DocumentRow
from adapters.parsers.chunker import chunk_text_deterministic
from adapters.parsers.text import parse_text_payload
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

    def _fake_chunker(normalized_text: str, **_kwargs: object) -> list[str]:
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


def _build_multipage_pdf_bytes(page_count: int, chars_per_page: int = 500) -> bytes:
    """Build a PDF with *page_count* pages, each containing *chars_per_page* of text."""
    writer = PdfWriter()
    for i in range(page_count):
        page_text = f"Page {i + 1}. " + "x" * (chars_per_page - len(f"Page {i + 1}. "))
        # Create a page with actual text content via pypdf annotation
        writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    raw = output.getvalue()

    # pypdf's add_blank_page doesn't embed text, so build pages manually.
    # Use a simple raw-PDF builder that embeds text streams.
    return _build_raw_multipage_pdf(page_count, chars_per_page)


def _build_raw_multipage_pdf(page_count: int, chars_per_page: int) -> bytes:
    """Construct a raw PDF with extractable text on every page."""
    # Object 1: Catalog
    # Object 2: Pages
    # Object 3: Font
    # Objects 4..4+2*page_count-1: Page + Contents pairs

    page_obj_ids: list[int] = []
    objects: list[str] = []

    # Catalog
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # Font
    objects.append(
        "3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )

    next_id = 4
    for i in range(page_count):
        page_id = next_id
        contents_id = next_id + 1
        next_id += 2
        page_obj_ids.append(page_id)

        text_body = f"Page {i + 1} content. " + "a" * max(0, chars_per_page - len(f"Page {i + 1} content. "))
        # Split into lines of ~70 chars for the PDF stream (Tj limit)
        lines: list[str] = []
        pos = 0
        y = 720
        while pos < len(text_body):
            segment = text_body[pos : pos + 70]
            # Escape parens for PDF string
            segment = segment.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            lines.append(f"({segment}) Tj\n0 -14 Td")
            pos += 70
            y -= 14
        stream = "BT\n/F1 12 Tf\n72 720 Td\n" + "\n".join(lines) + "\nET\n"
        stream_bytes = stream.encode("latin-1")

        objects.append(
            f"{page_id} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {contents_id} 0 R >>\n"
            f"endobj\n"
        )
        objects.append(
            f"{contents_id} 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n"
            f"{stream}endstream\nendobj\n"
        )

    # Pages object (object 2)
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {page_count} >>\nendobj\n"
    objects.insert(1, pages_obj)  # Insert after catalog

    header = "%PDF-1.4\n"
    body = ""
    offsets: list[int] = [0]
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


def test_multipage_pdf_produces_reasonable_chunk_count() -> None:
    """A multi-page PDF with ~500 chars/page should produce proportional chunks."""
    page_count = 10
    chars_per_page = 500
    pdf_bytes = _build_raw_multipage_pdf(page_count, chars_per_page)

    parsed = parse_text_payload(
        raw_bytes=pdf_bytes,
        filename="multipage.pdf",
        content_type="application/pdf",
    )

    total_extracted = len(parsed.normalized_text)
    # Verify we actually extracted substantial text (not just 2000 chars for 10 pages)
    assert total_extracted > page_count * 100, (
        f"Expected >{page_count * 100} chars from {page_count}-page PDF, "
        f"got {total_extracted}"
    )

    chunks = chunk_text_deterministic(parsed.normalized_text, chunk_size=1000, overlap=150)
    # With ~5000 chars total and 1000-char chunks, we expect at least 4 chunks
    expected_min = max(1, total_extracted // 1000)
    assert len(chunks) >= expected_min, (
        f"Expected ≥{expected_min} chunks from {total_extracted} chars, got {len(chunks)}"
    )
