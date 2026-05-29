import pytest

from backend.app.services.parser import CanonicalDocument, DocumentElement, parse_source

PDF_BYTES = (
    b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\n0000000115 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
)


def test_parse_pdf_minimal_bytes_does_not_raise():
    pytest.importorskip("pdfplumber")

    doc = parse_source(PDF_BYTES, "application/pdf")

    assert doc.parser_name == "pdfplumber"
    assert isinstance(doc.elements, list)


def test_parse_plaintext_returns_paragraph_elements():
    doc = parse_source(b"First paragraph\n\nSecond paragraph", "text/plain")

    assert doc.parser_name == "plaintext"
    assert doc.elements == [
        DocumentElement(type="paragraph", text="First paragraph"),
        DocumentElement(type="paragraph", text="Second paragraph"),
    ]


def test_parse_markdown_returns_headings_and_paragraphs():
    doc = parse_source(b"# Title\n\nIntro\n\n## Topic\nMore\n\n### Detail", "text/markdown")

    assert [element.type for element in doc.elements] == [
        "heading_1",
        "paragraph",
        "heading_2",
        "paragraph",
        "heading_3",
    ]
    assert [element.text for element in doc.elements] == [
        "Title",
        "Intro",
        "Topic",
        "More",
        "Detail",
    ]


def test_canonical_document_text_serializes_markdown_headings():
    doc = CanonicalDocument(
        parser_name="markdown",
        elements=[
            DocumentElement(type="heading_1", text="Title"),
            DocumentElement(type="heading_2", text="Topic"),
            DocumentElement(type="heading_3", text="Detail"),
            DocumentElement(type="paragraph", text="Body"),
        ],
    )

    assert doc.text == "# Title\n\n## Topic\n\n### Detail\n\nBody"


def test_parse_source_raises_for_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported source format"):
        parse_source(b"data", "application/octet-stream", "blob.bin")


def test_parse_source_strips_content_type_parameters():
    doc = parse_source(b"Plain body text.", "text/plain; charset=utf-8")
    assert doc.parser_name == "plaintext"
    assert "Plain body text." in doc.text


def test_parse_source_falls_back_to_extension_for_octet_stream_markdown():
    doc = parse_source(b"# Heading\n\nBody", "application/octet-stream", "notes.md")
    assert doc.parser_name == "markdown"
    assert doc.text == "# Heading\n\nBody"
