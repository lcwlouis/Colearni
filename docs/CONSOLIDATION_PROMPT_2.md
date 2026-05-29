# Agent Prompt: Consolidation Item 2 — Phase 10 Parser Pipeline + Auto-Linking

## Context

Read `docs/CONSOLIDATION_PLAN.md` Item 2 before proceeding.

Phase 10 built upload-only storage. Files are saved to private object storage and a
`SourceRecord`/`SourceRevision` row is created with `parser_name="none"` and
`parser_status="pending"`. No parsing, chunking, or indexing ever happens. As a result,
Phase 11's retrieval service has no real data to search, and the tutor never uses uploaded
source content.

Your job is to implement the five-stage pipeline described in the architecture section of Item 2:
**Parser → CanonicalDocument (markdown) → Chunker (with line numbers) → Embedder → Linker**,
then wire it into the upload path. You also add the **Reranker stub** used by the retrieval
service.

---

## Mandatory reads before writing any code

- `docs/AGENTS.md` — repo rules, git policy, constraints.
- `docs/CODEX.md` — code standards.
- `docs/CONSOLIDATION_PLAN.md` Item 2 — full architecture, scope, acceptance criteria.
- `backend/app/services/source_ingestion.py` — `upload_private_source`, `PARSER_NAME`.
- `backend/app/services/concept_source_links.py` — `link_source_to_concept`.
- `backend/app/services/retrieval.py` — `search_sources_by_title` (extend or add text search).
- `backend/app/models/source.py` — `SourceRecord`, `SourceRevision`, `ConceptSourceLink`.
- `backend/app/api/sources.py` — upload route (add optional `trail_id` form field).
- `backend/app/models/graph.py` — `ConceptNode` model (used by linker to enumerate concepts).
- `backend/app/agents/llm_client.py` — provider routing pattern to follow for EmbeddingClient.
- `backend/app/settings.py` — existing settings pattern (pydantic-settings).
- `backend/alembic/` — migration pattern for adding new tables.
- `backend/tests/test_source_ingestion.py` — existing ingestion tests.
- `backend/tests/test_trail_pack_export.py` — export regression tests.
- `pyproject.toml` — dependency management (hatchling, optional extras).

---

## Exact changes required

### 1. Parser — `backend/app/services/parser.py` (new file)

Implement a `parse_source(data: bytes, content_type: str) -> CanonicalDocument` function.

```python
from dataclasses import dataclass, field
from typing import Literal

ElementType = Literal[
    "heading_1", "heading_2", "heading_3", "paragraph", "list_item", "code"
]

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
        """Markdown representation stored in SourceRevision.raw_text.

        Headings are serialized with # markers so read_document_section can
        return structured content to the LLM. Line numbers in this string are
        the navigation anchor for SourceChunk.line_start/line_end.
        """
        lines = []
        for e in self.elements:
            if not e.text.strip():
                continue
            if e.type == "heading_1":
                lines.append(f"# {e.text}")
            elif e.type == "heading_2":
                lines.append(f"## {e.text}")
            elif e.type == "heading_3":
                lines.append(f"### {e.text}")
            elif e.type == "list_item":
                lines.append(f"- {e.text}")
            elif e.type == "code":
                lines.append(f"```\n{e.text}\n```")
            else:  # paragraph
                lines.append(e.text)
        return "\n\n".join(lines)
```

Support the following `content_type` values:

- `"application/pdf"`: use `pdfplumber` (`import pdfplumber`). Open bytes via
  `pdfplumber.open(io.BytesIO(data))`, iterate pages, call `page.extract_text()`.
  Join page texts with `"\n\n"`, then split on `\n\n` (or runs of ≥2 blank lines) to produce
  `DocumentElement(type="paragraph", text=...)` objects. Strip leading/trailing whitespace
  from each; skip empty strings. Set `parser_name="pdfplumber"`.
  If pdfplumber raises, raise a descriptive `ValueError`.
  Heading detection via font size heuristics is deferred — all PDF elements are `"paragraph"` at MVP.

