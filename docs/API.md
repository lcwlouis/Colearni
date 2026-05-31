# CoLearni API Contract

## Overview

Application routes are prefixed with `/api`. The health endpoint is the only planned unprefixed route. The backend is a FastAPI application. Routes stay thin: they validate input, call a service, and return a response. No business logic in routes.

## Workspace Scoping

In the local-ready design there is no auth. The active workspace is identified by `workspace_id` in the URL path. A default workspace is auto-created on first run. Clients should store the workspace id locally (e.g. in localStorage) and include it in all requests.

Every endpoint that operates on workspace data uses the pattern:

```
/api/workspaces/{workspace_id}/...
```

This keeps the API SaaS-compatible without requiring auth in the local-ready design.

## Common Types

```python
# Concept levels (intrinsic node attribute, not inferred from edges)
ConceptLevel = Literal["umbrella", "topic", "subtopic", "granular"]

# Bloom taxonomy levels
BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]

# Mastery statuses
MasteryStatus = Literal["not_started", "learning", "needs_review", "mastered"]

# Node types
NodeType = Literal["concept", "skill", "misconception", "example"]

# Edge relation types
RelationType = Literal["prerequisite", "contains", "application", "related"]

# Tutor modes
TutorMode = Literal["socratic", "direct", "repair", "quiz_prompt", "explore", "free_explore"]

# Source origins
SourceOrigin = Literal["research_agent", "user_upload", "manual", "system"]

# Source access levels
SourceAccess = Literal["public", "private", "restricted", "unknown"]

# Difficulty levels
Difficulty = Literal["beginner", "intermediate", "advanced"]

# Target depth (same values as BloomLevel, used on Trail creation)
TargetDepth = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]

# Optional Trail generation cap. Defaults to 40 in the local-ready UI.
# Normal generation should usually stay around 10-30 concepts; 100 is the per-Trail viewer cap.
MaxNodes = int  # 10 <= max_nodes <= 100

# Quiz type
QuizType = Literal["level_up", "practice"]

# Quiz question type
QuizQuestionType = Literal["multiple_choice", "short_answer", "long_answer"]

# Quiz question difficulty
QuizQuestionDifficulty = Literal["light", "standard", "challenge"]

# Tutor stream status
TutorStreamStatus = Literal[
    "thinking",
    "calling_tool",
    "tool_called",
    "tool_complete",
    "responding",
    "retrying_without_thinking",
]

# Source ingestion revision status
SourceRevisionStatus = Literal["pending_parse", "parsed", "failed", "skipped"]
```

## Schemas

### Workspace

```json
{
  "id": "uuid",
  "name": "string",
  "created_at": "ISO 8601 datetime"
}
```

