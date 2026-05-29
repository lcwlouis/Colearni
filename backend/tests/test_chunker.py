import uuid

import pytest

from backend.app.services import chunker
from backend.app.services.chunker import chunk_elements
from backend.app.services.parser import CanonicalDocument, DocumentElement


def test_plain_paragraphs_shorter_than_limit_create_one_chunk(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 100)
    elements = [
        DocumentElement(type="paragraph", text="Alpha"),
        DocumentElement(type="paragraph", text="Beta"),
    ]

    chunks = _chunks(elements)

    assert len(chunks) == 1
    assert chunks[0].text == "Alpha\n\nBeta"


def test_paragraph_overflow_creates_multiple_chunks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 10)
    elements = [
        DocumentElement(type="paragraph", text="Alpha"),
        DocumentElement(type="paragraph", text="BetaBeta"),
        DocumentElement(type="paragraph", text="Gamma"),
    ]

    chunks = _chunks(elements)

    assert len(chunks) == 3
    assert all(len(chunk.text) <= 10 for chunk in chunks)


def test_heading_flushes_current_buffer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 100)
    elements = [
        DocumentElement(type="paragraph", text="Before"),
        DocumentElement(type="heading_2", text="Section"),
        DocumentElement(type="paragraph", text="After"),
    ]

    chunks = _chunks(elements)

    assert [chunk.text for chunk in chunks] == ["Before", "## Section\n\nAfter"]


def test_section_heading_tracks_heading_scope(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 100)
    elements = [
        DocumentElement(type="paragraph", text="Before"),
        DocumentElement(type="heading_1", text="Vectors"),
        DocumentElement(type="paragraph", text="After"),
    ]

    chunks = _chunks(elements)

    assert chunks[0].section_heading is None
    assert chunks[1].section_heading == "Vectors"


def test_single_oversized_paragraph_splits_by_sentence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 13)
    elements = [DocumentElement(type="paragraph", text="One sentence. Two sentence. Third one.")]

    chunks = _chunks(elements)

    assert [chunk.text for chunk in chunks] == ["One sentence.", "Two sentence.", "Third one."]
    assert all(len(chunk.text) <= 13 for chunk in chunks)


def test_empty_elements_return_zero_chunks():
    assert _chunks([]) == []


def test_sentence_split_chunks_anchor_line_numbers_across_newlines(
    monkeypatch: pytest.MonkeyPatch,
):
    """Combined sentence chunks aren't verbatim substrings; offsets must still map."""
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 12)
    # One oversized paragraph whose sentences are separated by newlines in the
    # canonical text, so the rejoined "Aaaa. Bbbb." chunk spans two lines.
    elements = [DocumentElement(type="paragraph", text="Aaaa.\nBbbb.\nCccc.")]
    doc = CanonicalDocument(elements=elements, parser_name="test")
    full_text = doc.text
    lines = full_text.splitlines()

    chunks = chunk_elements(elements, uuid.uuid4(), uuid.uuid4(), full_text)

    assert [chunk.text for chunk in chunks] == ["Aaaa. Bbbb.", "Cccc."]
    combined = chunks[0]
    # The combined chunk's words must live inside the referenced line window.
    window = " ".join(lines[combined.line_start - 1 : combined.line_end])
    for token in combined.text.split():
        assert token in window
    assert combined.line_start == 1
    assert combined.line_end == 2


def test_line_numbers_are_set_for_single_and_multiline_chunks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(chunker, "MAX_CHUNK_CHARS", 100)
    elements = [
        DocumentElement(type="heading_1", text="Title"),
        DocumentElement(type="paragraph", text="Line one\nLine two"),
        DocumentElement(type="heading_2", text="Next"),
    ]

    chunks = _chunks(elements)

    assert all(chunk.line_start >= 1 and chunk.line_end >= 1 for chunk in chunks)
    assert chunks[0].line_start < chunks[0].line_end
    assert chunks[1].line_start == chunks[1].line_end


def _chunks(elements: list[DocumentElement]):
    doc = CanonicalDocument(elements=elements, parser_name="test")
    return chunk_elements(elements, uuid.uuid4(), uuid.uuid4(), doc.text)