- `"text/markdown"`: decode bytes as UTF-8. Parse heading lines (`^#{1,3}\s+(.+)`) into
  `"heading_1"/"heading_2"/"heading_3"` elements. Remaining non-blank runs between headings
  become `"paragraph"` elements. Return with `parser_name="markdown"`.

- `"text/plain"`: decode bytes as UTF-8. Split on `\n\n` to produce `"paragraph"` elements.
  Return with `parser_name="plaintext"`.

- Any other content type: raise `ValueError(f"Unsupported content type: {content_type}")`.

The function must be synchronous (called from an async context via `asyncio.to_thread`).
Do not import `asyncio` inside this module.

Add `pdfplumber` to `pyproject.toml` dependencies (it is MIT-licensed). Check first — if
already present, do not add a duplicate. `pdfplumber` pulls in `pdfminer.six` as a transitive
dependency; do not add pdfminer.six separately.

### 2. SourceChunk model — `backend/app/models/source.py`

Add a `SourceChunk` SQLAlchemy model to the existing `source.py`.

The `embedding` column uses pgvector. Add `pgvector` as an optional dependency:
- In `pyproject.toml` add `pgvector>=0.3.0` to a new `[project.optional-dependencies]` entry
  named `"embedding"`. This keeps it opt-in for environments without the pgvector Postgres
  extension.
- Import `Vector` conditionally at the top of `source.py` with a graceful fallback:

```python
try:
    from pgvector.sqlalchemy import Vector as _Vector
    def _embedding_column(dim: int) -> sa.Column:
        return mapped_column(_Vector(dim), nullable=True)
except ImportError:
    # pgvector not installed; embedding column degrades to JSON array for non-Postgres envs
    def _embedding_column(dim: int) -> sa.Column:
        return mapped_column(JSON, nullable=True)
```

Use the default dimension from settings or a fallback constant:

```python
import os
_EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))
```

Model definition:

```python
class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_revisions.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    text: Mapped[str]
    char_start: Mapped[int]
    char_end: Mapped[int]
    line_start: Mapped[int]   # 1-indexed line in SourceRevision.raw_text
    line_end: Mapped[int]     # 1-indexed line in SourceRevision.raw_text
    section_heading: Mapped[str | None]  # nearest ancestor heading text, NULL if none
    embedding: Mapped[list[float] | None] = _embedding_column(_EMBEDDING_DIM)
```

Also import `SourceChunk` wherever `SourceRevision` is already imported so the mapper picks
it up.

### 3. Alembic migration for `source_chunks`

Create a new migration file in `backend/alembic/versions/`. Follow the naming convention of
existing migrations. The migration must:

- Execute `CREATE EXTENSION IF NOT EXISTS vector` (safe no-op if pgvector is not installed).
- Create the `source_chunks` table with all columns above.
- Add an index on `(source_revision_id)`.
- The `embedding` column: use raw SQL `op.execute("ALTER TABLE source_chunks ADD COLUMN
  embedding vector(1536)")` in a try/except that falls back to a JSON column if the vector
  type is unavailable. This ensures tests using SQLite or a Postgres instance without pgvector
  don't fail the migration.
- Include a `downgrade` that drops the table.

Use `op.execute` for the extension and vector column rather than SQLAlchemy type objects to
avoid a hard runtime dependency on the pgvector Python package in migrations.

### 4. Chunker — `backend/app/services/chunker.py` (new file)

Implement:
```python
def chunk_elements(
    elements: list[DocumentElement],
    revision_id: uuid.UUID,
    workspace_id: uuid.UUID,
    full_text: str,  # CanonicalDocument.text — used for line number computation
) -> list[SourceChunk]
```

This is a **structure-aware** chunker. Do NOT use a fixed-size sliding window.

Chunk parameters (configurable via env vars with these defaults):
- `MAX_CHUNK_CHARS`: int = 2000

**Algorithm**:

