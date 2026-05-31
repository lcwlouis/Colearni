# Consolidation Plan: Closing Phase 10–12 Gaps

## Why This Exists

After completing Phases 10, 11, and 12, a review identified a consistent pattern across all three:

- The backend service and API were implemented correctly.
- The frontend never called the new endpoints.
- The harder backend pieces (parser pipeline, LLM tool calling loop) were deferred each time.

Left unresolved, these compound. Phase 13+ will continue building on a foundation that looks
complete in the plan but is not wired up for users. The demo path (Phase 17) requires all three
items to work end-to-end.

This document tracks the three consolidation items that must be resolved before Phase 13 begins.

---

## Item 1: Phase 12 UI — Frontend Recommendation Consumption

**Status: complete**

### Problem

`GET /api/workspaces/{workspace_id}/trails/{trail_id}/next` was built in Phase 12 but is called
by nothing in the frontend. The dashboard and Trail detail page compute recommendations entirely
client-side using `apps/web/lib/recommendation.ts:pickRecommendedConcept`, which duplicates
the backend heuristic. The two can silently diverge.

### What exists

- Backend: `backend/app/services/recommendation.py`, `GET /{trail_id}/next` route in
  `backend/app/api/trails.py`, `NextConceptResponse` schema in `backend/app/schemas/trail.py`.
- Frontend client-side heuristic: `apps/web/lib/recommendation.ts` — `pickRecommendedConcept`
  and `summarizeTrail`.
- Dashboard renders "Recommended next concept" at `apps/web/app/page.tsx:252–274` using the
  client-side result.
- No call to `/trails/{trail_id}/next` exists anywhere in the frontend.

### Scope

1. Add `getTrailNext(workspaceId, trailId)` to `apps/web/lib/api.ts`.
2. In `apps/web/app/page.tsx`: fetch `getTrailNext()` alongside `getTrail()` in the existing
   parallel fetch; replace `pickRecommendedConcept` result with the backend response for the
   "Recommended next concept" section.
3. On the Trail detail page (`apps/web/app/trails/[id]/page.tsx`) or its graph panel: expose the
   backend recommendation as a visible prompt — e.g., a "Focus on next" indicator or a
   recommended-concept highlight that deep-links to `?concept=<id>`.
4. Remove or stub `pickRecommendedConcept` from `lib/recommendation.ts`. Keep `summarizeTrail`
   (it computes progress percentages and mastery counts from already-loaded Trail data — separate
   from the recommendation itself).
5. Add or update frontend tests for the new API call and rendering.
6. Update `docs/CURRENT_VARIANT.md` deferred list to mark Phase 12 UI as complete.
7. Update `docs/REBUILD_PLAN.md` Phase 12 status line.

### Acceptance criteria

- The dashboard's "Recommended next concept" uses the backend response, not the client heuristic.
- The Trail detail view surfaces the recommendation (concept title + reason) from the backend.
- `pickRecommendedConcept` is removed from the client-side codebase.
- 349+ backend tests still pass; frontend tests pass.

---

## Item 2: Phase 10 Parser Pipeline — At Least One Format + Auto-Linking

**Status: complete**

Implemented end-to-end: `parser.py` (PDF via pdfplumber, markdown, plaintext; content-type is
matched on its bare media type and falls back to the filename extension), `chunker.py`
(heading-aware buffering + sentence splitting with whitespace-tolerant line anchoring),
`SourceChunk` model + migration `0011` (vector column sized from `EMBEDDING_DIM`),
`EmbeddingClient` (best-effort: provider/network failures leave embeddings NULL and fall back to
ILIKE), the `trail_id` upload field, and `auto_link_source_to_trail` (concept title match).
Note: the model/ingestion fields are named `status` / `error_message` (not the
`parser_status` / `parser_error` used in the prose below).

### Problem

Phase 10 implemented upload-only storage: files are saved to private object storage and a
`SourceRecord`/`SourceRevision` row is created with `parser_name="none"`. No parsing,
canonicalisation, chunking, or indexing happens. Phase 11's retrieval service therefore has
no real data to search. The tutor never uses uploaded source content because there is nothing
to retrieve from.

Additionally, `link_source_to_concept` is a fully manual call — uploading a file creates no
automatic connection to any concept or trail. Users must manually link each source to each
concept after upload, which kills the upload UX in practice.

