"""Unit tests for deterministic chunking."""

import pytest
from adapters.parsers.chunker import chunk_text_deterministic


def test_chunk_text_deterministic_is_stable_for_same_input() -> None:
    """Chunk ordering and content should be stable across repeated calls."""
    text = ("alpha beta gamma delta epsilon zeta eta theta iota kappa\n" * 30).strip()

    first = chunk_text_deterministic(text, chunk_size=120, overlap=20, size_unit="chars")
    second = chunk_text_deterministic(text, chunk_size=120, overlap=20, size_unit="chars")

    assert first == second
    assert first


def test_chunk_text_deterministic_handles_short_input() -> None:
    """Short text should produce a single chunk."""
    chunks = chunk_text_deterministic("short text", chunk_size=100, overlap=10, size_unit="chars")
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
    chunks = chunk_text_deterministic(text, chunk_size=100, overlap=10, size_unit="chars")
    # First chunk should end at the paragraph break, not the later space
    assert chunks[0] == para1


def test_prefers_sentence_end_over_space() -> None:
    """Sentence endings ('. ') should be preferred over later spaces."""
    sentence = "X" * 55 + ". "
    tail = "Y" * 30 + " " + "Z" * 30
    text = sentence + tail
    chunks = chunk_text_deterministic(text, chunk_size=100, overlap=10, size_unit="chars")
    assert chunks[0].endswith(".")


def test_empty_input_returns_empty_list() -> None:
    assert chunk_text_deterministic("", chunk_size=100, overlap=10, size_unit="chars") == []


# ── Word-based chunking tests ──────────────────────────────────────


def test_word_based_chunking_produces_correct_word_count() -> None:
    text = " ".join(["word"] * 500)
    chunks = chunk_text_deterministic(text, chunk_size=250, overlap=40, size_unit="words")
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        wc = len(chunk.split())
        assert 200 <= wc <= 300, f"non-final chunk word count {wc} outside 200-300"
    # Last chunk may be shorter
    last_wc = len(chunks[-1].split())
    assert 1 <= last_wc <= 300, f"final chunk word count {last_wc} outside 1-300"


def test_word_chunking_overlap() -> None:
    text = " ".join(f"w{i}" for i in range(300))
    chunks = chunk_text_deterministic(text, chunk_size=100, overlap=20, size_unit="words")
    assert len(chunks) >= 2
    for i in range(len(chunks) - 1):
        tail_words = chunks[i].split()[-20:]
        head_words = chunks[i + 1].split()[:20]
        shared = set(tail_words) & set(head_words)
        assert len(shared) > 0, f"no overlap between chunk {i} and {i+1}"


def test_word_chunking_respects_paragraph_breaks() -> None:
    para1 = " ".join(f"a{i}" for i in range(150))
    para2 = " ".join(f"b{i}" for i in range(150))
    text = para1 + "\n\n" + para2
    chunks = chunk_text_deterministic(text, chunk_size=200, overlap=30, size_unit="words")
    assert len(chunks) >= 2
    # First chunk should end near the paragraph boundary
    first_words = set(chunks[0].split())
    assert "a0" in first_words
    assert "b149" not in first_words


def test_word_chunking_small_text() -> None:
    text = " ".join(f"w{i}" for i in range(50))
    chunks = chunk_text_deterministic(text, chunk_size=250, overlap=40, size_unit="words")
    assert len(chunks) == 1
    assert chunks[0] == text


def test_word_chunking_empty_text() -> None:
    assert chunk_text_deterministic("", chunk_size=250, overlap=40, size_unit="words") == []


def test_default_is_word_based() -> None:
    text = " ".join(["hello"] * 500)
    chunks = chunk_text_deterministic(text)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        wc = len(chunk.split())
        assert 100 <= wc <= 350, f"default chunk word count {wc} outside expected range"
    # Last chunk may be shorter
    last_wc = len(chunks[-1].split())
    assert 1 <= last_wc <= 350, f"default final chunk word count {last_wc} outside range"


def test_large_document_word_chunking() -> None:
    import random

    rng = random.Random(42)
    words: list[str] = []
    while len(words) < 5000:
        sentence_len = rng.randint(5, 20)
        sentence_words = [f"word{rng.randint(0, 9999)}" for _ in range(sentence_len)]
        sentence_words[0] = sentence_words[0].capitalize()
        words.extend(sentence_words)
        words[-1] = words[-1] + "."
    text = " ".join(words[:5000])

    chunks = chunk_text_deterministic(text, chunk_size=250, overlap=40, size_unit="words")
    assert 15 <= len(chunks) <= 25, f"expected ~20 chunks, got {len(chunks)}"
    for chunk in chunks:
        wc = len(chunk.split())
        assert 100 <= wc <= 350, f"chunk word count {wc} outside 100-350"
