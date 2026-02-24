"""Deterministic text chunking helpers."""

from __future__ import annotations


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
        end = hard_end

        if hard_end < text_len:
            search_region = text[start:hard_end]
            split_offset = max(
                search_region.rfind("\n\n"),
                search_region.rfind("\n"),
                search_region.rfind(" "),
            )
            if split_offset >= min_break_size:
                end = start + split_offset + 1

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