### What exists

- Upload API and private object storage: `backend/app/api/sources.py`,
  `backend/app/services/source_ingestion.py`.
- `SourceRevision` model with `parser_name`, `parser_version`, `parser_status`, `raw_text`,
  `parser_error` fields.
- Manual linking service: `backend/app/services/concept_source_links.py` —
  `link_source_to_concept`.
- Retrieval service: `backend/app/services/retrieval.py` — `get_concept_sources_for_tutor`,
  `get_graph_neighbourhood`, `search_sources_by_title`.
- No parser implementation; `parser_status` is always `"pending"` after upload.
- No auto-linking; upload accepts only `workspace_id` + file, no `trail_id`.

### Architecture

The parser pipeline is layered so that multimodal formats (images, tables, audio transcripts)
can be added later without restructuring:

```
Upload → Parser (format-specific) → CanonicalDocument (typed elements + markdown text)
       → Chunker (structure-aware, section-boundary, line-number tracking) → SourceChunk rows
       → Embedder (multi-provider EmbeddingClient) → embedding vectors on SourceChunk rows
       → Linker (keyword substring matching) → ConceptSourceLink rows
```

Each stage is a pure function or thin async wrapper. The route and ingestion service stay thin.

**Parser layer** — format-specific, returns `CanonicalDocument` with a typed `elements` list:

```python
@dataclass
class DocumentElement:
    type: str   # "heading_1" | "heading_2" | "heading_3" | "paragraph" | "list_item" | "code"
    text: str

@dataclass
class CanonicalDocument:
    elements: list[DocumentElement]
    parser_name: str

    @property
    def text(self) -> str:
        """Markdown representation stored in SourceRevision.raw_text.

        Headings are serialized with # markers so the LLM can read structured
        sections via read_document_section. Line numbers in raw_text are the
        navigation anchor for SourceChunk.line_start/line_end.
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

`raw_text` is the markdown representation. The LLM reads from it via `read_document_section`
(Item 3). Storing markdown rather than flat text preserves heading structure, which the LLM
can use to navigate and understand document context.

Format-specific element extraction:
- **PDF** (`pdfplumber`, MIT): extract text page by page, use basic font-size heuristics where
  available, split on `\n\n` or ≥2 blank lines to produce `"paragraph"` elements. pdfplumber
  is preferred over pdfminer.six because it exposes font metadata and image bounding boxes,
  enabling richer heading detection and future image placeholder insertion (Phase 17). All
  elements are `"paragraph"` currently; heading detection via font sizes is deferred.
- **Markdown** (`text/markdown`): regex-based heading detection (`^#{1,3}\s+`), then paragraph
  splitting. Produces `"heading_1"/"heading_2"/"heading_3"` + `"paragraph"` elements.
- **Plain text** (`text/plain`): paragraph detection only (split on `\n\n`). All `"paragraph"`.
- **DOCX / PPTX**: deferred to second pass (`python-docx`, `python-pptx`, both MIT). DOCX has
  native style names that map directly to element types — clean to add later.

**Chunker layer** — structure-aware, respects document hierarchy. No fixed-size sliding window.

Primary strategy: flush a chunk at **heading boundaries**. Each heading element starts a new
chunk; all content under it accumulates until the next heading.

Overflow strategy: if adding the next paragraph would push the current chunk over `MAX_CHUNK_CHARS`,
flush first. Never cut in the middle of a `paragraph` or `list_item` element.

Fallback: if a **single element** exceeds `MAX_CHUNK_CHARS` on its own, split it on sentence
boundaries (`(?<=[.!?])\s+`), grouping sentences until the cap.

Each `SourceChunk` row stores: `source_revision_id`, `workspace_id`, `chunk_index`, `text`,
`char_start`, `char_end`, `line_start`, `line_end`, `section_heading` (nearest ancestor heading
text, or `NULL`), and `embedding` (nullable pgvector column for similarity search).

`line_start`/`line_end` are 1-indexed line numbers in `SourceRevision.raw_text`. They are
computed from `char_start`/`char_end` by counting newlines in the full markdown text:

```python
def char_to_line(text: str, offset: int) -> int:
    return text[:offset].count('\n') + 1  # 1-indexed
```

