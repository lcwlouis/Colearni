import io
import re
from dataclasses import dataclass
from typing import Literal

ElementType = Literal["heading_1", "heading_2", "heading_3", "paragraph", "list_item", "code"]


@dataclass
class DocumentElement:
    type: ElementType
    text: str


@dataclass
class CanonicalDocument:
    elements: list[DocumentElement]
    parser_name: str

    @property
    def text(self) -> str:
        """Markdown representation stored in SourceRevision.raw_text."""
        lines = []
        for element in self.elements:
            if not element.text.strip():
                continue
            if element.type == "heading_1":
                lines.append(f"# {element.text}")
            elif element.type == "heading_2":
                lines.append(f"## {element.text}")
            elif element.type == "heading_3":
                lines.append(f"### {element.text}")
            elif element.type == "list_item":
                lines.append(f"- {element.text}")
            elif element.type == "code":
                lines.append(f"```\n{element.text}\n```")
            else:
                lines.append(element.text)
        return "\n\n".join(lines)


def parse_source(
    data: bytes,
    content_type: str,
    filename: str | None = None,
) -> CanonicalDocument:
    fmt = _resolve_format(content_type, filename)
    if fmt == "pdf":
        return _parse_pdf(data)
    if fmt == "markdown":
        return _parse_markdown(data)
    if fmt == "plaintext":
        return _parse_plaintext(data)
    raise ValueError(
        f"Unsupported source format (content_type={content_type!r}, filename={filename!r})"
    )


# Content types are matched on their bare media type (parameters like
# "; charset=utf-8" are stripped) and fall back to the filename extension,
# because browsers frequently send parameters or misreport text uploads as
# application/octet-stream.
_CONTENT_TYPE_FORMATS: dict[str, str] = {
    "application/pdf": "pdf",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "text/plain": "plaintext",
}
_EXTENSION_FORMATS: dict[str, str] = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".txt": "plaintext",
    ".text": "plaintext",
}


def _resolve_format(content_type: str, filename: str | None) -> str | None:
    bare_type = (content_type or "").split(";", 1)[0].strip().lower()
    fmt = _CONTENT_TYPE_FORMATS.get(bare_type)
    if fmt is not None:
        return fmt
    if filename:
        from pathlib import Path

        return _EXTENSION_FORMATS.get(Path(filename).suffix.lower())
    return None


def _parse_pdf(data: bytes) -> CanonicalDocument:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        raise ValueError(f"PDF parsing failed: {exc}") from exc

    text = "\n\n".join(page_texts)
    return CanonicalDocument(
        elements=_paragraph_elements(text),
        parser_name="pdfplumber",
    )


def _parse_markdown(data: bytes) -> CanonicalDocument:
    text = data.decode("utf-8")
    elements: list[DocumentElement] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        paragraph = "\n".join(paragraph_lines).strip()
        if paragraph:
            elements.append(DocumentElement(type="paragraph", text=paragraph))
        paragraph_lines.clear()

    for line in text.splitlines():
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            elements.append(DocumentElement(type=f"heading_{level}", text=heading.group(2).strip()))
        elif line.strip():
            paragraph_lines.append(line.strip())
        else:
            flush_paragraph()
    flush_paragraph()

    return CanonicalDocument(elements=elements, parser_name="markdown")


def _parse_plaintext(data: bytes) -> CanonicalDocument:
    text = data.decode("utf-8")
    return CanonicalDocument(elements=_paragraph_elements(text), parser_name="plaintext")


def _paragraph_elements(text: str) -> list[DocumentElement]:
    return [
        DocumentElement(type="paragraph", text=part.strip())
        for part in re.split(r"\n\s*\n+", text)
        if part.strip()
    ]
