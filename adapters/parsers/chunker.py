"""Deterministic text chunking helpers."""

from __future__ import annotations


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


def chunk_text_deterministic(
    text: str,
    *,
    chunk_size: int = 1000,
    overlap: int = 150,
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
