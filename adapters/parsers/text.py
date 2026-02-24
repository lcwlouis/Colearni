"""Text and markdown parsing helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_MARKDOWN_EXTENSIONS = {".md"}
_TEXT_EXTENSIONS = {".txt"}
_MARKDOWN_MIME_TYPES = {"text/markdown"}
_TEXT_MIME_TYPES = {"text/plain"}


class UnsupportedTextDocumentError(ValueError):
    """Raised when payload type is not supported for text ingestion."""


@dataclass(frozen=True)
class ParsedTextDocument:
    """Normalized representation of a text-based payload."""

    normalized_text: str
    mime_type: str
    filename: str | None


def normalize_text(text: str) -> str:
    """Normalize input text into a deterministic canonical form."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")

    # Keep printable characters plus tab/newline; drop other control chars.
    normalized = "".join(
        char for char in normalized if char in {"\n", "\t"} or ord(char) >= 32
    )

    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def parse_text_payload(
    *,
    raw_bytes: bytes,
    filename: str | None,
    content_type: str | None,
) -> ParsedTextDocument:
    """Parse and normalize a markdown/text payload."""
    mime_type = _resolve_mime_type(filename=filename, content_type=content_type)
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedTextDocumentError(
            "Only UTF-8 encoded .md/.txt payloads are supported."
        ) from exc

    normalized = normalize_text(decoded)
    return ParsedTextDocument(
        normalized_text=normalized,
        mime_type=mime_type,
        filename=filename,
    )


def _resolve_mime_type(*, filename: str | None, content_type: str | None) -> str:
    """Resolve canonical MIME type from either filename extension or content-type."""
    extension = _file_extension(filename)
    canonical_content_type = _canonical_content_type(content_type)

    if extension in _MARKDOWN_EXTENSIONS:
        return "text/markdown"
    if extension in _TEXT_EXTENSIONS:
        return "text/plain"

    if canonical_content_type in _MARKDOWN_MIME_TYPES:
        return "text/markdown"
    if canonical_content_type in _TEXT_MIME_TYPES:
        return "text/plain"

    raise UnsupportedTextDocumentError("Only .md and .txt documents are supported.")


def _file_extension(filename: str | None) -> str | None:
    if not filename:
        return None
    return os.path.splitext(filename)[1].lower()


def _canonical_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", maxsplit=1)[0].strip().lower()
