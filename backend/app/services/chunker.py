import os
import re
import uuid

from backend.app.models.source import SourceChunk
from backend.app.services.parser import DocumentElement

MAX_CHUNK_CHARS = int(os.environ.get("MAX_CHUNK_CHARS", "2000"))
_HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}


def chunk_elements(
    elements: list[DocumentElement],
    revision_id: uuid.UUID,
    workspace_id: uuid.UUID,
    full_text: str,
) -> list[SourceChunk]:
    current_heading: str | None = None
    current_buffer: list[DocumentElement] = []
    chunks: list[SourceChunk] = []
    search_cursor = 0

    def append_chunk(text: str, heading: str | None) -> None:
        nonlocal search_cursor
        if not text.strip():
            return
        char_start, char_end = _locate(full_text, text, search_cursor)
        search_cursor = char_end
        chunks.append(
            SourceChunk(
                source_revision_id=revision_id,
                workspace_id=workspace_id,
                chunk_index=len(chunks),
                text=text,
                char_start=char_start,
                char_end=char_end,
                line_start=_char_to_line(full_text, char_start),
                line_end=_char_to_line(full_text, char_end),
                section_heading=heading,
                embedding=None,
            )
        )

    def flush_buffer() -> None:
        nonlocal current_buffer
        append_chunk(_serialize_elements(current_buffer), current_heading)
        current_buffer = []

    for element in elements:
        is_heading = element.type in _HEADING_TYPES
        if is_heading:
            if current_buffer:
                flush_buffer()
            current_heading = element.text
            current_buffer = [element]
            continue

        elem_len = len(element.text)
        if current_buffer and _serialized_len([*current_buffer, element]) > MAX_CHUNK_CHARS:
            flush_buffer()

        if elem_len > MAX_CHUNK_CHARS:
            for sentence_chunk in _split_by_sentences(element.text, MAX_CHUNK_CHARS):
                append_chunk(sentence_chunk, current_heading)
        else:
            current_buffer.append(element)

    if current_buffer:
        flush_buffer()

    return chunks


def _serialize_elements(elements: list[DocumentElement]) -> str:
    parts: list[str] = []
    for element in elements:
        if not element.text.strip():
            continue
        if element.type == "heading_1":
            parts.append(f"# {element.text}")
        elif element.type == "heading_2":
            parts.append(f"## {element.text}")
        elif element.type == "heading_3":
            parts.append(f"### {element.text}")
        elif element.type == "list_item":
            parts.append(f"- {element.text}")
        elif element.type == "code":
            parts.append(f"```\n{element.text}\n```")
        else:
            parts.append(element.text)
    return "\n\n".join(parts)


def _serialized_len(elements: list[DocumentElement]) -> int:
    return len(_serialize_elements(elements))


def _split_by_sentences(text: str, max_chars: int) -> list[str]:
    sentences = [
        sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()
    ]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                sentence[index : index + max_chars] for index in range(0, len(sentence), max_chars)
            )
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _locate(full_text: str, text: str, cursor: int) -> tuple[int, int]:
    """Return (char_start, char_end) of *text* within *full_text*.

    Sentence-split chunks are stripped and rejoined with single spaces, so they
    are not always verbatim substrings of *full_text*. When an exact match fails
    we fall back to a whitespace-tolerant search (and finally to the cursor) so
    line offsets used for navigation stay anchored to the real document.
    """
    start = full_text.find(text, cursor)
    if start == -1:
        start = full_text.find(text)
    if start != -1:
        return start, start + len(text)

    tokens = text.split()
    if tokens:
        pattern = re.compile(r"\s+".join(re.escape(token) for token in tokens))
        match = pattern.search(full_text, cursor) or pattern.search(full_text)
        if match:
            return match.start(), match.end()

    return cursor, cursor + len(text)


def _char_to_line(text: str, offset: int) -> int:
    """Return 1-indexed line number for a character offset."""
    return text[:offset].count("\n") + 1
