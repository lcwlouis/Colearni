# Consolidation Plan: Closing Phase 10–12 Gaps

## Why This Exists

After completing Phases 10, 11, and 12, a review identified a consistent pattern across all three:

- The backend service and API were implemented correctly.
- The frontend never called the new endpoints.
- The harder backend pieces (parser pipeline, LLM tool calling loop) were deferred each time.

Left unresolved, these compound. Phase 13+ will continue building on a foundation that looks
complete in the plan but is not wired up for users. The demo path (Phase 16) requires all three
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

**Status: pending**

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
Upload → Parser (format-specific) → CanonicalDocument (typed elements + metadata)
       → Chunker (structure-aware, section-boundary) → SourceChunk rows
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
    def text(self) -> str:  # concatenated text for raw_text storage
        return "\n\n".join(e.text for e in self.elements if e.text.strip())
```

Format-specific element extraction:
- **PDF** (`pdfminer.six`, MIT, fallback `pypdf`): extract raw text, split on `\n\n` or ≥2 blank
  lines to produce `"paragraph"` elements. No heading detection from PDF at MVP (font metadata not
  exposed by the high-level pdfminer API). All elements are `"paragraph"` type.
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
`char_start`, `char_end`, `section_heading` (nearest ancestor heading text, or `NULL`).
No embedding column yet (pgvector deferred to Phase 16). No overlap — heading context in
`section_heading` field replaces the need for overlap.

`MAX_CHUNK_CHARS` default: 2 000. Configurable via env var.

**Linker layer** — auto-creates `ConceptSourceLink` rows when `trail_id` is provided at upload:
- For every concept in the trail, check if the concept's `title` or `description` appears in
  any chunk (case-insensitive substring match). If yes → link with `link_type="supplementary"`.
- This is MVP-grade keyword linking. Embedding-based candidate generation and LLM reranking are
  planned for Phase 16 when pgvector column is added.
- Linker runs only when upload includes `trail_id`. Without it, no auto-links are created.
- Linker respects existing manual links — no duplicate `ConceptSourceLink` rows.

### Scope

1. **Parser**: implement `parse_source(data: bytes, content_type: str) -> CanonicalDocument`
   in `backend/app/services/parser.py`. Support `application/pdf` (via `pdfminer.six`,
   fallback `pypdf`), `text/plain`, and `text/markdown`. Each format produces typed
   `DocumentElement` objects (see Architecture above). Store `doc.text` in
   `SourceRevision.raw_text`. Set `parser_name` dynamically, `parser_status="parsed"` on
   success, `"failed"` + `parser_error` on error. Run synchronously on upload (background
   worker is Phase 16 polish).

2. **Chunker + SourceChunk model**: implement
   `chunk_elements(elements: list[DocumentElement], revision_id, workspace_id) -> list[SourceChunk]`
   in `backend/app/services/chunker.py`. Add `SourceChunk` SQLAlchemy model and Alembic
   migration if the table does not exist. Each row: `id`, `source_revision_id`, `workspace_id`,
   `chunk_index`, `text`, `char_start`, `char_end`, `section_heading` (nullable string).

3. **Upload route change**: accept an optional `trail_id` form field in
   `backend/app/api/sources.py`. Pass it through to `upload_private_source` in
   `backend/app/services/source_ingestion.py`.

4. **Linker**: implement `auto_link_source_to_trail(session, source_revision_id, trail_id)`
   in `backend/app/services/concept_source_links.py`. Called from ingestion after chunking
   when `trail_id` is not None.

5. **Text search**: add `search_sources_by_text(query, workspace_id, session)` to
   `backend/app/services/retrieval.py`. Uses `ILIKE '%query%'` against `SourceChunk.text`.
   Vector search is deferred.

6. **Export safety**: confirm `SourceChunk` content is excluded from Trail Pack export
   (add assertion to existing export tests).

7. **Tests**: unit tests for parser, chunker, and linker. Integration test: upload PDF bytes
   → `parser_status="parsed"`, at least one chunk created, auto-link created when `trail_id`
   supplied. Export regression test still passes.

### Acceptance criteria

- Uploading a PDF sets `parser_status="parsed"` and populates `raw_text`.
- At least one `SourceChunk` row is created per parsed source.
- Uploading with `trail_id` creates `ConceptSourceLink` rows for matching concepts.
- `search_sources_by_text` returns results from chunk text.
- Export regression tests still pass (no chunk content leaks).

### Note on scope

DOCX and PPTX can follow in a second pass. One working format (PDF) unblocks the retrieval
loop. Embedding-based linking and the background-job upgrade are Phase 16 polish.
Agentic workspace-wide file search (distinct from Phase 11 concept-scoped retrieval tools)
needs separate architecture planning before Phase 14.

**Images**: `pdfminer.six` silently skips embedded image objects — they are binary blobs in the
PDF stream that pdfminer does not read. A diagram or screenshot in a PDF produces no chunk.
Markdown image alt text (`![alt](url)`) IS preserved as paragraph text; the image data at the
URL is not fetched. DOCX/PPTX picture shapes produce no text. This is acceptable at MVP.
The `DocumentElement` type list reserves `"image"` as a deferred type for Phase 16 multimodal
support: a vision model converts image bytes → text description → `DocumentElement(type="image")`
→ flows through the chunker identically to a paragraph. No structural change will be needed.

---

## Item 3: Phase 11 LLM Tool Calling Loop

**Status: pending**

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
   to `search_sources_by_text` (the new chunk-text ILIKE search added in Item 2) rather than
   the title-only `search_sources_by_title`. This is what makes uploaded content agentically
   retrievable.

6. **SSE events**: emit `tool_call` and `tool_result` SSE events for each retrieval call with
   sanitized previews (same pattern as the existing instruction-tool events).

7. **Persistence**: persist all retrieval tool turns as hidden `ConversationTurn` rows (same
   pattern as instruction tool turns) so they survive prompt replay and context stays
   consistent across turns.

8. **Scope checks**: enforce existing workspace/trail scope in every tool executor. The loop
   must not allow cross-workspace access.

9. **Tests**: fake-provider tests covering:
   - Two tool calls returned in one response → both executed concurrently, budget decremented by 2
   - Budget hit mid-turn (3 calls requested, budget=3, then 1 more → capped to 0)
   - Duplicate call → second execution skipped, cached result returned
   - No tool call → loop exits immediately, text streams to client
   - Malformed tool arguments → degrade safely, return error result, do not crash loop
   - Tool offer condition: tools NOT passed when `context.sources` is empty

10. Update `docs/CURRENT_VARIANT.md` deferred list to mark the LLM tool calling loop as complete.

### Acceptance criteria

- The tutor can invoke retrieval tools during a turn when the LLM chooses to; multiple calls
  in one response are executed concurrently (not sequentially with separate LLM calls).
- Budget (`TOOL_CALL_BUDGET = 3`) counts individual executions; no infinite loop.
- Each tool result is capped at `MAX_TOOL_RESULT_CHARS = 2000` before entering context.
- Duplicate calls within a turn return cached results.
- `search_sources` dispatches to chunk-text ILIKE search (not title-only).
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
| 2 | Phase 10 parser pipeline: PDF format + chunking | pending |
| 3 | Phase 11 LLM tool calling loop | pending |

Update this table as items complete.
