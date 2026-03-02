"""Deterministic text chunking helpers."""

from __future__ import annotations

import re


def _find_best_break(text: str, start: int, hard_end: int, min_offset: int) -> int:
    """Find the best split point in *text[start:hard_end]*.

    Priority: paragraph break (``\\n\\n``) > line break (``\\n``) > sentence
    end (``. `` / ``? `` / ``! ``) > space.  Returns the absolute index
    after the break character, or *hard_end* if no usable break is found.
    """
    region = text[start:hard_end]
    for sep in ("\n\n", "\n"):
        pos = region.rfind(sep)
        if pos >= min_offset:
            return start + pos + len(sep)
    # Sentence-end heuristic: ". " or "? " or "! "
    for ending in (". ", "? ", "! "):
        pos = region.rfind(ending)
        if pos >= min_offset:
            return start + pos + len(ending)
    # Fallback: space
    pos = region.rfind(" ")
    if pos >= min_offset:
        return start + pos + 1
    return hard_end


def _word_offset_to_char(text: str, word_count: int) -> int:
    """Return the character index after *word_count* whitespace-delimited words."""
    idx = 0
    counted = 0
    length = len(text)
    while counted < word_count and idx < length:
        # skip whitespace
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        # skip word
        while idx < length and not text[idx].isspace():
            idx += 1
        counted += 1
    return idx if counted >= word_count else length


def _chunk_by_chars(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Character-based chunking (original algorithm)."""
    chunks: list[str] = []
    start = 0
    text_len = len(text)
    min_break_size = chunk_size // 2

    while start < text_len:
        hard_end = min(start + chunk_size, text_len)

        if hard_end < text_len:
            end = _find_best_break(text, start, hard_end, min_break_size)
        else:
            end = hard_end

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        next_start = max(end - overlap, start + 1)
        if next_start <= start:
            raise RuntimeError("Chunker failed to make progress.")
        start = next_start

    return chunks


def _chunk_by_words(text: str, chunk_words: int, overlap_words: int) -> list[str]:
    """Word-based chunking that still respects natural break points."""
    word_starts = [m.start() for m in re.finditer(r"\S+", text)]
    if not word_starts:
        return []

    total_words = len(word_starts)
    chunks: list[str] = []
    word_idx = 0

    while word_idx < total_words:
        end_word = min(word_idx + chunk_words, total_words)

        char_start = word_starts[word_idx]
        if end_word < total_words:
            char_end = word_starts[end_word]
            min_offset = (end_word - word_idx) // 2
            min_char = (
                word_starts[word_idx + min_offset] - char_start
                if min_offset > 0
                else 0
            )
            end = _find_best_break(text, char_start, char_end, min_char)
        else:
            end = len(text)

        chunk = text[char_start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_word = max(end_word - overlap_words, word_idx + 1)
        if next_word <= word_idx:
            next_word = word_idx + 1
        word_idx = next_word

    return chunks


def chunk_text_deterministic(
    text: str,
    *,
    chunk_size: int = 250,
    overlap: int = 40,
    size_unit: str = "words",
) -> list[str]:
    """Split text into deterministic, overlapping chunks with stable ordering."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not text:
        return []

    if size_unit == "words":
        return _chunk_by_words(text, chunk_size, overlap)
    return _chunk_by_chars(text, chunk_size, overlap)