This metadata lets the LLM navigate directly: `search_sources` returns `line_start` for any
matching chunk; the LLM can then call `read_document_section(revision_id, line_start)` to
read the surrounding context window from `raw_text`.

`MAX_CHUNK_CHARS` default: 2 000. Configurable via env var.

**Embedder stage** — runs after chunking, before auto-linking:
- Calls `EmbeddingClient.embed(texts)` for all chunk texts in one batch call.
- Stores returned vectors in `SourceChunk.embedding` (pgvector `vector(dim)` column).
- If `EMBEDDING_PROVIDER=disabled` (the default), embedding is skipped; `embedding` stays NULL.
- `EMBEDDING_DIM` controls the vector dimension (default: 1536). Changing this after initial
  migration requires a new Alembic migration to ALTER the column type.

**EmbeddingClient** — multi-provider, all routed through the OpenAI SDK (same pattern as
`LLMClient`) since OpenAI's SDK supports `base_url` overrides for any OpenAI-compatible
endpoint:

| `EMBEDDING_PROVIDER` | Routing | Notes |
|---|---|---|
| `disabled` | no-op (returns None) | Default; ILIKE fallback used for search |
| `openai` | openai SDK (default endpoint) | Recommended default when enabled |
| `gemini` | openai SDK + Google OAI-compat base URL | Uses `text-embedding-004` by default |
| `ollama` | openai SDK + `http://localhost:11434/v1` | Local; any Ollama embedding model |
| `openai_compatible` | openai SDK + `EMBEDDING_API_BASE` | Any OAI-compatible endpoint |

Settings:

```
EMBEDDING_PROVIDER     disabled | openai | gemini | ollama | openai_compatible
EMBEDDING_MODEL        model name (default: text-embedding-3-small)
EMBEDDING_API_KEY      API key (optional: falls back to LLM_API_KEY if same provider)
EMBEDDING_API_BASE     base URL override (required for openai_compatible; used by ollama)
EMBEDDING_DIM          vector dimension, must match model output (default: 1536)
```

**Reranker stage** — optional pipeline step between chunk retrieval and result delivery:

```
search_sources_by_text → [reranker.rerank(query, candidates)] → limit → return
```

The reranker is a no-op by default (`RERANKER_PROVIDER=none`). The interface is defined now
so that Cohere Rerank or FlashRank (MIT, local) can be plugged in without changing the
retrieval pipeline shape. A no-op that returns input order imposes no cost or latency.

```
RERANKER_PROVIDER      none (default) | cohere | flashrank
RERANKER_API_KEY       API key for Cohere (not needed for none/flashrank)
```

**Linker layer** — auto-creates `ConceptSourceLink` rows when `trail_id` is provided at upload:
- For every concept in the trail, check if the concept's `title` or `description` appears in
  any chunk (case-insensitive substring match). If yes → link with `link_type="supplementary"`.
- This is basic keyword linking. When embeddings are enabled, similarity-based candidate
  generation is possible but is deferred to Phase 17 (after the embedding pipeline is proven
  in production).
- Linker runs only when upload includes `trail_id`. Without it, no auto-links are created.
- Linker respects existing manual links — no duplicate `ConceptSourceLink` rows.

**`search_sources_by_text`** — returns `ChunkSearchResult` objects (not bare `SourceRecord`
rows) so the LLM receives chunk-level navigation metadata:

```python
@dataclass
class ChunkSearchResult:
    source_id: uuid.UUID
    source_revision_id: uuid.UUID
    source_title: str
    chunk_text: str          # the matching chunk text (capped for context)
    section_heading: str | None
    line_start: int          # navigation anchor for read_document_section
    line_end: int
    similarity: float | None # cosine similarity from vector search; None for ILIKE
```

When `EMBEDDING_PROVIDER != disabled`, search uses pgvector cosine similarity. When disabled
or when embedding is NULL, falls back to ILIKE. Both paths return the same `ChunkSearchResult`
shape. The reranker receives this list and returns it reordered (no-op by default).

### Scope