### Trail

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "title": "string",
  "topic": "string",
  "goal": "string",
  "target_depth": "TargetDepth",
  "created_at": "ISO 8601 datetime",
  "node_count": "int",
  "edge_count": "int"
}
```

### ConceptNode

```json
{
  "id": "uuid",
  "trail_id": "uuid",
  "slug": "string (unique within trail)",
  "title": "string",
  "node_type": "NodeType",
  "concept_level": "ConceptLevel",
  "difficulty": "Difficulty",
  "bloom_level": "BloomLevel",
  "mastery_check_labels": ["string"],
  "metadata_json": {}
}
```

`metadata_json` may carry a cached `primer` object (`{ "overview", "key_terms", "sample_questions", "version" }`); the concept-detail response also surfaces it as the top-level `primer` field (see `ConceptPrimer`).

### ConceptPrimer

```json
{
  "overview": "string (one-paragraph concept orientation)",
  "key_terms": [{ "term": "string", "definition": "string (one line)" }],
  "sample_questions": ["string (<=90 chars starter prompt)"],
  "version": "int (current cache schema version: 2)"
}
```

Concept-level orientation generated in a separate LLM pass and cached on `ConceptNode.metadata_json["primer"]`. `key_terms` holds 3-6 entries; `sample_questions` holds 3-4 short starter prompts that power the chat welcome chips. `sample_questions` defaults to `[]` for primers cached before the field existed (version 1). Content is abstract and not source-derived, so it is export-safe.

### ConceptEdge

```json
{
  "id": "uuid",
  "trail_id": "uuid",
  "source_node_id": "uuid",
  "target_node_id": "uuid",
  "relation_type": "RelationType"
}
```

### TrailGraph

```json
{
  "nodes": ["ConceptNode"],
  "edges": ["ConceptEdge"],
  "mastery": {
    "<concept_id>": "MasteryRecord"
  }
}
```

### NextConceptResponse

```json
{
  "concept_id": "uuid | null",
  "concept_title": "string | null",
  "reason": "string",
  "all_mastered": "bool"
}
```

### MasteryRecord

```json
{
  "id": "uuid | null",
  "workspace_id": "uuid",
  "concept_id": "uuid",
  "status": "MasteryStatus",
  "bloom_level": "BloomLevel",
  "score": "float (0.0–1.0)",
  "updated_at": "ISO 8601 datetime | null"
}
```

When no DB row exists yet, the API synthesizes a default `MasteryRecord` with `status: "not_started"`, `score: 0.0`, and `id`/`updated_at` as `null`.

### QuizQuestion

```json
{
  "id": "string (stable within a card)",
  "type": "multiple_choice | multi_select | ordering | cloze | short_answer | long_answer | code",
  "prompt": "string",
  "mastery_label": "string",
  "difficulty": "QuizQuestionDifficulty",
  "options": ["string"]
}
```

`options` is present for `multiple_choice`, `multi_select`, and `ordering` questions (2-6 entries). New API responses emit `multiple_choice`, `multi_select`, `ordering`, `cloze`, `short_answer`, `long_answer`, and `code`; older persisted `explain` / `apply` / `compare` snapshots are normalized to `long_answer` when read back through the API. Prompts may contain Markdown and LaTeX. The submitted `QuizAnswer.answer` is always a single string: `multi_select`/`ordering` are newline-separated option/item lists, `cloze` is newline-separated fill-ins (one per `____` blank in the prompt), and `code` is a code/pseudocode snippet.

### LevelUpCard

```json
{
  "concept_id": "uuid",
  "quiz_type": "QuizType",
  "questions": ["QuizQuestion"]
}
```

### QuizGenerateRequest

```json
{
  "force_new": "bool (default false)"
}
```

Quiz generation reuses the existing backend draft for the same `(concept_id, quiz_type)` unless `force_new` is `true`. Drafts are cleared after grading.

### GradeResult

```json
{
  "passed": "bool",
  "score": "float (0.0–1.0)",
  "feedback": "string",
  "per_question": [
    {
      "question_id": "string",
      "score": "float (0.0–1.0)",
      "feedback": "string"
    }
  ],
  "mastery_status": "MasteryStatus",
  "attempt_id": "uuid"
}
```

### QuizAttempt

```json
{
  "id": "uuid",
  "concept_id": "uuid",
  "quiz_type": "QuizType",
  "questions": ["QuizQuestion"],
  "answers": [{"question_id": "string", "answer": "string"}],
  "evaluator_feedback": "string",
  "passed": "bool",
  "score": "float (0.0–1.0)",
  "created_at": "ISO 8601 datetime"
}
```

### QuizAttemptListResponse

```json
{
  "attempts": ["QuizAttempt"]
}
```

### ConversationMessage

```json
{
  "id": "uuid",
  "role": "user | assistant",
  "content": "string",
  "reasoning": "string | null",
  "reasoning_parts": [
    {
      "kind": "status | thinking | tool_call | tool_result | suggest_quiz | suggest_flashcards | suggest_artifact",
      "status": "TutorStreamStatus | null",
      "text": "string | null",
      "name": "string | null",
      "mode": "TutorMode | null",
      "query": "string | null",
      "result": "string | null",
      "quiz_type": "level_up | practice | null",
      "artifact_kind": "worked_example | comparison_card | timeline | mini_graph | simulation_slider | null",
      "reason": "string | null"
    }
  ],
  "mode": "TutorMode | null",
  "created_at": "ISO 8601 datetime"
}
```

### SourceRecord

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "title": "string",
  "url": "string | null",
  "origin": "SourceOrigin",
  "access": "SourceAccess",
  "license": "string | null",
  "include_on_public_export": "bool",
  "metadata_json": {}
}
```

### SourceRevision

Internal persistence record. Stored in the database; not returned directly by learner-facing APIs.

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "source_id": "uuid",
  "revision_number": "int",
  "object_key": "string (private storage key; metadata only, not a public URL)",
  "content_hash": "sha256:<hex>",
  "content_type": "string | null",
  "file_size_bytes": "int",
  "parser_name": "string",
  "parser_version": "string",
  "status": "pending_parse | parsed | failed | skipped",
  "error_message": "string | null",
  "metadata_json": {},
  "created_at": "ISO 8601 datetime"
}
```

The Phase 10 parser pipeline is implemented. Uploading a supported file type (`text/plain`, `text/markdown`, `application/pdf`) synchronously parses, chunks, and optionally embeds the content. The revision's `status` is set to `"parsed"` on success or `"failed"` on parse error. `parser_name` reflects the format-specific parser used (`"plaintext"`, `"pdfplumber"`, etc.). `object_key` and `content_hash` are internal storage/provenance fields and must never appear in public Trail Pack export or learner-facing source metadata responses.

### SourceRevisionSummary

Sanitized revision summary returned by upload/source metadata endpoints.

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "source_id": "uuid",
  "revision_number": "int",
  "content_type": "string | null",
  "file_size_bytes": "int",
  "parser_name": "string",
  "parser_version": "string",
  "status": "pending_parse | parsed | failed | skipped",
  "error_message": "string | null",
  "metadata_json": {},
  "created_at": "ISO 8601 datetime"
}
```

