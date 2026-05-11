# CoLearni API Contract

## Overview

All routes are prefixed with `/api`. The backend is a FastAPI application. Routes stay thin: they validate input, call a service, and return a response. No business logic in routes.

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
TutorMode = Literal["socratic", "direct", "repair", "quiz_prompt", "explore"]

# Source origins
SourceOrigin = Literal["research_agent", "user_upload", "manual", "system"]

# Source access levels
SourceAccess = Literal["public", "private", "restricted", "unknown"]

# Difficulty levels
Difficulty = Literal["beginner", "intermediate", "advanced"]

# Target depth (same values as BloomLevel, used on Trail creation)
TargetDepth = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]

# Quiz type
QuizType = Literal["level_up", "practice"]
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
  "id": "uuid",
  "workspace_id": "uuid",
  "concept_id": "uuid",
  "status": "MasteryStatus",
  "bloom_level": "BloomLevel",
  "score": "float (0.0–1.0)",
  "updated_at": "ISO 8601 datetime"
}
```

### QuizQuestion

```json
{
  "id": "string (stable within a card)",
  "type": "explain | apply | compare",
  "prompt": "string",
  "mastery_label": "string"
}
```

### LevelUpCard

```json
{
  "concept_id": "uuid",
  "quiz_type": "QuizType",
  "questions": ["QuizQuestion"]
}
```

### GradeResult

```json
{
  "passed": "bool",
  "score": "float (0.0–1.0)",
  "feedback": "string",
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
  "mode": "TutorMode",
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
  "target_depth": "TargetDepth"
}
```

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
  "children": ["ConceptNode"],
  "related": ["ConceptNode"],
  "mastery": "MasteryRecord",
  "sources": ["SourceRecord"]
}
```

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/level-up`

Generate a level-up quiz card for a concept. Cards are generated from `mastery_check_labels` and never include private/source-derived content.

**Response 200:** `LevelUpCard` (with `quiz_type: "level_up"`)

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/grade`

Grade a level-up quiz attempt. If passed, updates mastery to `mastered`. If failed, updates to `needs_review`.

**Request body:**

```json
{
  "answers": [
    {"question_id": "string", "answer": "string"}
  ]
}
```

**Response 200:** `GradeResult`

Note: This endpoint only updates mastery for `level_up` attempts. See `/practice/grade` for practice attempts.

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/practice`

Generate a practice quiz card. Identical to level-up card generation but marks the card as `quiz_type: "practice"`.

**Response 200:** `LevelUpCard` (with `quiz_type: "practice"`)

---

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/practice/grade`

Grade a practice quiz attempt. Stores the attempt and returns feedback but **never updates mastery status**.

**Request body:**

```json
{
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
Emitted first, before tokens, so the client knows which mode was selected.

```json
{ "type": "token", "content": "string" }
```
Streamed tokens as they arrive from the LLM.

```json
{ "type": "done", "conversation_id": "uuid", "message": "ConversationMessage" }
```
Emitted once at the end. Includes the full assembled message for storage.

```json
{ "type": "error", "code": "string", "message": "string" }
```
Emitted if the LLM call fails. The stream then closes.

**Mastery side-effect:** The first message in a conversation sets concept mastery to `learning` if it is currently `not_started`.

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

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | binary | yes | File to upload |
| `title` | string | no | Defaults to filename |

**Response 201:** `SourceRecord`

---

### Research

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/research`

Run the research agent on the Trail. Searches public sources, selects relevant links, and stores a research trace. Stores links and metadata only — never copied content.

**Request body:**

```json
{
  "concept_id": "uuid | null",
  "max_sources": "int (default: 5, max: 20)"
}
```

**Response 200:**

```json
{
  "sources_found": "int",
  "sources_selected": "int",
  "trace": {
    "topic": "string",
    "queries": ["string"],
    "selected_sources": ["SourceRecord"],
    "excluded_sources": [
      {"title": "string", "reason": "string"}
    ]
  }
}
```

---

#### `GET /api/workspaces/{workspace_id}/trails/{trail_id}/research`

Get the stored research trace for a Trail.

**Response 200:**

```json
{
  "trace": {
    "topic": "string",
    "generated_by": "string",
    "queries": ["string"],
    "selected_sources": ["SourceRecord"],
    "excluded_sources": [
      {"title": "string", "reason": "string"}
    ]
  }
}
```

---

### Hydration

#### `POST /api/workspaces/{workspace_id}/trails/{trail_id}/hydrate`

Hydrate a Trail with private local evidence. Fetches allowed public sources and indexes content privately. Hydrated content stays private.

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
| `format` | `json` or `yaml` | `json` | Output format |

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
- Only `research_agent` + `public` sources appear, as links/metadata only.

---

### Trail Pack Import

#### `POST /api/workspaces/{workspace_id}/trail-packs/import`

Import a Trail Pack into a workspace. Forks the Trail. Validates the pack before import.

**Request:** `multipart/form-data` or `application/json`

| Field | Type | Required | Description |
|---|---|---|---|
| `pack` | JSON object or file | yes | Trail Pack payload |

**Validation rejects:**
- Missing required manifest fields.
- Unknown node references in edges.
- Duplicate node ids.
- Unknown `concept_level` values.
- Packs containing raw chunks, embeddings, uploaded files, private notes, or mastery records.
- Malformed YAML/JSON.

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
3. Handle `mode` event to update UI indicator.
4. Accumulate `token` events to display streamed text.
5. On `done`, persist the `conversation_id` for future turns.
6. On `error`, display the message and close the connection.

FastAPI implementation should use `StreamingResponse` with `media_type="text/event-stream"` and an async generator.
