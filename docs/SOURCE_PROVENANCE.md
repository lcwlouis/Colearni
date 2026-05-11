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