### SourceUploadResponse

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "title": "string",
  "url": null,
  "origin": "user_upload",
  "access": "private",
  "license": null,
  "include_on_public_export": false,
  "metadata_json": {},
  "revision": "SourceRevisionSummary"
}
```

### ExportReport

```json
{
  "included": {
    "concepts": "int",
    "edges": "int",
    "source_links": "int",
    "has_research_trace": "bool"
  },
  "excluded": {
    "uploaded_files": "int",
    "source_revisions": "int",
    "chunks": "int",
    "embeddings": "int",
    "private_notes": "int",
    "mastery_records": "bool"
  }
}
```

### TrailPack

The Phase 6 JSON export is content-light. For round-trip import compatibility,
export now includes additive Trail and node fields that older clients may ignore:

```json
{
  "manifest": {
    "id": "string",
    "title": "string",
    "topic": "string | null",
    "goal": "string | null",
    "target_depth": "TargetDepth | null",
    "version": "string",
    "pack_type": "structure",
    "content_included": false,
    "hydration_supported": true
  },
  "graph": {
    "nodes": [
      {
        "id": "string",
        "title": "string",
        "node_type": "NodeType",
        "concept_level": "ConceptLevel",
        "difficulty": "Difficulty | null",
        "bloom_level": "BloomLevel | null"
      }
    ],
    "edges": [
      {"source": "string", "target": "string", "relation_type": "RelationType"}
    ]
  },
  "concepts": {},
  "sources": [],
  "research_trace": {}
}
```

### ImportReport

```json
{
  "trail_id": "uuid",
  "concepts_imported": "int",
  "edges_imported": "int",
  "sources_available": "int",
  "sources_missing": "int",
  "hydration_required": "bool",
  "warnings": ["string"]
}
```

## Error Format

All errors return a consistent JSON body:

```json
{
  "error": {
    "code": "string (machine-readable)",
    "message": "string (human-readable)",
    "details": {}
  }
}
```

Common error codes:

| HTTP Status | Code | Meaning |
|---|---|---|
| 400 | `invalid_input` | Request body failed validation |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | Duplicate slug, etc. |
| 413 | `invalid_input` | Upload/request exceeds the configured limit |
| 422 | `validation_error` | Pydantic validation failed |
| 500 | `llm_error` | LLM call failed or returned malformed output |
| 500 | `storage_error` | Private local storage operation failed |
| 503 | `budget_exceeded` | Resolver or gardener budget hit |

---

## Endpoints

### Health

#### `GET /health`

Returns service health. Always succeeds unless the process is dead.

**Response 200:**

```json
{
  "status": "ok",
  "version": "string",
  "db": "ok | error"
}
```

---

### Workspaces

#### `POST /api/workspaces`

Create a new workspace.

**Request body:**

```json
{
  "name": "string"
}
```

**Response 201:** `Workspace`

---

#### `GET /api/workspaces`

List all workspaces.

**Response 200:**

```json
{
  "workspaces": ["Workspace"]
}
```

---

#### `GET /api/workspaces/{workspace_id}`

Get a workspace.

**Response 200:** `Workspace`

---

### Trails

#### `POST /api/workspaces/{workspace_id}/trails/generate`

Generate a new Trail from a topic description. Calls the graph generator LLM, validates the output, and stores the graph.

**Request body:**

```json
{
  "topic": "string",
  "goal": "string",
  "target_depth": "TargetDepth",
  "max_nodes": "int | optional, default 40, min 10, max 100",
  "prior_knowledge": "string | optional, null, max 2000 chars"
}
```

`prior_knowledge` is the learner's stated prior knowledge for this Trail. It is persisted on the Trail and fed read-only into the tutor mode classifier (as `learner_prior_knowledge`) to calibrate pacing. When `null` or empty, the tutor assumes a complete beginner.

`max_nodes` is intentionally supported for local graph-size exploration. Normal generation should usually stay around 10-30 nodes; 100 is the current per-Trail viewer cap.

**Response 201:**

```json
{
  "trail": "Trail",
  "graph": "TrailGraph"
}
```

**Errors:**
- `500 llm_error` — LLM returned malformed output after one repair attempt
- `503 budget_exceeded` — resolver budget hit during generation

---

#### `POST /api/workspaces/{workspace_id}/trails/generate/stream`

Generate a new Trail while streaming progress events to the frontend. This endpoint is a local-ready progress helper for the current UI. It is **not durable across page refreshes**; Phase 17 demo polish replaces this with backend jobs and polling.

**Request body:** same as `POST /api/workspaces/{workspace_id}/trails/generate`.

**Response headers:**

```text
Content-Type: text/event-stream
```

**SSE event types:**

```json
{ "message": "Generating concept graph..." }
```
Emitted as `event: progress`.

```json
{ "text": "partial model output" }
```
Emitted as `event: delta` for visible model output and `event: thinking` when a provider exposes reasoning/thinking text.

```json
{ "trail": "Trail", "graph": "TrailGraph" }
```
Emitted as `event: done` after validation and persistence.

```json
{ "error": { "code": "string", "message": "string", "details": {} } }
```
Emitted as `event: error`; the stream then closes.

---

#### `GET /api/workspaces/{workspace_id}/trails`

List all Trails in a workspace.

**Response 200:**

```json
{
  "trails": ["Trail"]
}
```

---

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}`

Get a Trail with its full graph and mastery summary.

**Response 200:**

```json
{
  "trail": "Trail",
  "graph": "TrailGraph",
  "mastery_summary": {
    "total": "int",
    "not_started": "int",
    "learning": "int",
    "needs_review": "int",
    "mastered": "int"
  }
}
```

