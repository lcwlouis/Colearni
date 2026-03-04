"""Text, markdown, and PDF parsing helpers."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

logger = logging.getLogger(__name__)

_MARKDOWN_EXTENSIONS = {".md"}
_TEXT_EXTENSIONS = {".txt"}
_PDF_EXTENSIONS = {".pdf"}
_MARKDOWN_MIME_TYPES = {"text/markdown"}
_TEXT_MIME_TYPES = {"text/plain"}
_PDF_MIME_TYPES = {"application/pdf"}


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
    """Parse and normalize a markdown/text/PDF payload."""
    mime_type = _resolve_mime_type(filename=filename, content_type=content_type)
    if mime_type == "application/pdf":
        decoded = _extract_pdf_text(raw_bytes)
    else:
        try:
            decoded = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedTextDocumentError(
                "Only UTF-8 encoded .md/.txt payloads are supported."
            ) from exc

    normalized = normalize_text(decoded)
    if decoded:
        before_len = len(decoded)
        after_len = len(normalized)
        logger.info(
            "Text normalization: %d chars → %d chars (%.1f%% retained)",
            before_len, after_len,
            (after_len / before_len * 100) if before_len else 0,
        )
    return ParsedTextDocument(
        normalized_text=normalized,
        mime_type=mime_type,
        filename=filename,
    )


def _extract_pdf_text(raw_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(raw_bytes))
    except Exception as exc:
        raise UnsupportedTextDocumentError(
            "Failed to parse PDF payload. Ensure the file is a valid, unencrypted PDF."
        ) from exc

    page_count = len(reader.pages)
    page_texts: list[str] = []
    total_chars = 0

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        char_count = len(text)
        total_chars += char_count
        if not text:
            logger.warning("PDF page %d/%d returned no extractable text", page_num + 1, page_count)
        page_texts.append(text)

    avg_chars = total_chars / page_count if page_count else 0
    logger.info(
        "PDF text extraction: %d pages, %d total chars, %.0f avg chars/page",
        page_count, total_chars, avg_chars,
    )
    if page_count and avg_chars < 100:
        logger.warning(
            "Suspiciously low text yield from PDF: %d pages but only %.0f avg chars/page "
            "(expected ≥100). The PDF may be image-based or have non-extractable text.",
            page_count, avg_chars,
        )

    return "\n\n".join(page_texts)


def _resolve_mime_type(*, filename: str | None, content_type: str | None) -> str:
    """Resolve canonical MIME type from either filename extension or content-type."""
    extension = _file_extension(filename)
    canonical_content_type = _canonical_content_type(content_type)

    if extension in _MARKDOWN_EXTENSIONS:
        return "text/markdown"
    if extension in _TEXT_EXTENSIONS:
        return "text/plain"
    if extension in _PDF_EXTENSIONS:
        return "application/pdf"

    if canonical_content_type in _MARKDOWN_MIME_TYPES:
        return "text/markdown"
    if canonical_content_type in _TEXT_MIME_TYPES:
        return "text/plain"
    if canonical_content_type in _PDF_MIME_TYPES:
        return "application/pdf"

    raise UnsupportedTextDocumentError("Only .md, .txt, and .pdf documents are supported.")


def _file_extension(filename: str | None) -> str | None:
    if not filename:
        return None
    return os.path.splitext(filename)[1].lower()


def _canonical_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", maxsplit=1)[0].strip().lower()
