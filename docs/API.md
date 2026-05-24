# CoLearni API Contract

## Overview

Application routes are prefixed with `/api`. The health endpoint is the only planned unprefixed route. The backend is a FastAPI application. Routes stay thin: they validate input, call a service, and return a response. No business logic in routes.

## Workspace Scoping

For the local-ready MVP there is no auth. The active workspace is identified by `workspace_id` in the URL path. A default workspace is auto-created on first run. Clients should store the workspace id locally (e.g. in localStorage) and include it in all requests.

Every endpoint that operates on workspace data uses the pattern:

```
/api/workspaces/{workspace_id}/...
```

This keeps the API SaaS-compatible without requiring auth in the MVP.

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
  "type": "multiple_choice | short_answer | long_answer",
  "prompt": "string",
  "mastery_label": "string",
  "difficulty": "QuizQuestionDifficulty",
  "options": ["string"]
}
```

`options` is only present for `multiple_choice` questions. New API responses emit only the current question types above; older persisted `explain` / `apply` / `compare` snapshots are normalized to `long_answer` when read back through the API.

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

### ConversationMessage

```json
{
  "id": "uuid",
  "role": "user | assistant",
  "content": "string",
  "reasoning": "string | null",
  "reasoning_parts": [
    {
      "kind": "status | thinking | tool_call | tool_result",
      "status": "TutorStreamStatus | null",
      "text": "string | null",
      "name": "string | null",
      "mode": "TutorMode | null",
      "result": "string | null"
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
| 422 | `validation_error` | Pydantic validation failed |
| 500 | `llm_error` | LLM call failed or returned malformed output |
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
  "max_nodes": "int | optional, default 40, min 10, max 100"
}
```

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

Generate a new Trail while streaming progress events to the frontend. This endpoint is a local-ready progress helper for the current UI. It is **not durable across page refreshes**; Phase 16 demo polish replaces this with backend jobs and polling.

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
  "sources": ["SourceRecord"]
}
```

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
  "conversation_id": "uuid | null"
}
```

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
{ "type": "status", "status": "thinking | calling_tool | tool_called | tool_complete | responding | retrying_without_thinking" }
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

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversation`

Retrieve the conversation history for a concept in the current workspace.

**Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
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

List all source records in a workspace.

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

This endpoint supports hydration/import workflows after the core learning loop and safe Trail Pack sharing foundations exist. Do not implement it as the first milestone, and do not build PDF ingestion before Trail generation, graph viewing, tutor chat, mastery, safe export, Trail Pack import/fork, and provider tool foundations are working.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | binary | yes | File to upload |
| `title` | string | no | Defaults to filename |

**Response 201:** `SourceRecord`

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

Record private hydration intent for a Trail. The current Phase 7 MVP does not fetch, chunk, embed, or index remote content. It creates private workspace-scoped `SourceRecord` placeholders from selected imported public research sources and/or model-knowledge intent. These records are `include_on_public_export=false` and are excluded by the public export sanitizer.

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
- Chunks, embeddings, private notes, chat history, and mastery records are excluded.
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
- Packs containing raw chunks, embeddings, uploaded files, private notes, mastery records, chat history, raw source prose, generated summaries, or generated quizzes.
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