---

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/next`

Get the deterministic recommended next concept for a Trail.

**Response 200:**

```json
{
  "concept_id": "uuid | null",
  "concept_title": "string | null",
  "reason": "string",
  "all_mastered": "bool"
}
```

`concept_id` and `concept_title` are `null` when `all_mastered` is `true`.

The recommendation is scoped to the current Trail and uses mastery status,
prerequisite edges, concept level, difficulty, and title as deterministic tie-breakers.

**Response 404:** Trail not found or does not belong to the workspace.

---

#### `DELETE /api/workspaces/{workspace_id}/trails/{trail_id}`

Delete a Trail and all associated data.

**Response 204:** No body.

---

### Concepts

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}`

Get a concept with its graph context and mastery state.

**Response 200:**

```json
{
  "concept": "ConceptNode",
  "prerequisites": ["ConceptNode"],
  "contained_nodes": ["ConceptNode"],
  "containing_nodes": ["ConceptNode"],
  "related": ["ConceptNode"],
  "mastery": "MasteryRecord",
  "sources": ["SourceRecord"],
  "primer": "ConceptPrimer | null"
}
```

`primer` is the cached concept orientation primer when present, or `null` when no primer has been generated yet. This GET never auto-generates a primer; generation is an explicit calling-side decision (see the primer endpoints below).

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/primer`

Generate (or return the cached) concept orientation primer in a separate LLM pass. Idempotent: returns the cached primer without calling the model unless `force_new` is set. Primer content is abstract concept-level orientation, not source-derived, so it is export-safe.

**Request body (optional):**

```json
{ "force_new": false }
```

`force_new: true` regenerates and overwrites the cache.

**Response 200:** `ConceptPrimer`

**Errors:**
- `404 not_found` — workspace/trail/concept not found
- `500 llm_error` — primer generation failed

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/primer/stream`

Stream primer generation over SSE so the client can show a live preview. Mirrors the tutor chat streaming structure: the `done` event carries the authoritative `ConceptPrimer`; `thinking` and `token` events are a cosmetic live preview only.

**Response headers:**

```text
Content-Type: text/event-stream
```

**SSE event sequence:**
- Cache hit: a single `done` event (no model call).
- Cache miss: `status` (`{ "status": "preparing" }`) → zero or more `thinking` (`{ "content": "string" }`) and `token` (`{ "content": "string" }`) preview events → `done` with the authoritative primer, or `error` on failure.

```json
{ "type": "done", "primer": "ConceptPrimer" }
```

```json
{ "type": "error", "code": "not_found | llm_error", "message": "string" }
```

Only `token` chunks are accumulated and parsed into the primer JSON; `thinking` chunks are never fed to the parser.

**Resilient, backend-driven generation.** On a cache miss the actual generation is **detached from this request**: the server runs it as a background task that owns its own database session and commits the cached primer independently. This SSE response only subscribes to that task for the live preview. If the client disconnects, refreshes, or navigates away mid-stream, generation still **completes and persists server-side** — nothing is wasted and the next open is a cache hit. Re-issuing the request after a disconnect attaches to the same in-flight generation (or returns the cache once it has completed).

**Single-flight dedup.** At most one detached generation runs per concept at a time. Concurrent `primer/stream` opens for the same concept share that single background generation and therefore a single model call (enforced in-process per `concept_id`, and across processes via a PostgreSQL `pg_advisory_xact_lock` with a post-lock cache re-check). All concurrent subscribers receive the same authoritative `done`. (The plain `POST .../primer` endpoint is unchanged and remains idempotent on the cache.)

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/level-up`

Generate a level-up quiz card for a concept. Cards are generated from `mastery_check_labels` and never include private/source-derived content.

**Request body (optional):** `QuizGenerateRequest`

**Response 200:** `LevelUpCard` (with `quiz_type: "level_up"`)

If an ungraded level-up draft already exists for the concept, the backend returns that stored card unless `force_new` is `true`.

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/grade`

Grade a level-up quiz attempt. If passed, updates mastery to `mastered`. If failed, updates to `needs_review`.

**Request body:**

```json
{
  "questions": ["QuizQuestion"],
  "answers": [
    {"question_id": "string", "answer": "string"}
  ]
}
```

**Response 200:** `GradeResult`

Note: This endpoint only updates mastery for `level_up` attempts. See `/practice/grade` for practice attempts.
The client must send back the `questions` snapshot from the generated card so grading is deterministic and the graded attempt stores the exact card that was answered.
The matching backend draft is deleted after successful grading.

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/practice`

Generate a practice quiz card. Identical to level-up card generation but marks the card as `quiz_type: "practice"`.

**Request body (optional):** `QuizGenerateRequest`

**Response 200:** `LevelUpCard` (with `quiz_type: "practice"`)

If an ungraded practice draft already exists for the concept, the backend returns that stored card unless `force_new` is `true`.

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/practice/grade`

Grade a practice quiz attempt. Stores the attempt and returns feedback but **never updates mastery status**.

**Request body:**

```json
{
  "questions": ["QuizQuestion"],
  "answers": [
    {"question_id": "string", "answer": "string"}
  ]
}
```

**Response 200:** `GradeResult` (mastery_status reflects current state, unchanged)