```
current_heading = None
current_buffer = []   # list of DocumentElement
current_chars = 0
chunks = []
char_cursor = 0       # tracks char_start for each chunk in the full_text

for each element in elements:
    is_heading = element.type in ("heading_1", "heading_2", "heading_3")

    if is_heading:
        # flush current buffer as a chunk (if non-empty)
        if current_buffer:
            chunks.append(build_chunk(current_buffer, current_heading, ...))
        # start fresh, this heading leads the next chunk
        current_heading = element.text
        current_buffer = [element]
        current_chars = len(element.text)
    else:
        elem_len = len(element.text)
        if current_chars + elem_len > MAX_CHUNK_CHARS and current_buffer:
            # overflow: flush first
            chunks.append(build_chunk(current_buffer, current_heading, ...))
            current_buffer = []
            current_chars = 0

        if elem_len > MAX_CHUNK_CHARS:
            # single oversized element: split by sentences
            for sentence_chunk in split_by_sentences(element.text, MAX_CHUNK_CHARS):
                chunks.append(build_single_text_chunk(sentence_chunk, current_heading, ...))
        else:
            current_buffer.append(element)
            current_chars += elem_len

# flush any remaining buffer
if current_buffer:
    chunks.append(build_chunk(current_buffer, current_heading, ...))
```

