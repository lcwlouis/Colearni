"""Unit tests for text parser/normalizer."""

import pytest
from adapters.parsers.text import (
    UnsupportedTextDocumentError,
    normalize_text,
    parse_text_payload,
)


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


def test_normalize_text_is_deterministic_across_newline_variants() -> None:
    """CRLF and LF versions of same content should normalize identically."""
    with_crlf = "Line one\r\nLine two\r\n\r\nLine three\r\n"
    with_lf = "Line one\nLine two\n\nLine three\n"

    expected = "Line one\nLine two\n\nLine three"
    assert normalize_text(with_crlf) == normalize_text(with_lf) == expected


def test_parse_text_payload_accepts_markdown_by_extension() -> None:
    """Markdown files are accepted and normalized."""
    parsed = parse_text_payload(
        raw_bytes=b"# Heading\r\nBody line\r\n",
        filename="notes.md",
        content_type="application/octet-stream",
    )

    assert parsed.mime_type == "text/markdown"
    assert parsed.normalized_text == "# Heading\nBody line"


def test_parse_text_payload_accepts_raw_text_by_content_type() -> None:
    """Raw text bodies with supported content-type are accepted."""
    parsed = parse_text_payload(
        raw_bytes=b"plain text",
        filename=None,
        content_type="text/plain; charset=utf-8",
    )

    assert parsed.mime_type == "text/plain"
    assert parsed.normalized_text == "plain text"


def test_parse_text_payload_rejects_unsupported_types() -> None:
    """Unsupported extensions and media types should be rejected."""
    with pytest.raises(UnsupportedTextDocumentError):
        parse_text_payload(
            raw_bytes=b"<html>hi</html>",
            filename="page.html",
            content_type="text/html",
        )


def test_parse_text_payload_accepts_pdf_and_extracts_text() -> None:
    """Text-layer PDFs should parse as application/pdf with extracted text."""
    parsed = parse_text_payload(
        raw_bytes=_build_text_pdf_bytes("Linear Algebra PDF"),
        filename="notes.pdf",
        content_type="application/octet-stream",
    )

    assert parsed.mime_type == "application/pdf"
    assert parsed.normalized_text == "Linear Algebra PDF"


def test_parse_text_payload_rejects_malformed_pdf() -> None:
    """Unreadable PDF payloads should return a clear parser error."""
    with pytest.raises(UnsupportedTextDocumentError, match="Failed to parse PDF payload"):
        parse_text_payload(
            raw_bytes=b"not a valid pdf",
            filename="broken.pdf",
            content_type="application/pdf",
        )
