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

## Flow

```text
Import Trail Pack
-> show source manifest
-> identify available public sources
-> user optionally uploads restricted/private sources
-> backend indexes allowed content
-> tutor can use hydrated evidence in this workspace
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

Public export after hydration must still run the export sanitizer. Hydrated chunks, embeddings, generated summaries, generated quizzes, private notes, and uploaded source text are excluded unless a future explicit policy allows a specific open-licensed artifact.