**`build_chunk`**: joins element texts using the same markdown serialization rules as
`CanonicalDocument.text` (headings as #/##/###, list_items as `-`, etc.). Sets `char_start`
and `char_end` by finding the chunk text's position in `full_text`. Sets `section_heading`
to `current_heading` (may be `None`).

**Line number computation**: after computing `char_start`/`char_end`, calculate:

```python
def _char_to_line(text: str, offset: int) -> int:
    """Return 1-indexed line number for a character offset."""
    return text[:offset].count('\n') + 1

chunk.line_start = _char_to_line(full_text, chunk.char_start)
chunk.line_end = _char_to_line(full_text, chunk.char_end)
```

`split_by_sentences`: split using `re.split(r'(?<=[.!?])\s+', text)`. Group sentences into
sub-chunks up to `MAX_CHUNK_CHARS` each.

The function is synchronous. It returns a list of unsaved `SourceChunk` ORM objects (not yet
added to any session). `chunk_index` is the 0-based position in the returned list.

Skip any chunk whose `.text.strip()` is empty after joining.

### 5. EmbeddingClient — `backend/app/agents/embedding_client.py` (new file)

Multi-provider embedding client following the same pattern as `LLMClient`:

```python
class EmbeddingClient:
    """Multi-provider embedding client using the OpenAI SDK with base_url overrides.

    All providers are routed through the openai AsyncOpenAI client, since OpenAI's
    SDK supports base_url overrides for any OpenAI-compatible endpoint. This covers:
    - OpenAI native (text-embedding-3-small, text-embedding-3-large, etc.)
    - Google Gemini (text-embedding-004 via OAI-compat endpoint)
    - Ollama local models (nomic-embed-text, mxbai-embed-large, etc.)
    - Any other OpenAI-compatible embedding endpoint

    When EMBEDDING_PROVIDER=disabled, embed() returns None and callers fall back
    to ILIKE search. This is the default — zero cost for deployments that don't
    configure an embedding provider.
    """

    @classmethod
    def from_settings(cls, settings: Settings) -> "EmbeddingClient": ...

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Return embedding vectors for each input text.

        Returns None when provider is disabled. Callers must handle None and
        fall back to ILIKE search.
        """
        ...
```

Provider routing (all via `openai.AsyncOpenAI`):

```python
EMBEDDING_PROVIDER_BASE_URLS: dict[str, str] = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "ollama": "http://localhost:11434/v1",
    # "openai" uses the default openai endpoint (no base_url needed)
    # "openai_compatible" uses EMBEDDING_API_BASE from settings
}
```

- `"disabled"`: `embed()` returns `None` immediately.
- `"openai"`: `AsyncOpenAI(api_key=...)`.
- `"gemini"`: `AsyncOpenAI(base_url=GEMINI_BASE, api_key=GEMINI_API_KEY)`.
- `"ollama"`: `AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")`.
- `"openai_compatible"`: `AsyncOpenAI(base_url=settings.embedding_api_base, api_key=settings.embedding_api_key)`.

Call:
```python
response = await client.embeddings.create(model=settings.embedding_model, input=texts)
return [item.embedding for item in response.data]
```

Add a `from_settings(cls, settings)` classmethod that constructs the right client
based on `settings.embedding_provider`.

### 6. Reranker stub — `backend/app/services/reranker.py` (new file)

```python
from dataclasses import dataclass

@dataclass
class ChunkSearchResult:
    """Chunk-level retrieval result with line navigation metadata.

    Used by search_sources_by_text and the reranker. The LLM uses
    source_revision_id + line_start to call read_document_section for
    full context window reads.
    """
    source_id: uuid.UUID
    source_revision_id: uuid.UUID
    source_title: str
    chunk_text: str
    section_heading: str | None
    line_start: int
    line_end: int
    similarity: float | None  # cosine similarity from vector search; None for ILIKE

class RerankerClient:
    """Pipeline stage for reranking chunk retrieval results.

    No-op by default (RERANKER_PROVIDER=none). The interface is defined now
    so Cohere Rerank or FlashRank can be plugged in without changing the
    retrieval pipeline shape (search → rerank → limit).

    Future providers:
    - cohere: Cohere Rerank API (cloud, ~$1/1000 queries)
    - flashrank: FlashRank MIT local model (~30ms, no API key needed)
    """

    @classmethod
    def from_settings(cls, settings: Settings) -> "RerankerClient": ...

    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Return candidates in reranked order. No-op returns input order."""
        return candidates
```

`ChunkSearchResult` is defined here and imported by `retrieval.py`. It is NOT a database
model — it is a pure data transfer object for the search → rerank → return pipeline.

### 7. New settings — `backend/app/settings.py`

Add to the `Settings` class:

```python
# Embedding provider — disabled by default; zero cost when not configured.
# ILIKE full-text search is used as fallback when disabled.
# Changing EMBEDDING_DIM after initial DB creation requires a new Alembic migration.
embedding_provider: str = "disabled"  # disabled | openai | gemini | ollama | openai_compatible
embedding_model: str = "text-embedding-3-small"  # model name for the chosen provider
embedding_api_key: str = ""           # API key; falls back to llm_api_key if same provider
embedding_api_base: str = ""          # base URL override for openai_compatible or ollama
embedding_dim: int = 1536             # vector dimension; must match model output

# Reranker — no-op by default. Interface stub ready for Cohere or FlashRank.
reranker_provider: str = "none"       # none | cohere | flashrank
reranker_api_key: str = ""            # API key for Cohere
```

### 8. Update `upload_private_source` — `backend/app/services/source_ingestion.py`

Change the function signature to accept an optional `trail_id`:

```python
async def upload_private_source(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    filename: str,
    content_type: str,
    data: bytes,
    trail_id: uuid.UUID | None = None,
) -> SourceUploadResponse:
```

After creating and flushing the `SourceRevision` row, add the pipeline:

```python
# Parse
try:
    doc = await asyncio.to_thread(parse_source, data, content_type)
    revision.raw_text = doc.text
    revision.parser_name = doc.parser_name
    revision.parser_status = "parsed"
except Exception as exc:
    revision.parser_status = "failed"
    revision.parser_error = str(exc)
    doc = None

# Chunk (only if parsed successfully)
if doc is not None:
    chunks = chunk_elements(doc.elements, revision.id, workspace_id, doc.text)
    session.add_all(chunks)
    await session.flush()  # ensure chunk IDs exist before embedding

    # Embed (only if provider is configured)
    embedding_client = EmbeddingClient.from_settings(settings)
    vectors = await embedding_client.embed([c.text for c in chunks])
    if vectors is not None:
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector

# Auto-link (only if trail_id provided and parsed)
if trail_id is not None and doc is not None:
    await auto_link_source_to_trail(session, revision.id, trail_id, workspace_id)
```

Import `parse_source` from `.parser`, `chunk_elements` from `.chunker`,
`EmbeddingClient` from `backend.app.agents.embedding_client`,
`auto_link_source_to_trail` from `.concept_source_links`.

Keep `PARSER_NAME = "none"` as a module-level constant for reference but stop using it
for `SourceRevision` construction — the parser sets the name dynamically.

### 9. Auto-linker — add to `backend/app/services/concept_source_links.py`

Add:

```python
async def auto_link_source_to_trail(
    session: AsyncSession,
    source_revision_id: uuid.UUID,
    trail_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
```

Algorithm:
1. Load all `SourceChunk` rows for `source_revision_id` (just their `.text` fields).
2. Load all `ConceptNode` rows for `trail_id`.
3. Concatenate all chunk texts into one lowercase string (`full_text`).
4. For each concept: if `concept.title.lower()` appears in `full_text`, call
   `link_source_to_concept(...)` with the concept's `source_id` (the `SourceRecord` linked to
   the revision) and `relation="supplementary"`. The existing function already skips duplicates.
