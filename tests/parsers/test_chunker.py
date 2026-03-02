"""Unit tests for deterministic chunking."""

import pytest
from adapters.parsers.chunker import chunk_text_deterministic


def test_chunk_text_deterministic_is_stable_for_same_input() -> None:
    """Chunk ordering and content should be stable across repeated calls."""
    text = ("alpha beta gamma delta epsilon zeta eta theta iota kappa\n" * 30).strip()

    first = chunk_text_deterministic(text, chunk_size=120, overlap=20)
    second = chunk_text_deterministic(text, chunk_size=120, overlap=20)

    assert first == second
    assert first


def test_chunk_text_deterministic_handles_short_input() -> None:
    """Short text should produce a single chunk."""
    chunks = chunk_text_deterministic("short text", chunk_size=100, overlap=10)
    assert chunks == ["short text"]


def test_chunk_text_deterministic_rejects_invalid_config() -> None:
    """Invalid chunking params should fail fast."""
    with pytest.raises(ValueError):
        chunk_text_deterministic("hello", chunk_size=0, overlap=0)
    with pytest.raises(ValueError):
        chunk_text_deterministic("hello", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_text_deterministic("hello", chunk_size=10, overlap=-1)


def test_prefers_paragraph_break_over_space() -> None:
    """Paragraph breaks should be preferred over later spaces."""
    para1 = "A" * 60
    para2 = "B" * 30 + " " + "C" * 8
    text = f"{para1}\n\n{para2}"
    chunks = chunk_text_deterministic(text, chunk_size=100, overlap=10)
    # First chunk should end at the paragraph break, not the later space
    assert chunks[0] == para1


def test_prefers_sentence_end_over_space() -> None:
    """Sentence endings ('. ') should be preferred over later spaces."""
    sentence = "X" * 55 + ". "
    tail = "Y" * 30 + " " + "Z" * 30
    text = sentence + tail
    chunks = chunk_text_deterministic(text, chunk_size=100, overlap=10)
    assert chunks[0].endswith(".")


def test_empty_input_returns_empty_list() -> None:
    assert chunk_text_deterministic("", chunk_size=100, overlap=10) == []
