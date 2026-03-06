# OCR1 — Page Analysis Infrastructure

Parent: `docs/OCR_MASTER_PLAN.md`

## Purpose

Add the foundation for detecting and rendering visual content from PDF pages. This track introduces PyMuPDF for page-to-image rendering, implements per-page image detection via pypdf's XObject resource inspection, and creates a utility module for page classification.

## Slices

### OCR1.1 — Add PyMuPDF dependency

**What:** Add `pymupdf` to `pyproject.toml` dependencies and verify installation.

**Steps:**
1. Add `"pymupdf>=1.25.0,<2.0.0"` to `pyproject.toml` under `[project] dependencies`
2. Run `uv sync` or `pip install -e .` to verify installation
3. Verify `import pymupdf` works

**Exit criteria:**
- `pymupdf` appears in `pyproject.toml`
- `python -c "import pymupdf; print(pymupdf.__version__)"` succeeds

---

### OCR1.2 — Create pdf_vision.py utilities

**What:** Create `adapters/parsers/pdf_vision.py` with image detection and page rendering.

**Steps:**
1. Create dataclasses:
   ```python
   @dataclass(frozen=True)
   class PageVisualInfo:
       page_index: int
       image_count: int
       text_char_count: int

   @dataclass(frozen=True)
   class PageImage:
       page_index: int
       base64_png: str
       width: int
       height: int
   ```

2. Implement `detect_visual_pages(raw_bytes: bytes) -> list[PageVisualInfo]`:
   - Use `pypdf.PdfReader` to iterate pages
   - For each page, count XObject images via `page["/Resources"].get("/XObject", {})`
   - Filter for XObjects with `/Subtype == /Image`
   - Also extract text char count via `page.extract_text()`
   - Return list of PageVisualInfo for all pages

3. Implement `render_pages_to_images(raw_bytes: bytes, page_indices: Sequence[int], *, dpi: int = 150) -> list[PageImage]`:
   - Open PDF with `pymupdf.open(stream=raw_bytes, filetype="pdf")`
   - For each requested page index, render with `page.get_pixmap(dpi=dpi)`
   - Convert pixmap to PNG bytes via `pixmap.tobytes("png")`
   - Base64 encode the PNG bytes
   - Return list of PageImage
   - Handle out-of-range page indices gracefully (skip with warning log)

**Exit criteria:**
- Both functions handle empty PDFs, single-page PDFs, and multi-page PDFs
- `render_pages_to_images` produces valid base64 PNG strings
- Out-of-range indices are handled without crash

---

### OCR1.3 — Page classification

**What:** Add `classify_pages()` that combines text extraction and image detection.

**Steps:**
1. Define enum:
   ```python
   class PageType(str, Enum):
       TEXT_ONLY = "text_only"
       MIXED = "mixed"
       VISUAL_ONLY = "visual_only"
   ```

2. Define result dataclass:
   ```python
   @dataclass(frozen=True)
   class PageClassification:
       pages: list[tuple[int, PageType]]
       visual_page_indices: list[int]  # convenience: mixed + visual_only
       total_pages: int
   ```

3. Implement `classify_pages(raw_bytes: bytes, *, text_threshold: int = 100) -> PageClassification`:
   - Call `detect_visual_pages()` to get per-page info
   - Classification rules:
     - `text_threshold` chars AND no images → `TEXT_ONLY`
     - `text_threshold` chars AND has images → `MIXED`
     - `< text_threshold` chars (regardless of images) → `VISUAL_ONLY`
   - Build `visual_page_indices` as pages that are MIXED or VISUAL_ONLY

**Exit criteria:**
- Correctly classifies text-only, mixed, and visual-only pages
- `visual_page_indices` is the union of mixed and visual_only
- Works with 0-page PDFs (returns empty classification)

## Audit Workspace

(Initially empty — populated during self-audit phase)