5. Commit is the caller's responsibility — do not commit inside this function.

Resolve `source_id` from `source_revision_id`:
```python
revision = await session.get(SourceRevision, source_revision_id)
source_id = revision.source_id
```

### 10. Upload route — `backend/app/api/sources.py`

Add an optional `trail_id` form field:

```python
trail_id: uuid.UUID | None = Form(default=None),
```

Pass it to `upload_private_source`. The field is optional — existing upload calls without
`trail_id` still work.

### 11. Text search — `backend/app/services/retrieval.py`

Add:

```python
async def search_sources_by_text(
    query: str,
    workspace_id: uuid.UUID,
    session: AsyncSession,
    limit: int = 10,
    reranker: RerankerClient | None = None,
) -> list[ChunkSearchResult]:
```

Implementation:

1. If embedding is available (call `EmbeddingClient.from_settings(settings).embed([query])`
   and result is not None), use pgvector cosine similarity:
   ```python
   stmt = (
       select(SourceRecord, SourceRevision, SourceChunk,
              SourceChunk.embedding.cosine_distance(query_vector).label("distance"))
       .join(SourceRevision, ...)
       .join(SourceChunk, ...)
       .where(
           SourceRecord.workspace_id == workspace_id,
           SourceChunk.embedding.is_not(None),
       )
       .order_by("distance")
       .limit(limit)
   )
   ```
   Map distance to similarity: `similarity = 1.0 - distance`.

2. Fallback (when embedding is disabled or query embedding fails): ILIKE against
   `SourceChunk.text`:
   ```python
   stmt = (
       select(SourceRecord, SourceRevision, SourceChunk)
       .join(SourceRevision, SourceRevision.source_id == SourceRecord.id)
       .join(SourceChunk, SourceChunk.source_revision_id == SourceRevision.id)
       .where(
           SourceRecord.workspace_id == workspace_id,
           SourceChunk.text.ilike(f"%{query}%"),
       )
       .distinct()
       .limit(limit)
   )
   ```
   Set `similarity=None` in results.

3. Map rows to `ChunkSearchResult` objects.
4. Apply reranker: `results = (reranker or RerankerClient()).rerank(query, results)`.
5. Return results.

`ChunkSearchResult` is imported from `backend.app.services.reranker`.

### 12. Export safety

Open `backend/app/services/trail_pack_export.py` (or wherever Trail Pack export is
implemented). Confirm that `SourceChunk` rows are not included in the export. If `SourceChunk`
is not referenced at all, add a comment:

```python
# SourceChunk rows are intentionally excluded from Trail Pack export (private content).
# Chunk embeddings are also excluded — they are private workspace artifacts.
```

---

## Tests

### New unit tests — `backend/tests/test_parser.py`

```
- parse_source("application/pdf") returns CanonicalDocument with parser_name="pdfplumber"
  for a minimal valid PDF bytes value; elements list may be empty but must not raise
- parse_source("text/plain") returns paragraph elements from double-newline-separated text
- parse_source("text/markdown") returns heading + paragraph elements; heading type matches
  #-count (# → heading_1, ## → heading_2, ### → heading_3)
- parse_source("text/markdown") CanonicalDocument.text re-serializes headings as # markers
- parse_source raises ValueError for unsupported content type
```

