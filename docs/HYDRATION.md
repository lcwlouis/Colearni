# Hydration

## Definition

Hydration means taking a content-light Trail Pack and enriching it locally with sources.

Hydration exists because public Trail Packs should share learning structure, not copied source content.

## Hydration Sources

```text
public source links
open-license sources
user-uploaded sources
model general knowledge
manual notes
```

## Hydration Output

Hydration may create:

- Private source records.
- Fetched content.
- Chunks.
- Embeddings.
- Generated explanations.
- Generated quizzes.
- Retrieval indexes.

Hydration output must remain private by default.

Hydration belongs after safe Trail Pack export/import foundations. It should make content-light Trail Packs locally useful without moving Trail sharing behind broad ingestion or retrieval work.

Current Phase 7 implementation: hydration records private intent only. `POST /hydrate` creates private `SourceRecord` placeholders from selected imported public research sources and/or model-knowledge intent. It does not fetch remote content, parse files, create chunks, create embeddings, generate explanations, or build retrieval indexes.

## Flow

```text
Import Trail Pack
-> show source manifest
-> identify available public sources
-> user optionally uploads restricted/private sources
-> backend records private hydration placeholders
-> later ingestion/retrieval phases fetch, index, and expose evidence through controlled tools
```

## Rules

- Hydrated content must not be included in public export unless it passes explicit provenance and licensing checks.
- User-uploaded sources remain private.
- Unknown license means no redistribution of content.
- Public access is not the same as redistribution rights.
- Hydration can be skipped; the learner should still be able to learn from the graph, tutor, and model knowledge where allowed.

## Source Records Created By Hydration

Hydrated source records should preserve:

- Original source id from the Trail Pack when applicable.
- URL or local upload reference.
- Origin.
- Access level.
- License.
- Whether retrieval is allowed.
- Whether public export is allowed.
- Fetch/index timestamp.

## Import-Time UI Requirements

After import, the UI should show:

- Which public sources are available.
- Which sources are missing.
- Which sources have unknown or restricted license status.
- Whether hydration has already run.
- What private uploads the user can optionally add.

## Export Interaction

Public export after hydration must still run the export sanitizer. Source revisions, object keys, hydrated chunks, embeddings, generated summaries, generated quizzes, private notes, and uploaded source text are excluded unless a future explicit policy allows a specific open-licensed artifact.

## Source Ingestion Relationship

The source ingestion foundation now stores private uploads with immutable revision provenance AND runs the parser pipeline (PDF/Markdown/plaintext parsing into canonical markdown, heading-aware chunking, best-effort embeddings, and `trail_id` auto-linking of sources to concepts). DOCX/PPTX parsing and durable background ingestion jobs remain deferred. The V1 ingestion flow is:

```text
Uploaded file
-> private object storage
-> parser
-> markdown-like canonical text
-> source revision
-> chunks
-> embeddings / full-text index
-> concept-source links
-> controlled retrieval/open tools
```

Priority formats are PDF, DOCX, and PPTX (PDF, Markdown, and plaintext are implemented; DOCX/PPTX deferred). Do not use git internally for user source tracking in V1; use content hashes, parser versions, source revision records, object keys, and database/object-storage versioning.

Raw filesystem browsing must not be the primary retrieval architecture. Retrieval should happen through controlled tools such as `search_sources`, `open_source_chunk`, `get_concept_sources`, and `get_graph_neighbourhood`, with workspace/Trail/concept budgets.