---

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/quiz-attempts`

List prior graded quiz attempts for a concept in newest-first order. Attempts are immutable snapshots and are read-only; ungraded drafts are not included.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `quiz_type` | `level_up | practice` | optional | Filter to one quiz type. |
| `limit` | int | 10 | Max attempts to return (1-50). |

**Response 200:** `QuizAttemptListResponse`

---

### Tutor Chat

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat`

Send a message to the Socratic tutor for a concept. Returns a **Server-Sent Events (SSE)** stream.

Internally the tutor may persist hidden tool-call/tool-result turns to support
prompt replay for mastery-gated modes. Those internal turns are never returned
by the public conversation history endpoint.
The current `get_tutor_instructions` step is validated through the backend
provider-tool abstraction, but the public SSE payloads below intentionally keep
the existing compatibility shape.

**Request body:**

```json
{
  "message": "string",
  "conversation_id": "uuid | null",
  "regenerate": "bool (default false)",
  "replace_latest_user": "bool (default false)"
}
```

When `regenerate` is `true`, the backend reuses the latest visible user turn and
deletes generated assistant/tool turns after it before streaming the replacement
assistant response. It must not append a duplicate user turn.

When `replace_latest_user` is `true`, the backend replaces the latest visible
user turn with `message` and deletes generated assistant/tool turns after it
before streaming the replacement assistant response. This is intended for editing
the latest user message only. `regenerate` and `replace_latest_user` must not both
be `true`.

**Response headers:**

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

**SSE event types (each line is `data: <json>\n\n`):**

```json
{ "type": "mode", "mode": "TutorMode" }
```
Emitted before visible `token` events so the client knows which mode produced the visible answer. In mastery-gated flows, `status` and `tool_*` events may appear earlier.

```json
{ "type": "status", "status": "selecting_mode | thinking | calling_tool | tool_called | tool_complete | responding | retrying_without_thinking" }
```
Optional activity milestones for chain-of-thought style UI. These can appear before or between `thinking`, `mode`, and `token` events as the tutor moves through reasoning, retries, and internal tool resolution.

Mode notes:
- `socratic` is the default.
- `repair`, `quiz_prompt`, and bounded `explore` are handled directly by the base tutor prompt.
- `direct` and `free_explore` are mastery-gated and are only used after the tutor resolves an internal instruction tool.

```json
{ "type": "tool_call", "name": "get_tutor_instructions", "mode": "TutorMode" }
```
Optional public trace event showing that the tutor requested the internal instruction tool for a gated mode. `mode` here is the requested instruction mode, not necessarily the final visible tutor mode.

```json
{ "type": "tool_result", "name": "get_tutor_instructions", "mode": "TutorMode", "result": "string" }
```
Optional public trace event showing the sanitized result preview for that internal tool call. The `result` field is a learner-safe preview, not the raw internal instructions.
If tool arguments fail validation, the public preview still uses this shape and omits raw provider/internal payloads.

```json
{ "type": "suggest_quiz", "quiz_type": "level_up | practice", "reason": "string" }
```
Optional learner-visible quiz suggestion (Phase 14). Emitted when the tutor calls the `suggest_quiz` provider tool, which is offered on every turn (not gated on sources). It only surfaces an opt-in CTA: nothing is generated, opened, or graded, and mastery is never changed by this event. `concept_id` is implicit (the current concept) and is never a model argument. The suggestion is persisted on the assistant turn's `reasoning_parts` as `{ "kind": "suggest_quiz", "quiz_type": ..., "reason": ... }` so the CTA rehydrates on reload. The client collapses to a single active CTA per `quiz_type`; clicking it reuses the existing `quiz_drafts` generate/reuse path (no new endpoint).

```json
{ "type": "suggest_flashcards", "reason": "string" }
```
Optional learner-visible flashcards suggestion (Phase 15c). Emitted when the tutor calls the `suggest_flashcards` provider tool, offered on every turn (not gated on sources). Same opt-in contract as `suggest_quiz`: nothing is generated, opened, or graded, and mastery is never changed. `concept_id` is implicit. Persisted as `{ "kind": "suggest_flashcards", "reason": ... }`. Clicking the CTA opens the flashcards panel, which uses the existing `flashcards/generate` path. This remains CTA-first today; a direct inline chat-trigger flow is still WIP.

```json
{ "type": "suggest_artifact", "artifact_kind": "worked_example | comparison_card | timeline | mini_graph | simulation_slider", "reason": "string" }
```
Optional learner-visible artifact suggestion (Phase 15f). Emitted when the tutor calls the `suggest_artifact` provider tool, offered on every turn (not gated on sources). Same opt-in contract: nothing is generated, opened, or persisted, and mastery is never changed. `concept_id` is implicit; the model only passes `kind` + `reason`. Persisted as `{ "kind": "suggest_artifact", "artifact_kind": ..., "reason": ... }`. Clicking the CTA runs the backend-owned `POST .../artifacts/build(/stream)` path. This remains CTA-first today; a direct inline chat-trigger flow is still WIP.