1. **Parser**: implement `parse_source(data: bytes, content_type: str) -> CanonicalDocument`
   in `backend/app/services/parser.py`. Support `application/pdf` (via `pdfplumber`),
   `text/plain`, and `text/markdown`. Each format produces typed `DocumentElement` objects.
   `CanonicalDocument.text` returns the markdown representation (headings as #/##/###).
   Store `doc.text` in `SourceRevision.raw_text`. Set `parser_name` dynamically,
   `parser_status="parsed"` on success, `"failed"` + `parser_error` on error.

2. **Chunker + SourceChunk model**: implement
   `chunk_elements(elements, revision_id, workspace_id, full_text) -> list[SourceChunk]`
   in `backend/app/services/chunker.py`. The chunker receives `full_text` (the markdown
   string from `CanonicalDocument.text`) to compute `line_start`/`line_end` from
   `char_start`/`char_end`. Add `SourceChunk` SQLAlchemy model and Alembic migration.
   Each row: `id`, `source_revision_id`, `workspace_id`, `chunk_index`, `text`,
   `char_start`, `char_end`, `line_start`, `line_end`, `section_heading` (nullable),
   `embedding` (nullable `vector(EMBEDDING_DIM)`).

3. **EmbeddingClient**: implement `backend/app/agents/embedding_client.py`. Multi-provider
   (OpenAI, Gemini, Ollama, OpenAI-compatible), all via OpenAI SDK + `base_url`. No-op when
   `EMBEDDING_PROVIDER=disabled`. `embed(texts: list[str]) -> list[list[float]] | None`.

4. **Reranker stub**: implement `backend/app/services/reranker.py`. No-op default
   (`RERANKER_PROVIDER=none`). Interface: `rerank(query, candidates) -> candidates`.

5. **Upload route change**: accept an optional `trail_id` form field in
   `backend/app/api/sources.py`. Pass it through to `upload_private_source`.

6. **Update `upload_private_source`**: parse → chunk → embed → auto-link pipeline. Accept
   optional `trail_id`. Call `EmbeddingClient` for chunk embeddings after chunking.

7. **Linker**: implement `auto_link_source_to_trail(session, source_revision_id, trail_id)`
   in `backend/app/services/concept_source_links.py`.

8. **Text search**: add `search_sources_by_text(query, workspace_id, session)` to
   `backend/app/services/retrieval.py`. Returns `list[ChunkSearchResult]`. Vector search
   when available, ILIKE fallback. Applies reranker before returning.

9. **New settings**: add `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`,
   `EMBEDDING_API_BASE`, `EMBEDDING_DIM`, `RERANKER_PROVIDER`, `RERANKER_API_KEY` to
   `backend/app/settings.py`.

10. **Export safety**: confirm `SourceChunk` content (including embeddings) is excluded from
    Trail Pack export (add assertion to existing export tests).

11. **Tests**: unit tests for parser, chunker, linker, embedding client, reranker stub.
    Integration test: upload PDF bytes → `parser_status="parsed"`, at least one chunk created,
    auto-link created when `trail_id` supplied. Export regression test still passes.

### Acceptance criteria

- Uploading a PDF sets `parser_status="parsed"` and populates `raw_text` (markdown format).
- At least one `SourceChunk` row is created per parsed source with `line_start`/`line_end`.
- When `EMBEDDING_PROVIDER` is configured, `embedding` column is populated on chunks.
- When `EMBEDDING_PROVIDER=disabled`, embedding is skipped and ILIKE fallback works.
- Uploading with `trail_id` creates `ConceptSourceLink` rows for matching concepts.
- `search_sources_by_text` returns `ChunkSearchResult` objects with line navigation metadata.
- Export regression tests still pass (no chunk content or embeddings leak).

### Note on scope

DOCX and PPTX can follow in a second pass. One working format (PDF) unblocks the retrieval
loop. Background-job upgrade for parsing is Phase 17 polish.

**Images**: pdfplumber exposes image bounding boxes and byte data (via `page.images`). Currently,
images are silently skipped — no chunk is produced. A `[IMAGE: page N]` placeholder insertion
and vision-model captioning via `LLMClient.caption_image` is reserved for Phase 17.
The `DocumentElement` type list reserves `"image"` as a deferred type: a vision model converts
image bytes → text description → `DocumentElement(type="image", text="...")` → flows through
the chunker identically to a paragraph. No structural change will be needed when this lands.
Markdown image alt text (`![alt](url)`) IS preserved as paragraph text.

**Why pdfplumber instead of pdfminer.six**: pdfplumber (MIT) exposes font metadata and image
bounding boxes through a higher-level API without the AGPL concerns of PyMuPDF. It gives us
the hooks for heading detection (via font size heuristics) and image handling (Phase 17)
without switching libraries later.

**Why embeddings now instead of Phase 17**: The Alembic migration and EmbeddingClient add
~100 LOC but avoid a schema migration on a live table later (adding a vector column to a
populated table requires `ALTER TABLE ... ADD COLUMN` which is instant for nullable columns
but still a migration event). Having the interface in place also means the reranker and
retrieval service have a consistent data shape from day one. With `EMBEDDING_PROVIDER=disabled`
as the default, there is zero runtime cost for deployments that don't configure an embedding
provider.

**Why a reranker stub now**: The retrieval pipeline has a natural `search → rerank → limit`
shape. Defining the interface now means any future Cohere or FlashRank integration is a
single provider addition, not a pipeline refactor.

---

## Item 3: Phase 11 LLM Tool Calling Loop

**Status: complete**

### Problem

Phase 11 registered three retrieval tool definitions (`search_sources`, `get_concept_sources`,
`get_graph_neighbourhood`) and built the service functions they wrap. But the tutor's chat loop
only invokes one tool today: `get_tutor_instructions` via the compatibility adapter. The LLM
never calls the retrieval tools during a turn. The tools exist but are never used.

This also matters for Phase 14 (Tutor-Suggested Quiz Cards): `suggest_quiz` will be the
second real tool the tutor invokes. Without a working multi-turn tool calling loop, Phase 14
will face the same choice — implement the loop then, or defer again.

### What exists

- Tool definitions: `backend/app/agents/retrieval_tools.py` — `RETRIEVAL_TOOLS` list with
  three `ProviderToolDefinition` objects.
- Tool service functions: `backend/app/services/retrieval.py`.
- Provider tool abstraction: `backend/app/agents/provider_tools.py`.
- Tutor chat service: `backend/app/services/conversations.py`. Currently runs one tool turn
  (get_tutor_instructions) then streams the visible response. No loop for subsequent tool calls.

### Architecture: Dual-Retrieval Pattern

Item 3 implements a two-tier retrieval design enabled by Item 2's chunk + line-number pipeline:

**Tier 1 — Chunk search** (`search_sources` tool): fast lookup returning `ChunkSearchResult`
objects with `section_heading`, `line_start`, `line_end`, `source_revision_id`. Gives the LLM
a map of where relevant content lives without flooding the context window.

**Tier 2 — Section reading** (`read_document_section` tool): the LLM uses `line_start` from a
Tier 1 result to call `read_document_section(source_revision_id, line_start, window_lines=50)`,
which reads that many lines from `SourceRevision.raw_text` (the markdown representation). This
returns the full structured section with surrounding context — headings, paragraphs, lists —
without dumping all chunks into every prompt.

The LLM decides when to drill into a section. The two-call pattern (search → read) is
intentional: it keeps average context size small while allowing deep dives on demand within
the tool budget.

### Scope

1. **Parallel tool-call loop** in `backend/app/services/conversations.py` (wherever the tutor
   generation lives): after the initial mode-selection tool turn, run a bounded retrieval loop.

   **Budget**: `TOOL_CALL_BUDGET = 3` counts individual tool call executions (not loop
   iterations). A single LLM response returning 2 calls costs 2 against the budget.

   **Parallel execution**: both providers can return multiple tool calls in one response
   (OpenAI `message.tool_calls` array; Anthropic `content` array with multiple `tool_use`
   blocks). The normalization layer already handles this — `_accumulate_openai_chat_tool_call_deltas`
   collects by stream index; `AnthropicStreamState.tool_blocks` is keyed by index. Execute
   all tool calls from one response concurrently with `asyncio.gather` before the next LLM
   call. This is 1 LLM round trip per batch of N calls, not N sequential round trips.

   ```
   budget = TOOL_CALL_BUDGET
   while budget > 0:
       events = collect all NormalizedStreamEvents from one LLM response
       tool_calls = [e.tool_call for e in events if e.kind == "tool_call"]
       if not tool_calls: break           # model done — stream text to client
       tool_calls = deduplicated(tool_calls)
       tool_calls = tool_calls[:budget]   # cap to remaining budget
       budget -= len(tool_calls)
       results = await asyncio.gather(*[execute_tool(tc) for tc in tool_calls])
       messages = append_tool_round(messages, tool_calls, results)
   ```

2. **Per-result size cap**: truncate each tool result to `MAX_TOOL_RESULT_CHARS = 2000`
   characters before appending to context. Add a count suffix if truncated
   (e.g., `"... [truncated, 3 more results]"`). Never inject raw multi-chunk dumps.

3. **Deduplication**: if the model calls the same tool name with identical arguments a second
   time within the same turn, return the cached result from the first call — do not re-execute
   and do not add a second copy of the result to context.

4. **Tool offer condition**: only pass `RETRIEVAL_TOOLS` to the LLM when the current concept
   has at least one linked source (`len(context.sources) > 0`). No tool overhead on turns with
   no source data to return.

5. **`SEARCH_SOURCES_TOOL` dispatch**: update the tool executor to route `search_sources` calls
   to `search_sources_by_text` (the chunk-text search added in Item 2, returning
   `ChunkSearchResult` objects) rather than the title-only `search_sources_by_title`. The
   result includes `line_start`, `line_end`, `section_heading`, `source_revision_id` so the
   LLM can chain into `read_document_section`.

6. **`READ_DOCUMENT_SECTION_TOOL`**: add a fourth retrieval tool. Parameters:
   `source_revision_id` (UUID string), `line_start` (int), `window_lines` (int, default 50).
   Reads lines `[line_start, line_start + window_lines)` from `SourceRevision.raw_text`.
   Returns the markdown text of that window. Scoped to workspace — reject if revision does not
   belong to the request workspace.

7. **SSE events**: emit `tool_call` and `tool_result` SSE events for each retrieval call with
   sanitized previews (same pattern as the existing instruction-tool events).

8. **Persistence**: persist all retrieval tool turns as hidden `ConversationTurn` rows (same
   pattern as instruction tool turns) so they survive prompt replay and context stays
   consistent across turns.

9. **Scope checks**: enforce existing workspace/trail scope in every tool executor. The loop
   must not allow cross-workspace access.

10. **Tests**: fake-provider tests covering:
    - Two tool calls returned in one response → both executed concurrently, budget decremented by 2
    - Budget hit mid-turn (3 calls requested, budget=3, then 1 more → capped to 0)
    - Duplicate call → second execution skipped, cached result returned
    - No tool call → loop exits immediately, text streams to client
    - Malformed tool arguments → degrade safely, return error result, do not crash loop
    - Tool offer condition: tools NOT passed when `context.sources` is empty
    - `read_document_section` returns correct lines from `raw_text`; rejects wrong workspace

11. Update `docs/CURRENT_VARIANT.md` deferred list to mark the LLM tool calling loop as complete.

### Acceptance criteria

- The tutor can invoke retrieval tools during a turn when the LLM chooses to; multiple calls
  in one response are executed concurrently (not sequentially with separate LLM calls).
- Budget (`TOOL_CALL_BUDGET = 3`) counts individual executions; no infinite loop.
- Each tool result is capped at `MAX_TOOL_RESULT_CHARS = 2000` before entering context.
- Duplicate calls within a turn return cached results.
- `search_sources` dispatches to chunk-text search and returns `ChunkSearchResult` objects
  with `line_start`/`line_end` navigation metadata.
- `read_document_section` reads lines from `raw_text` (markdown), scoped to workspace.
- Hidden tool turns persist and replay correctly.
- SSE `tool_call` / `tool_result` events stream to the client.
- All existing 349+ tests still pass.

---

## Order and Rationale

1. **Item 1 first** — small, completes Phase 12, makes the backend recommendation visible to
   users immediately, and does not depend on Items 2 or 3.
2. **Item 2 second** — unblocks real data for the retrieval loop. Item 3 without data to
   retrieve is still mostly a no-op from the learner's perspective.
3. **Item 3 third** — once parsed chunks exist, the tool loop has real results to return.
   Also unblocks Phase 14 (suggest_quiz tool pattern).

Do not start Phase 13 until all three items are complete.

---

## Status Summary

| Item | Description | Status |
|---|---|---|
| 1 | Phase 12 UI: frontend recommendation consumption | complete |
| 2 | Phase 10 parser pipeline: PDF format + chunking | complete |
| 3 | Phase 11 LLM tool calling loop | complete |

Update this table as items complete.