Minimal valid PDF bytes for tests (pdfplumber returns empty text for this; no raise expected):
```python
PDF_BYTES = (
    b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\n0000000115 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
)
```

### New unit tests — `backend/tests/test_chunker.py`

```
- plain paragraph elements shorter than MAX_CHUNK_CHARS → exactly one chunk
- multiple paragraphs that collectively exceed MAX_CHUNK_CHARS → multiple chunks;
  no chunk exceeds MAX_CHUNK_CHARS
- heading element flushes current buffer: elements [para_a, heading_x, para_b] produce two
  chunks (para_a alone; heading_x + para_b together)
- section_heading is set on chunks that follow a heading element; NULL on chunks before any heading
- single oversized paragraph element → split by sentences, each sub-chunk ≤ MAX_CHUNK_CHARS
- empty elements list → zero chunks
- line_start and line_end are set on every chunk and are ≥ 1
- line_start < line_end for multi-line chunks; line_start == line_end for single-line chunks
```

### New unit tests — `backend/tests/test_embedding_client.py`

```
- EmbeddingClient with EMBEDDING_PROVIDER=disabled returns None from embed()
- EmbeddingClient.from_settings builds correct client for each provider
  (mock the openai AsyncOpenAI call; verify base_url is set correctly for gemini/ollama)
```

### New unit tests — `backend/tests/test_reranker.py`

```
- RerankerClient(provider="none").rerank(query, candidates) returns candidates unchanged
- ChunkSearchResult is constructable with all required fields
```

### Integration tests — `backend/tests/test_source_ingestion.py`

Add to the existing test file:

```
- upload_private_source with PDF bytes sets parser_status="parsed" and raw_text non-empty
  (mock parse_source to return a CanonicalDocument to avoid pdfplumber dep in CI)
- upload_private_source with unsupported type sets parser_status="failed"
- upload_private_source with trail_id calls auto_link_source_to_trail
  (mock the linker; assert it was called with correct args)
- upload_private_source calls EmbeddingClient.embed when provider is configured
  (mock EmbeddingClient; assert embed() is called with chunk texts)
- upload_private_source skips embedding when EMBEDDING_PROVIDER=disabled
  (no embed() call expected)
```

### Export regression — `backend/tests/test_trail_pack_export.py`

Add an assertion that the Trail Pack export output does not contain any `source_chunks` key
or `embedding` key:

```python
export_json = json.dumps(export_result)
assert "source_chunks" not in export_json
assert "embedding" not in export_json
```

---

## Verification

```bash
# Backend tests
python -m pytest backend/tests/ -q

# Ruff lint (pre-existing failures in logging_config.py and models/conversation.py are known)
python -m ruff check backend/app/

# Frontend is unchanged — no tsc or vitest run needed for this item
```

All 349+ existing backend tests must still pass. The lint run should show no new errors
beyond the 7 known pre-existing ones.

---

## Constraints

- Do **not** commit or push. Stop after implementing and verifying. The user will review.
- FastAPI routes must stay thin — no business logic in the route handler.
- The chunker must not import any tokeniser or ML model. Structure detection uses only regex
  and string operations.
- Auto-link uses keyword substring matching only — no LLM calls, no embedding calls.
- Do not modify any frontend file.
- Do not break Trail Pack export (no chunk content or embeddings should appear in exports).
- pgvector column must be nullable — chunks with failed or skipped embedding have NULL.
- The migration must not fail on Postgres instances without the pgvector extension (use
  `CREATE EXTENSION IF NOT EXISTS vector` and handle the fallback).
- `EmbeddingClient` must use the OpenAI SDK with `base_url` overrides — do not introduce
  google-generativeai, requests, or other HTTP clients. The openai SDK already supports
  all four providers via `base_url`.

---

## Deliverable

When done, report:

1. Which files were changed or created, with a one-line summary of each.
2. Backend test count (must be 349+, likely higher after new tests).
3. Ruff output (pre-existing errors are fine; no new errors).
4. Any decisions or edge cases (e.g., how you handled the migration fallback, line number
   computation, embedding provider test mocking).
5. Any scope that was not completed and why.

The user will review before any commit is made.