```json
{ "type": "thinking", "content": "string" }
```
Optional reasoning/thinking chunks when the provider exposes them. When available, assistant turns persist the assembled full text in `ConversationMessage.reasoning` and an ordered public UI trace in `ConversationMessage.reasoning_parts` so clients can rehydrate thinking/tool boundaries after refresh.

```json
{ "type": "token", "content": "string" }
```
Streamed tokens as they arrive from the LLM.

Tutor message content is Markdown. The current frontend supports GFM, KaTeX math, fenced code blocks, and fenced `mermaid` diagrams.

```json
{
  "type": "done",
  "conversation_id": "uuid",
  "message": "ConversationMessage",
  "mastery_update": {
    "concept_id": "uuid",
    "status": "MasteryStatus",
    "score": "float"
  }
}
```
Emitted once at the end. Includes the full assembled message for storage and the latest mastery state for optimistic graph updates.

```json
{ "type": "error", "code": "string", "message": "string" }
```
Emitted if the LLM call fails. The stream then closes.

**Mastery side-effect:** The first successful tutor turn auto-transitions concept mastery from `not_started` to `learning`. If the concept was already `needs_review`, a new tutor retry also resets it to `learning`.

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversations`

Create a fresh tutor conversation thread for this concept. This does not send a
message; it gives the learner a clean thread to start from.

**Response 200:**

```json
{
  "id": "uuid",
  "title": "New thread",
  "preview": null,
  "message_count": 0,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversations`

List tutor conversation threads for this concept, newest first.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Max thread summaries to return |

**Response 200:**

```json
{
  "conversations": [
    {
      "id": "uuid",
      "title": "First learner question, truncated",
      "preview": "Latest visible message, truncated | null",
      "message_count": 2,
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ]
}
```

---

#### `PATCH /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversations/{conversation_id}`

Rename one tutor conversation thread for this concept.

**Request body:**

```json
{ "title": "Renamed thread" }
```

**Response 200:**

```json
{
  "id": "uuid",
  "title": "Renamed thread",
  "preview": "Latest visible message, truncated | null",
  "message_count": 2,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

#### `DELETE /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversations/{conversation_id}`

Delete one tutor conversation thread for this concept.

**Response 204:** no body.

---

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversation`

Retrieve one tutor conversation thread for a concept in the current workspace.
When `conversation_id` is omitted, the latest updated thread is returned. If no
thread exists yet, the response has `conversation_id: null` and no messages.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `conversation_id` | uuid | latest thread | Specific thread to load |
| `limit` | int | 20 | Max messages to return |

**Response 200:**

```json
{
  "conversation_id": "uuid | null",
  "messages": ["ConversationMessage"]
}
```

---

### Sources

#### `GET /api/workspaces/{workspace_id}/sources`

Planned source listing endpoint. It is not implemented in the current backend slice.

**Query params:**

| Param | Type | Description |
|---|---|---|
| `origin` | SourceOrigin | Filter by origin |
| `access` | SourceAccess | Filter by access level |

**Response 200:**

```json
{
  "sources": ["SourceRecord"]
}
```

---

#### `POST /api/workspaces/{workspace_id}/sources/upload`

Upload a source file. Stored as a private source. Defaults: `origin: user_upload`, `access: private`, `include_on_public_export: false`.

Supported content types are parsed synchronously: `text/plain`, `text/markdown`, and `application/pdf` (via pdfplumber). The file is chunked into `SourceChunk` rows. If `EMBEDDING_PROVIDER` is configured (not `"disabled"`), chunk embeddings are computed and stored. If `trail_id` is provided, the source is automatically linked to matching concepts in the trail via keyword matching. Unsupported content types set `status: "failed"` on the revision. No raw private file text, storage object key, or content hash is returned by this endpoint.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
| `file` | binary | yes | File to upload |
| `title` | string | no | Defaults to filename |
| `trail_id` | uuid | no | When provided, auto-links parsed chunks to matching concepts in the trail |

**Response 201:** `SourceUploadResponse`

**Errors:**
- `400 invalid_input` — empty file or invalid upload metadata
- `404 not_found` — workspace does not exist
- `413 invalid_input` — uploaded file exceeds the current 50 MB limit
- `500 storage_error` — local private storage failed before a valid source state could be committed

---

#### `GET /api/workspaces/{workspace_id}/sources/{source_id}`

Read private uploaded-source metadata and latest sanitized revision summary for one workspace-scoped upload. This endpoint does not return raw uploaded bytes, parsed text, chunks, embeddings, storage object keys, or content hashes. Non-upload source records use the existing concept/detail metadata surfaces for now.

**Response 200:** `SourceUploadResponse`

**Errors:**
- `404 not_found` — source does not exist in the workspace or has no revision

---

### Research

Automated `POST /research` is deferred until a real search/provider-tool stack exists. The current Phase 7 backend slice only preserves imported research traces and exposes stored trace retrieval.

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/research`

Get the stored research trace for a Trail. Returns `{ "trace": {} }` when no trace has been imported or stored.

**Response 200:**

```json
{
  "trace": {
    "topic": "string",
    "generated_by": "string",
    "queries": ["string"],
    "selected_public_sources": [
      {"source_id": "string", "reason": "string"}
    ],
    "excluded_sources": [
      {"title": "string", "reason": "string"}
    ]
  }
}
```

---

### Hydration

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/hydrate`

Record private hydration intent for a Trail. The current Phase 7 implementation does not fetch, chunk, embed, or index remote content. It creates private workspace-scoped `SourceRecord` placeholders from selected imported public research sources and/or model-knowledge intent. These records are `include_on_public_export=false` and are excluded by the public export sanitizer.

**Request body:**

```json
{
  "concept_id": "uuid | null",
  "source_ids": ["uuid"],
  "use_model_knowledge": "bool (default: false)"
}
```

**Response 200:**

```json
{
  "hydrated_concepts": "int",
  "private_records_created": "int",
  "skipped_sources": [
    {"source_id": "uuid", "reason": "string"}
  ]
}
```

---

### Trail Pack Export

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/export`

Export a Trail as a safe public Trail Pack. Runs the export sanitizer before generating output.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `format` | `json` | `json` | Output format for the Phase 6 slice |

**Response 200:**

```json
{
  "pack": {
    "manifest": {},
    "graph": {},
    "concepts": {},
    "sources": [],
    "research_trace": {}
  },
  "report": "ExportReport"
}
```

The sanitizer enforces these rules before generating the response:
- `user_upload` sources are excluded.
- `private` or `restricted` sources are excluded.
- Source revisions, chunks, embeddings, private notes, chat history, and mastery records are excluded.
- Only `research_agent` + `public` + `include_on_public_export=true` sources appear, as links/metadata only.

---

### Trail Pack Import

#### `POST /api/workspaces/{workspace_id}/trail-packs/import`

Import a Trail Pack into a workspace. Forks the Trail. Validates the pack before import.

**Request:** `application/json`

The endpoint accepts either the raw Trail Pack object or the Phase 6 export wrapper shape:

```json
{
  "pack": {},
  "report": {}
}
```

**Validation rejects:**
- Missing required manifest fields.
- Unknown node references in edges.
- Duplicate node ids.
- Duplicate concept slugs in the imported trail.
- Unknown `concept_level` values.
- Private or uploaded-like source entries.
- Packs containing source revisions, object keys, content hashes, raw chunks, embeddings, uploaded files, private notes, mastery records, chat history, raw source prose, generated summaries, or generated quizzes.
- Malformed JSON.

If an older content-light pack lacks the additive round-trip fields, import uses conservative defaults and reports warnings: `topic = manifest.title`, `goal = "Imported from Trail Pack"`, `target_depth = "understand"`, missing node `difficulty = "beginner"`, and missing node `bloom_level = "understand"`.

**Response 201:**

```json
{
  "trail": "Trail",
  "graph": "TrailGraph",
  "report": "ImportReport"
}
```

---

## Artifacts (Phase 15)

Artifacts are workspace + trail scoped learning artifacts rendered from a validated, versioned envelope (`artifact_version`, `kind`, `title`, `caption?`, required `text_fallback`, `provenance{source_ids, visibility, citations[]}`, kind-specific `data`). Shipped kinds: `worked_example`, `comparison_card`, `timeline`, `mini_graph`, `simulation_slider`. The frontend renders through a `kind -> component` registry that degrades to `text_fallback` on any unknown kind, invalid data, or render error. Generation (the builder sub-agent + detached generation) is implemented; see the build endpoints below.

Provenance/export: concept-level / `local_only` artifacts are excluded from public Trail Pack export (like the primer). `source_derived` artifacts are public-export-eligible only if EVERY contributing source passes the source-level export gate AND none is `user_upload` (all-or-nothing, fail-closed).

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/artifacts`

List artifacts for a trail. Optional `?concept_id=<uuid>` filters to one concept.

**Response 200:** `{ "artifacts": [ArtifactRead] }` where `ArtifactRead = { id, workspace_id, trail_id, concept_id, artifact_type, title, visibility, payload, created_at }` and `payload` is the stored envelope.

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/artifacts/build`

Generate (or reuse) an artifact via the backend-owned artifact-builder sub-agent. **Body:** `ArtifactBuildRequest = { "kind": ArtifactKind, "concept_id": "<uuid> | null", "force_new": false }`. The builder runs a bounded retrieval loop (reusing the tutor retrieval tools under `tutor_tool_call_budget`) with exactly one repair attempt, drops citations that do not map to a retrieved `source_revision_id`, downgrades zero-citation payloads to `local_only`, and persists the result. Advisory-lock dedupe serializes concurrent builds for the same target. **Response 200:** `ArtifactRead`. **404** when the trail/concept is out of scope; **502** error envelope (`code: "llm_error"`) when generation fails.

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/artifacts/build/stream`

LIVE-preview variant of `/build`. Streams SSE status while a DETACHED background task (own DB session, cancel-safe, lifespan-managed `ArtifactGenerationManager`) performs and persists the generation, so it completes even if the client disconnects. `force_new` is rejected here (**400**) — use `POST /build` for forced regeneration so the single-flight manager never reconciles force-vs-dedupe races. **Response:** `text/event-stream`.

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/artifacts/{artifact_id}`

Retrieve one artifact. **Response 200:** `ArtifactRead`. **404** error envelope when the artifact is missing or out of workspace/trail scope.

---

## Pins / Saved (Phase 15b)

Polymorphic pins let a learner "save" supported items to a Trail. Pins are workspace + trail scoped (per-USER == per-workspace until auth lands) and aggregate across supported `item_type`s (`artifact`, `quiz_attempt`, `flashcard`). Pin/unpin are IDEMPOTENT: a second pin of the same item is a no-op (a unique constraint on `(workspace_id, trail_id, item_type, item_id)` guarantees one row), and unpinning a non-pinned item is a no-op. Pinning validates the referenced item belongs to the same workspace+trail (no cross-trail / cross-workspace pins); a mismatch returns a **404** error envelope.

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/pins`

Pin an item. **Body:** `{ "item_type": "artifact" | "quiz_attempt" | "flashcard", "item_id": "<uuid>" }` (for `flashcard`, `item_id` is the deck id). **Response 200:** `{ "status": "pinned" }` (idempotent). **404** error envelope when the trail or referenced item is missing / out of scope.

#### `DELETE /api/workspaces/{workspace_id}/trails/{trail_id}/pins`

Unpin an item. **Query:** `?item_type=<artifact|quiz_attempt|flashcard>&item_id=<uuid>`. **Response 200:** `{ "status": "unpinned" }` (idempotent; a no-op when the item is not pinned). **404** error envelope when the trail is missing / out of scope.

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/pins`

List pinned items for a trail, grouped by type. **Response 200:** `{ "artifacts": [ArtifactRead], "quiz_attempts": [QuizAttemptRead], "flashcards": [FlashcardDeckRead] }` — the existing read shapes so the frontend reuses `ArtifactRenderer` and the quiz-attempt rendering. Pins whose target row no longer resolves in scope are excluded. **404** error envelope when the trail is missing / out of scope.

---

## Flashcards (Phase 15c)

Flashcards are a DEDICATED subsystem (not a generic artifact). Each concept owns at most one `FlashcardDeck` (the retrievable / pinnable unit, like a quiz attempt); the deck is the canonical relational store. Generation is source-grounded (every card's `source_ref` must map to a real retrieved `source_revision_id`, else it is dropped), atomic, and dedup-aware via a deterministic embedding-similarity gate; the generator can decline with `exhausted: true` + a `reason` instead of padding. Scheduling v1 is LEITNER (`box` + geometric `interval_days`; recall-first swipe: yes => box+1 capped, no => box 1 with `lapses++`); the extra columns (`last_reviewed`, `due`, `reps`, `lapses`) keep the schema FSRS-ready. CSV export is Anki-compatible and EXPORT-ONLY (not the source of truth); JSON export round-trips the deck.

`FlashcardRead = { id, deck_id, front, back, hint, source_ref, card_type, box, interval_days, last_reviewed, due, reps, lapses, created_at }`. `FlashcardDeckRead = { id, workspace_id, trail_id, concept_id, title, created_at, updated_at, cards: [FlashcardRead] }`.

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/flashcards/generate`

Generate (or extend) the concept's deck. **Body:** `{ "extend": false, "force": false }` (both default off). With neither flag an existing populated deck is returned unchanged (idempotent); `extend` appends new non-duplicate cards; `force` regenerates from scratch. **Response 200:** `{ "deck": FlashcardDeckRead, "exhausted": bool, "reason": string }` — `exhausted` is the generator's honest decline (e.g. no linked source material, or the deck soft-cap is reached). **404** error envelope when the concept is missing / out of scope; **502** error envelope on generator failure.

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/flashcards`

Retrieve the concept's deck + cards with scheduling state. **Response 200:** `FlashcardDeckRead`. **404** error envelope when no deck exists or the concept is out of scope.

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/flashcards/{card_id}/review`

Apply one Leitner recall-first swipe. **Body:** `{ "recalled": true | false }` — `true` promotes the card (box+1 capped, `reps++`, recomputes `interval_days`/`due`); `false` resets to box 1 and increments `lapses` (`reps++`). **Response 200:** the updated `FlashcardRead`. **404** error envelope when the card / concept is missing or out of scope.

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/flashcards/export`

Export the deck. **Query:** `?format=csv` (default) or `?format=json`. CSV is an Anki-compatible export (`#separator:Comma`, `#columns:front,back,hint,source_ref,card_type`) returned as `text/csv` with a `Content-Disposition` attachment header; JSON returns the round-trippable deck as `application/json`. **400** error envelope when `format` is not `csv`/`json`; **404** error envelope when no deck exists or the concept is out of scope.

---

## Streaming Notes

The tutor chat endpoint uses SSE. Clients should:

1. Open the connection with a `POST` request (body is the chat payload).
2. Read events line by line (`data: ...`).
3. Handle optional `status`, `thinking`, `tool_call`, and `tool_result` events as reasoning/activity UI.
4. Handle `mode` to update the tutor-mode indicator. It arrives before visible tokens, but not necessarily before reasoning/tool activity.
5. Accumulate `token` events to display streamed text.
6. On `done`, persist the `conversation_id` for future turns and rehydrate from `reasoning_parts` when available.
7. On `error`, display the message and close the connection.

FastAPI implementation should use `StreamingResponse` with `media_type="text/event-stream"` and an async generator.
