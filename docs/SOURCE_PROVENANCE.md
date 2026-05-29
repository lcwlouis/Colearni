# Source Provenance

## Core Rule

Every source must declare origin, access level, and export eligibility.

Source provenance is mandatory because Trail Packs are designed to share learning structure without leaking private or copyrighted/source-derived content.

## Source Origins

```text
research_agent
user_upload
manual
system
```

Additional internal content types such as `private_note` and `chat_history` should be treated as private workspace records and excluded from public export.

## Access Levels

```text
public
private
restricted
unknown
```

Access meanings:

- `public`: the source is publicly reachable, but content redistribution is not automatically allowed.
- `private`: the source belongs to the workspace/user and must not be exported.
- `restricted`: the source has contractual, paywalled, institutional, or other access limits.
- `unknown`: access or license status is unclear; no content redistribution is allowed.

## Default Export Rules

```text
origin = user_upload      -> exclude from public export
origin = private_note     -> exclude from public export
origin = chat_history     -> exclude from public export
origin = research_agent   -> include public link/metadata only
access = unknown          -> no redistribution of content
access = restricted       -> metadata only or exclude
```

Public export may include:

- Concept title.
- Graph edges.
- Learning objectives.
- Abstract mastery labels.
- Public source URL.
- Source title.
- Source type.
- Research trace.

Public export must exclude:

- Uploaded files.
- Raw source text.
- Chunks.
- Embeddings.
- Private notes.
- Chat history.
- Mastery state.
- Generated summaries from private/user-uploaded content.
- Generated quizzes from private/user-uploaded content.
- Artifact payloads derived from private/user-uploaded content unless a future explicit open-license policy allows them.

Trail Pack sharing/import is part of the MVP product identity. Source ingestion, retrieval, and visual artifacts must preserve this public/private boundary rather than moving Trail sharing later or weakening the sanitizer.

## Sanitizer Pseudocode

```python
def can_include_source_in_public_export(source):
    if source.origin == "user_upload":
        return False
    if source.access in {"private", "restricted"}:
        return False
    if source.origin == "research_agent" and source.access == "public":
        return True
    return False
```

The export sanitizer should be stricter than UI state. It must not trust client-provided inclusion flags without checking provenance.

## Source-Derived Artifact Rules

Artifacts derived from a source inherit that source's export restrictions unless explicitly proven otherwise.

Examples:

- A summary generated from a user-uploaded PDF is private.
- A quiz generated from a restricted source is private.
- Chunks and embeddings are never public Trail Pack content.
- A research-agent public source URL may be exported as metadata, but copied page text may not.
- Future visualiser/artifact templates inherit the most restrictive source provenance used to create them.

## Ingestion Provenance

Source ingestion V1 tracks uploaded/private files without using git internally for user source history.

Current implemented foundation:

- Uploaded files are stored as private local objects under `SOURCE_STORAGE_ROOT`.
- Each upload creates a private `SourceRecord` with `origin = user_upload`, `access = private`, and `include_on_public_export = false`.
- Each upload creates one immutable `SourceRevision` with object key, `sha256:<hex>` content hash, file size/content type, parser metadata, status, and metadata.
- Parser pipeline (Consolidation Item 2): `raw_text` is populated as markdown (headings serialized as `#`/`##`/`###`), `parser_status` is `"parsed"` on success or `"failed"` with `parser_error` on failure.
- `SourceChunk` rows are created per revision with `text`, `char_start`, `char_end`, `line_start`, `line_end`, `section_heading`, and (optionally) `embedding`.
- Chunk embeddings are stored in the `embedding` column (pgvector) when `EMBEDDING_PROVIDER` is configured. NULL when disabled.
- Learner-facing source metadata APIs return sanitized revision summaries, not storage object keys, content hashes, raw text, chunks, or embeddings.
- Public export excludes uploaded sources, revision artifacts, chunk rows, and embedding vectors; import rejects source revision/object/hash fields.

Required provenance fields for ingested sources and revisions:

- Object key.
- Content hash.
- Parser name/version.
- Source revision record.
- Access level.
- License/access status.
- Export eligibility.

Priority ingestion formats: PDF (pdfplumber), Markdown, plain text. DOCX/PPTX deferred.
Parsed canonical text, chunks, embeddings, generated summaries, and concept-source links derived from private uploads stay private unless a future explicit licensing policy says otherwise.

## Tutor Context Sources

The tutor assembles source metadata for the current concept before each turn. The access rules here are deliberately more permissive than the export sanitizer — the workspace owner is allowed to see their own private material inside the tutor.

**Allowed in tutor context (same workspace only):**

```text
access = public   -> included
access = private  -> included (workspace owner's own material)
```

**Excluded from tutor context:**

```text
access = restricted  -> excluded (contractual/paywalled limits apply inside the workspace too)
access = unknown     -> excluded (redistribution status unclear; do not expose)
```

Additional safety rules applied by `get_concept_sources_for_tutor`, `search_sources_by_title`,
and `search_sources_by_text`:

- Only sources linked to the current concept via `ConceptSourceLink` are returned by `get_concept_sources_for_tutor`. `search_sources_by_text` may search the full workspace when no `concept_id` is given, but still scopes to the same workspace and access filter.
- Cross-workspace isolation is enforced with a double check: `SourceRecord.workspace_id == workspace_id` AND `Trail.workspace_id == workspace_id` (via a JOIN through `ConceptNode → Trail`).
- `read_document_section` is scoped to workspace: it looks up `SourceRevision` by both `id` AND `workspace_id`. A revision from another workspace raises `LookupError` (→ 404 in routes).
- Results are capped at 10 by `_MAX_RETRIEVAL_RESULTS`; callers may request a lower cap.
- Only whitelisted metadata fields are returned (`id`, `title`, `url`, `origin`, `access`, `license`, `relation`). Object keys, content hashes, raw text, chunks, and embeddings are never included in tool results or source metadata APIs.
- `read_document_section` returns markdown text from `raw_text` — this is learner-visible content scoped to the same workspace. It must never be included in Trail Pack export.

## Research Agent Sources

Research-agent sources may be included in public export only as links and metadata:

- Source id.
- Title.
- URL.
- Source type.
- License/access status.
- Why the source was selected.
- Search query used.

They must not include copied source content or long summaries.

## Unknown License

Public access is not the same as redistribution rights. When in doubt, export links and metadata only.

`license = unknown` means:

- Do not redistribute copied content.
- Do not export source-derived prose.
- Allow local hydration only if fetching/indexing is permitted by the user's environment and policy.

## Critical Tests

- User-upload source never appears in public export.
- Private notes never appear.
- Raw chunks never appear.
- Embeddings never appear.
- Chat history never appears.
- Public research source URL appears.
- Research trace appears.
- Export report lists excluded items.
