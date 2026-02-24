"""Unit tests for text parser/normalizer."""

import pytest
from adapters.parsers.text import (
    UnsupportedTextDocumentError,
    normalize_text,
    parse_text_payload,
)


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
