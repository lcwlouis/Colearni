# docs/API.md

## Backend HTTP API Reference

This document is the canonical reference for all FastAPI HTTP endpoints exposed by `apps/api`.

### Conventions

- Base URL: `http://localhost:8000`
- Authentication: Bearer session token (obtained via `/auth/verify`). Some routes require workspace membership.
- Transport: JSON unless otherwise noted
- Validation errors are returned as HTTP `422` (`HTTPValidationError` schema)

### Endpoint Index

- `GET /healthz`
- `POST /auth/magic-link`
- `POST /auth/verify`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /auth/me/tutor-profile`
- `POST /documents/upload`
- `GET /workspaces`
- `POST /workspaces`
- `GET /workspaces/{ws_id}`
- `PATCH /workspaces/{ws_id}/settings`
- `POST /workspaces/{ws_id}/chat/respond`
- `POST /workspaces/{ws_id}/chat/sessions`
- `GET /workspaces/{ws_id}/chat/sessions`
- `DELETE /workspaces/{ws_id}/chat/sessions/{session_id}`
- `PATCH /workspaces/{ws_id}/chat/sessions/{session_id}`
- `GET /workspaces/{ws_id}/chat/sessions/{session_id}/messages`
- `GET /workspaces/{ws_id}/graph/concepts`
- `GET /workspaces/{ws_id}/graph/concepts/{concept_id}`
- `GET /workspaces/{ws_id}/graph/concepts/{concept_id}/subgraph`
- `GET /workspaces/{ws_id}/graph/lucky`
- `GET /workspaces/{ws_id}/knowledge-base/documents`
- `POST /workspaces/{ws_id}/knowledge-base/documents/upload`
- `DELETE /workspaces/{ws_id}/knowledge-base/documents/{document_id}`
- `POST /workspaces/{ws_id}/knowledge-base/documents/{document_id}/reprocess`
- `POST /workspaces/{ws_id}/practice/flashcards`
- `POST /workspaces/{ws_id}/practice/flashcards/rate`
- `POST /workspaces/{ws_id}/practice/flashcards/stateful`
- `POST /workspaces/{ws_id}/practice/quizzes`
- `POST /workspaces/{ws_id}/practice/quizzes/{quiz_id}/submit`
- `POST /workspaces/{ws_id}/quizzes/level-up`
- `POST /workspaces/{ws_id}/quizzes/{quiz_id}/submit`
- `GET /workspaces/{ws_id}/readiness/snapshot`
- `GET /workspaces/{ws_id}/research/candidates`
- `PATCH /workspaces/{ws_id}/research/candidates/{candidate_id}`
- `POST /workspaces/{ws_id}/research/runs`
- `GET /workspaces/{ws_id}/research/runs`
- `POST /workspaces/{ws_id}/research/sources`
- `GET /workspaces/{ws_id}/research/sources`
- `DELETE /workspaces/{ws_id}/research/sources/{source_id}`

### GET /healthz

Tag/group: untagged

Purpose: liveness probe for the backend service.

Request contract:

- Path params: none
- Query params: none
- Body: none

Success responses:

- `200 OK` with payload `{"status": "ok"}`

Error responses:

- none application-specific

Example:

```bash
curl -sS http://localhost:8000/healthz
```

```json
{
  "status": "ok"
}
```

### POST /auth/magic-link

Tag/group: `auth`

Purpose: issue a magic-link token for the given email address. In dev mode the token is echoed back; in production it would be emailed.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `email` | JSON body | string (email) | yes | valid email address |

Success responses:

- `200 OK` with `MagicLinkResponse`

`MagicLinkResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `message` | string | confirmation message |
| `debug_token` | string/null | raw token echoed in dev mode |

Error responses:

- `422 Unprocessable Entity` for validation failures

### POST /auth/verify

Tag/group: `auth`

Purpose: exchange a magic-link token for a session token and user record.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `token` | JSON body | string | yes | non-empty magic-link token |

Success responses:

- `200 OK` with `VerifyTokenResponse`

`VerifyTokenResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `session_token` | string | Bearer session token |
| `user` | object | `UserPublic` with `public_id`, `email`, `display_name` |

Error responses:

- `401 Unauthorized` when token is invalid or expired
- `422 Unprocessable Entity` for validation failures

### POST /auth/logout

Tag/group: `auth`

Purpose: revoke the current session token. Requires Bearer auth.

Request contract:

- Body: none
- Headers: `Authorization: Bearer <session_token>`

Success responses:

- `204 No Content`

Error responses:

- `401 Unauthorized` when not authenticated

### GET /auth/me

Tag/group: `auth`

Purpose: return the authenticated user profile.

Request contract:

- Body: none
- Headers: `Authorization: Bearer <session_token>`

Success responses:

- `200 OK` with `UserPublic`

`UserPublic` fields:

| Field | Type | Notes |
|---|---|---|
| `public_id` | string | UUID public identifier |
| `email` | string | user email |
| `display_name` | string/null | optional display name |

Error responses:

- `401 Unauthorized` when not authenticated

### GET /auth/me/tutor-profile

Tag/group: `auth`

Purpose: return or initialize the tutor profile for the authenticated user.

Request contract:

- Body: none
- Headers: `Authorization: Bearer <session_token>`

Success responses:

- `200 OK` with `TutorProfileResponse`

`TutorProfileResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `readiness_summary` | string | aggregated readiness notes |
| `learning_style_notes` | string | inferred learning style |
| `last_activity_at` | string/null | ISO timestamp |

Error responses:

- `401 Unauthorized` when not authenticated

### POST /workspaces

Tag/group: `workspaces`

Purpose: create a workspace and add the current user as owner-member.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `name` | JSON body | string | yes | 1–255 chars |
| `description` | JSON body | string | no | optional description |

Success responses:

- `201 Created` with `WorkspaceSummary`

`WorkspaceSummary` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace row ID |
| `public_id` | string | UUID public identifier |
| `name` | string | workspace name |
| `description` | string/null | optional description |

Error responses:

- `401 Unauthorized` when not authenticated
- `422 Unprocessable Entity` for validation failures

### GET /workspaces

Tag/group: `workspaces`

Purpose: list workspaces the current user is a member of.

Request contract:

- Body: none
- Headers: `Authorization: Bearer <session_token>`

Success responses:

- `200 OK` with `WorkspaceListResponse`

Error responses:

- `401 Unauthorized` when not authenticated

### GET /workspaces/{ws_id}

Tag/group: `workspaces`

Purpose: get workspace details including settings (requires membership).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `ws_id` | path | integer | yes | workspace ID |

Success responses:

- `200 OK` with `WorkspaceDetail`

`WorkspaceDetail` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace row ID |
| `public_id` | string | UUID public identifier |
| `name` | string | workspace name |
| `description` | string/null | optional description |
| `settings` | object | JSONB settings blob |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `404 Not Found` when workspace does not exist

### PATCH /workspaces/{ws_id}

Tag/group: `workspaces`

Purpose: update workspace name and description.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `ws_id` | path | string | yes | workspace public ID |
| `name` | body | string | yes | new workspace name |
| `description` | body | string/null | no | optional description |

Success responses:

- `200 OK` with `WorkspaceDetail`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `404 Not Found` when workspace does not exist

### PATCH /workspaces/{ws_id}/settings

Tag/group: `workspaces`

Purpose: merge new settings into the workspace JSONB settings column.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `ws_id` | path | integer | yes | workspace ID |
| `settings` | JSON body | object | yes | key-value pairs to merge |

Success responses:

- `200 OK` with `WorkspaceDetail`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `404 Not Found` when workspace does not exist
- `422 Unprocessable Entity` for validation failures

### POST /workspaces/{ws_id}/chat/respond

Tag/group: `chat`

Purpose: generate one verified assistant response envelope with evidence/citations and grounding policy applied.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `query` | JSON body | string | yes | non-empty |
| `user_id` | JSON body | integer | no | `> 0`; used with `concept_id` for mastery gating |
| `concept_id` | JSON body | integer | no | `> 0`; used with `user_id` for mastery gating |
| `top_k` | JSON body | integer | no | default `5`, minimum `1` |
| `grounding_mode` | JSON body | enum | no | `"hybrid"` or `"strict"`; defaults from app settings |

Success responses:

- `200 OK` with `AssistantResponseEnvelope`

`AssistantResponseEnvelope` key fields:

| Field | Type | Notes |
|---|---|---|
| `kind` | enum | `"answer"` or `"refusal"` |
| `text` | string | assistant output text |
| `grounding_mode` | enum | `"hybrid"` or `"strict"` |
| `evidence` | array | evidence snippets with provenance metadata |
| `citations` | array | citations linked to `evidence_id` |
| `refusal_reason` | enum/null | `"insufficient_evidence"` or `"invalid_citations"` when `kind="refusal"` |

Error responses:

- `422 Unprocessable Entity` for request validation failures

Example:

```bash
curl -sS http://localhost:8000/chat/respond \
  -H 'content-type: application/json' \
  -d '{
    "workspace_id": 7,
    "query": "Describe linear maps",
    "user_id": 5,
    "concept_id": 11,
    "grounding_mode": "strict"
  }'
```

```json
{
  "kind": "answer",
  "text": "SOCRATIC: What property must hold for both addition and scalar multiplication?",
  "grounding_mode": "strict",
  "evidence": [
    {
      "evidence_id": "e1",
      "source_type": "workspace",
      "content": "Linear maps preserve vector addition and scalar multiplication.",
      "document_id": 9,
      "chunk_id": 21,
      "chunk_index": 0,
      "document_title": "Linear Algebra Notes",
      "source_uri": "file://notes.md",
      "score": 0.93
    }
  ],
  "citations": [
    {
      "citation_id": "c1",
      "evidence_id": "e1",
      "label": "From your notes",
      "quote": "Linear maps preserve vector addition and scalar multiplication."
    }
  ],
  "refusal_reason": null
}
```

### POST /workspaces/{ws_id}/chat/sessions

Tag/group: `chat`

Purpose: create a chat session for one `workspace_id` + `user_id`.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `user_id` | JSON body | integer | yes | `> 0` |
| `title` | JSON body | string | no | optional custom title |

Success responses:

- `201 Created` with `ChatSessionSummary`

Error responses:

- `422 Unprocessable Entity` for validation failures

### GET /workspaces/{ws_id}/chat/sessions

Tag/group: `chat`

Purpose: list sessions for one `workspace_id` + `user_id`.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `user_id` | query | integer | yes | `> 0` |
| `limit` | query | integer | no | default `30`, range `1..100` |

Success responses:

- `200 OK` with `ChatSessionListResponse`

Error responses:

- `422 Unprocessable Entity` for validation failures

### GET /workspaces/{ws_id}/chat/sessions/{session_id}/messages

Tag/group: `chat`

Purpose: fetch timeline messages for one session.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `session_id` | path | integer | yes | `> 0` |
| `workspace_id` | query | integer | yes | `> 0` |
| `user_id` | query | integer | yes | `> 0` |
| `limit` | query | integer | no | default `300`, range `1..1000` |

Success responses:

- `200 OK` with `ChatMessagesResponse`

Error responses:

- `404 Not Found` when the session is not scoped to workspace/user
- `422 Unprocessable Entity` for validation failures

### PATCH /workspaces/{ws_id}/chat/sessions/{session_id}

Tag/group: `chat`

Purpose: rename (update the title of) a chat session.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `session_id` | path | string | yes | UUID public_id |
| `title` | body | string | yes | 1-120 chars |

Success responses:

- `200 OK` with `ChatSessionSummary`

Error responses:

- `404 Not Found` when the session is not scoped to workspace/user
- `422 Unprocessable Entity` for validation failures

### DELETE /workspaces/{ws_id}/chat/sessions/{session_id}

Tag/group: `chat`

Purpose: delete a chat session and its timeline messages.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `session_id` | path | integer | yes | `> 0` |
| `workspace_id` | query | integer | yes | `> 0` |
| `user_id` | query | integer | yes | `> 0` |

Success responses:

- `204 No Content`

Error responses:

- `404 Not Found` when the session is not scoped to workspace/user
- `422 Unprocessable Entity` for validation failures

### POST /documents/upload

Tag/group: `documents`

Purpose: ingest `.md`, `.txt`, or text-extractable `.pdf` content into a workspace.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `uploaded_by_user_id` | query | integer | yes | `> 0` |
| `title` | query | string | no | optional explicit title |
| `source_uri` | query | string | no | optional source URI |

Body transport options:

- `multipart/form-data` with file part named `file` (required)
- raw body with content type `text/plain`, `text/markdown`, or `application/pdf`

Success responses:

- `201 Created` with `DocumentUploadResponse` when a new document is created
- `200 OK` with `DocumentUploadResponse` when duplicate content is detected (`created=false`)

`DocumentUploadResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `document_id` | integer | document row ID |
| `workspace_id` | integer | owning workspace |
| `title` | string | resolved title |
| `mime_type` | string | canonical MIME type |
| `content_hash` | string | SHA-256 hash of normalized text |
| `chunk_count` | integer | number of persisted chunks |
| `created` | boolean | `true` for new ingest, `false` for duplicate |

Error responses:

- `415 Unsupported Media Type` when payload is not `.md`, `.txt`, or `.pdf`, or text decoding fails
- `422 Unprocessable Entity` for semantic validation issues (missing multipart `file`, empty body/file, no extractable text layer, no chunks)
- `503 Service Unavailable` when embedding or graph dependencies are required but unavailable

Example (multipart):

```bash
curl -sS -X POST \
  'http://localhost:8000/documents/upload?workspace_id=1&uploaded_by_user_id=1&title=Notes' \
  -F 'file=@./notes.md;type=text/markdown'
```

```json
{
  "document_id": 10,
  "workspace_id": 1,
  "title": "Notes",
  "mime_type": "text/markdown",
  "content_hash": "abc123...",
  "chunk_count": 2,
  "created": true
}
```

### GET /workspaces/{ws_id}/graph/concepts

Tag/group: `graph`

Purpose: list canonical concepts in a workspace, optionally enriched with user mastery.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `user_id` | query | integer | no | `> 0`; includes mastery fields when provided |
| `q` | query | string | no | optional name/alias search |
| `limit` | query | integer | no | default `50`, range `1..200` |

Success responses:

- `200 OK` with `GraphConceptListResponse`

Error responses:

- `422 Unprocessable Entity` for validation failures

### GET /workspaces/{ws_id}/graph/concepts/{concept_id}

Tag/group: `graph`

Purpose: fetch detail for one canonical concept in a workspace.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `concept_id` | path | integer | yes | `> 0` |
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `200 OK` with `GraphConceptDetailResponse`

`GraphConceptDetailResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `concept` | object | concept payload |
| `concept.concept_id` | integer | canonical concept ID |
| `concept.canonical_name` | string | canonical label |
| `concept.description` | string | concept summary |
| `concept.aliases` | string[] | known aliases |
| `concept.degree` | integer | active incident edge count |

Error responses:

- `404 Not Found` when the concept is not in the workspace
- `422 Unprocessable Entity` for validation failures

Example:

```bash
curl -sS 'http://localhost:8000/graph/concepts/42?workspace_id=7'
```

```json
{
  "workspace_id": 7,
  "concept": {
    "concept_id": 42,
    "canonical_name": "Linear Map",
    "description": "Preserves vector addition and scalar multiplication.",
    "aliases": ["Linear Transformation"],
    "degree": 6
  }
}
```

### GET /workspaces/{ws_id}/graph/concepts/{concept_id}/subgraph

Tag/group: `graph`

Purpose: return a bounded k-hop neighborhood for a seed concept.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `concept_id` | path | integer | yes | `> 0` |
| `workspace_id` | query | integer | yes | `> 0` |
| `max_hops` | query | integer | no | default `1`, range `1..3` |
| `max_nodes` | query | integer | no | default `40`, range `1..80` |
| `max_edges` | query | integer | no | default `80`, range `1..160` |

Success responses:

- `200 OK` with `GraphSubgraphResponse`

`GraphSubgraphResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `root_concept_id` | integer | requested concept ID |
| `max_hops` | integer | applied hop cap |
| `nodes` | array | subgraph nodes with `hop_distance` |
| `edges` | array | bounded edge set, ordered by weight desc |

Error responses:

- `404 Not Found` when the concept is not in the workspace
- `422 Unprocessable Entity` for validation failures (including bounds outside caps)

Example:

```bash
curl -sS \
  'http://localhost:8000/graph/concepts/42/subgraph?workspace_id=7&max_hops=2&max_nodes=20&max_edges=30'
```

```json
{
  "workspace_id": 7,
  "root_concept_id": 42,
  "max_hops": 2,
  "nodes": [
    {
      "concept_id": 42,
      "canonical_name": "Linear Map",
      "description": "Preserves vector operations.",
      "hop_distance": 0
    }
  ],
  "edges": []
}
```

### GET /workspaces/{ws_id}/graph/full

Tag/group: `graph`

Purpose: retrieve the full knowledge graph for a workspace (capped to prevent overload).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `ws_id` | path | string | yes | workspace public ID |
| `max_nodes` | query | integer | no | default 100, range 1–500 |
| `max_edges` | query | integer | no | default 300, range 1–1000 |

Success responses:

- `200 OK` with `GraphSubgraphResponse`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### GET /workspaces/{ws_id}/graph/lucky

Tag/group: `graph`

Purpose: choose one suggested concept using either adjacent-hop scoring or wildcard scoring.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `concept_id` | query | integer | yes | seed concept ID, `> 0` |
| `mode` | query | enum | yes | `"adjacent"` or `"wildcard"` |
| `k_hops` | query | integer | no | default `1`, range `1..3` |

Success responses:

- `200 OK` with `GraphLuckyResponse`

`GraphLuckyResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `seed_concept_id` | integer | input concept |
| `mode` | enum | `adjacent` or `wildcard` |
| `pick` | object | mode-specific pick payload |

`pick` shape by mode:

- `adjacent`: includes `hop_distance` and `score_components.strongest_link_weight`
- `wildcard`: includes `hop_distance: null` and `score_components.{degree,total_incident_weight}`

Error responses:

- `404 Not Found` when the seed concept is missing or no eligible candidate exists
- `422 Unprocessable Entity` for validation failures

Example:

```bash
curl -sS 'http://localhost:8000/graph/lucky?workspace_id=7&concept_id=42&mode=adjacent&k_hops=2'
```

```json
{
  "workspace_id": 7,
  "seed_concept_id": 42,
  "mode": "adjacent",
  "pick": {
    "concept_id": 99,
    "canonical_name": "Kernel",
    "description": "Vectors mapped to zero.",
    "hop_distance": 1,
    "score_components": {
      "hop_distance": 1,
      "strongest_link_weight": 8.0
    }
  }
}
```

### POST /workspaces/{ws_id}/quizzes/level-up

Tag/group: `quizzes`

Purpose: create a level-up quiz for one concept.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `user_id` | JSON body | integer | yes | `> 0` |
| `concept_id` | JSON body | integer | yes | `> 0` |
| `session_id` | JSON body | integer | no | `> 0` when present |
| `question_count` | JSON body | integer | no | default `5`, range `5..10` |
| `items` | JSON body | array<object> | no | optional pre-specified quiz items |

Success responses:

- `201 Created` with `QuizCreateResponse`

`QuizCreateResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `quiz_id` | integer | created quiz ID |
| `workspace_id` | integer | workspace scope |
| `user_id` | integer | quiz owner |
| `concept_id` | integer | target concept |
| `status` | string | quiz lifecycle state |
| `items` | array | item summaries (`item_id`, `position`, `item_type`, `prompt`, `choices`) |

Error responses:

- `404 Not Found` when workspace/user/concept scope is invalid
- `422 Unprocessable Entity` for validation or domain quiz-shape errors

Example:

```bash
curl -sS -X POST http://localhost:8000/quizzes/level-up \
  -H 'content-type: application/json' \
  -d '{
    "workspace_id": 7,
    "user_id": 5,
    "concept_id": 42,
    "question_count": 5
  }'
```

```json
{
  "quiz_id": 101,
  "workspace_id": 7,
  "user_id": 5,
  "concept_id": 42,
  "status": "ready",
  "items": [
    {
      "item_id": 1001,
      "position": 1,
      "item_type": "mcq",
      "prompt": "Which statement best describes a linear map?",
      "choices": [
        {"id": "a", "text": "Preserves vector addition and scalar multiplication."},
        {"id": "b", "text": "Maps every vector to zero."}
      ]
    }
  ]
}
```

### POST /workspaces/{ws_id}/quizzes/{quiz_id}/submit

Tag/group: `quizzes`

Purpose: submit answers for a level-up quiz and return grading plus mastery state.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `quiz_id` | path | integer | yes | integer route parameter |
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `user_id` | JSON body | integer | yes | `> 0` |
| `answers` | JSON body | array<object> | yes | minimum length `1` |

Success responses:

- `200 OK` with `LevelUpQuizSubmitResponse`

`LevelUpQuizSubmitResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `quiz_id` | integer | quiz ID |
| `attempt_id` | integer | graded attempt ID |
| `score` | number | `0.0..1.0` |
| `passed` | boolean | pass/fail decision |
| `critical_misconception` | boolean | true if critical misconception detected |
| `overall_feedback` | string | overall grading feedback |
| `items` | array | per-item feedback (`result`, `feedback`, `score`, etc.) |
| `replayed` | boolean | true when returning previously graded attempt |
| `retry_hint` | string/null | hint for retry path |
| `mastery_status` | enum | `locked`, `learning`, or `learned` |
| `mastery_score` | number | `0.0..1.0` |

Error responses:

- `404 Not Found` when quiz/workspace/user scope is invalid
- `422 Unprocessable Entity` for validation or grading payload errors
- `503 Service Unavailable` when required grading dependencies are unavailable

Example:

```bash
curl -sS -X POST http://localhost:8000/quizzes/101/submit \
  -H 'content-type: application/json' \
  -d '{
    "workspace_id": 7,
    "user_id": 5,
    "answers": [
      {"item_id": 1001, "answer": "a"}
    ]
  }'
```

```json
{
  "quiz_id": 101,
  "attempt_id": 5001,
  "score": 0.8,
  "passed": true,
  "critical_misconception": false,
  "overall_feedback": "Good work. Focus on edge cases next.",
  "items": [
    {
      "item_id": 1001,
      "item_type": "mcq",
      "result": "correct",
      "is_correct": true,
      "critical_misconception": false,
      "feedback": "Correct.",
      "score": 1.0
    }
  ],
  "replayed": false,
  "retry_hint": null,
  "mastery_status": "learned",
  "mastery_score": 0.8
}
```

### POST /workspaces/{ws_id}/practice/flashcards

Tag/group: `practice`

Purpose: generate bounded practice flashcards for a concept (non-leveling).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `concept_id` | JSON body | integer | yes | `> 0` |
| `card_count` | JSON body | integer | no | default `6`, range `3..12` |

Success responses:

- `200 OK` with `PracticeFlashcardsResponse`

`PracticeFlashcardsResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `concept_id` | integer | target concept |
| `concept_name` | string | canonical concept name |
| `flashcards` | array | each card has `front`, `back`, `hint` |

Error responses:

- `404 Not Found` when concept/workspace scope is invalid
- `422 Unprocessable Entity` for validation or generation-shape errors
- `503 Service Unavailable` when generation dependencies are unavailable

Example:

```bash
curl -sS -X POST http://localhost:8000/practice/flashcards \
  -H 'content-type: application/json' \
  -d '{
    "workspace_id": 7,
    "concept_id": 42,
    "card_count": 4
  }'
```

```json
{
  "workspace_id": 7,
  "concept_id": 42,
  "concept_name": "Linear Map",
  "flashcards": [
    {
      "front": "What property must f(u + v) satisfy?",
      "back": "f(u + v) = f(u) + f(v)",
      "hint": "Think additivity"
    }
  ]
}
```

### POST /workspaces/{ws_id}/practice/flashcards/stateful

Tag/group: `practice`

Purpose: generate stateful flashcards persisted to the bank with novelty dedup.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `concept_id` | JSON body | integer | yes | `> 0` |
| `card_count` | JSON body | integer | no | default `6`, range `3..12` |

Success responses:

- `200 OK` with `StatefulFlashcardsResponse`

`StatefulFlashcardsResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `concept_id` | integer | target concept |
| `concept_name` | string | canonical concept name |
| `run_id` | string | UUID of the generation run |
| `flashcards` | array | `StatefulFlashcard` objects with `flashcard_id`, `front`, `back`, `hint` |
| `has_more` | boolean | whether more cards can be generated |
| `exhausted_reason` | string/null | reason when no more cards available |

Error responses:

- `401 Unauthorized` when not authenticated
- `404 Not Found` when concept/workspace scope is invalid
- `422 Unprocessable Entity` for validation or generation errors
- `503 Service Unavailable` when LLM is unavailable

### POST /workspaces/{ws_id}/practice/flashcards/rate

Tag/group: `practice`

Purpose: submit a self-rating for a stateful flashcard.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `flashcard_id` | JSON body | string | yes | UUID of the flashcard |
| `self_rating` | JSON body | enum | yes | `"again"`, `"hard"`, `"good"`, or `"easy"` |

Success responses:

- `200 OK` with `FlashcardRateResponse`

`FlashcardRateResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `flashcard_id` | string | echoed flashcard UUID |
| `self_rating` | enum | recorded rating |
| `passed` | boolean | true for `good`/`easy`, false for `again`/`hard` |

Error responses:

- `401 Unauthorized` when not authenticated
- `404 Not Found` when flashcard not found
- `422 Unprocessable Entity` for validation failures

### GET /workspaces/{ws_id}/practice/flashcards/due

Tag/group: `practice`

Purpose: retrieve flashcards due for spaced-repetition review.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `ws_id` | path | string | yes | workspace public ID |
| `limit` | query | integer | no | default 10, max 50 |

Success responses:

- `200 OK` with `{ workspace_id, due_flashcards: [...] }`

Each flashcard in `due_flashcards`:

| Field | Type | Notes |
|---|---|---|
| `flashcard_id` | integer | bank row ID |
| `front` | string | question side |
| `back` | string | answer side |
| `hint` | string/null | optional hint |
| `concept_name` | string | canonical concept name |
| `due_at` | string | ISO-8601 timestamp |
| `interval_days` | float | current interval |
| `last_rating` | string/null | most recent self-rating |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### POST /workspaces/{ws_id}/practice/quizzes

Tag/group: `practice`

Purpose: create a practice quiz for a concept (does not update mastery to learned).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `user_id` | JSON body | integer | yes | `> 0` |
| `concept_id` | JSON body | integer | yes | `> 0` |
| `session_id` | JSON body | integer | no | `> 0` when present |
| `question_count` | JSON body | integer | no | default `4`, range `3..6` |

Success responses:

- `201 Created` with `QuizCreateResponse`

Error responses:

- `404 Not Found` when concept/workspace scope is invalid
- `422 Unprocessable Entity` for validation or generation-shape errors
- `503 Service Unavailable` when generation dependencies are unavailable

Example:

```bash
curl -sS -X POST http://localhost:8000/practice/quizzes \
  -H 'content-type: application/json' \
  -d '{
    "workspace_id": 7,
    "user_id": 5,
    "concept_id": 42,
    "question_count": 4
  }'
```

```json
{
  "quiz_id": 201,
  "workspace_id": 7,
  "user_id": 5,
  "concept_id": 42,
  "status": "ready",
  "items": [
    {
      "item_id": 2001,
      "position": 1,
      "item_type": "short_answer",
      "prompt": "Explain why kernels matter.",
      "choices": null
    }
  ]
}
```

### POST /workspaces/{ws_id}/practice/quizzes/{quiz_id}/submit

Tag/group: `practice`

Purpose: submit practice quiz answers and receive graded feedback (no mastery promotion).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `quiz_id` | path | integer | yes | integer route parameter |
| `workspace_id` | JSON body | integer | yes | `> 0` |
| `user_id` | JSON body | integer | yes | `> 0` |
| `answers` | JSON body | array<object> | yes | minimum length `1` |

Success responses:

- `200 OK` with `PracticeQuizSubmitResponse`

`PracticeQuizSubmitResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `quiz_id` | integer | quiz ID |
| `attempt_id` | integer | graded attempt ID |
| `score` | number | `0.0..1.0` |
| `passed` | boolean | thresholded practice pass flag |
| `critical_misconception` | boolean | misconception signal |
| `overall_feedback` | string | overall feedback |
| `items` | array | per-item feedback |
| `replayed` | boolean | true on idempotent replay |
| `retry_hint` | string/null | retry guidance |

Error responses:

- `404 Not Found` when quiz/workspace/user scope is invalid
- `422 Unprocessable Entity` for validation, generation, or grading errors
- `503 Service Unavailable` when grading dependencies are unavailable

Example:

```bash
curl -sS -X POST http://localhost:8000/practice/quizzes/201/submit \
  -H 'content-type: application/json' \
  -d '{
    "workspace_id": 7,
    "user_id": 5,
    "answers": [
      {"item_id": 2001, "answer": "Because they characterize injectivity."}
    ]
  }'
```

```json
{
  "quiz_id": 201,
  "attempt_id": 6001,
  "score": 0.75,
  "passed": true,
  "critical_misconception": false,
  "overall_feedback": "Good. Add a formal definition next time.",
  "items": [
    {
      "item_id": 2001,
      "item_type": "short_answer",
      "result": "partial",
      "is_correct": false,
      "critical_misconception": false,
      "feedback": "Partially correct; include null-space wording.",
      "score": 0.75
    }
  ],
  "replayed": false,
  "retry_hint": null
}
```

### GET /workspaces/{ws_id}/knowledge-base/documents

Tag/group: `knowledge-base`

Purpose: list documents in the workspace knowledge base with chunk counts.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `200 OK` with `KBDocumentListResponse`

`KBDocumentListResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `documents` | array | list of `KBDocumentSummary` |

`KBDocumentSummary` fields:

| Field | Type | Notes |
|---|---|---|
| `document_id` | integer | document row ID |
| `public_id` | string | UUID public identifier |
| `title` | string/null | document title |
| `source_uri` | string/null | original source URI |
| `chunk_count` | integer | number of chunks |
| `ingestion_status` | string | `pending` \| `ingested` |
| `graph_status` | string | `disabled` \| `pending` \| `extracted` |
| `graph_concept_count` | integer | distinct concept links extracted for this document |
| `created_at` | datetime | ingestion timestamp |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### DELETE /workspaces/{ws_id}/knowledge-base/documents/{document_id}

Tag/group: `knowledge-base`

Purpose: delete a document and its chunks from the knowledge base (cascading delete). Optionally prune orphaned canonical graph nodes.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `document_id` | path | integer | yes | document ID |
| `workspace_id` | query | integer | yes | `> 0` |
| `prune_orphan_graph` | query | boolean | no | default `false`; when `true`, removes canonical concepts/edges with no remaining provenance after deletion |

Success responses:

- `204 No Content`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `404 Not Found` when document not found in workspace

### POST /workspaces/{ws_id}/knowledge-base/documents/upload

Tag/group: `knowledge-base`

Purpose: upload a document (txt, md, pdf) to the workspace knowledge base.

Request contract (multipart/form-data):

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `file` | body (multipart) | file | yes | txt, md, or pdf; max 20 MB |
| `workspace_id` | body (form) | integer | yes | `> 0` |
| `title` | body (form) | string | no | optional document title |

Success responses:

- `201 Created` with payload `{"document_id", "workspace_id", "title", "chunk_count", "created"}`

Error responses:

- `400 Bad Request` when uploaded file is empty
- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `413 Request Entity Too Large` when file exceeds 20 MB
- `422 Unprocessable Entity` when document content is invalid
- `503 Service Unavailable` when graph dependencies unavailable

### POST /workspaces/{ws_id}/knowledge-base/documents/{document_id}/reprocess

Tag/group: `knowledge-base`

Purpose: re-chunk and re-embed a document (returns 202 — async stub).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `document_id` | path | integer | yes | document ID |
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `202 Accepted` with status payload `{"document_id", "workspace_id", "status": "queued", "message"}`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `404 Not Found` when document not found in workspace

### GET /workspaces/{ws_id}/readiness/snapshot

Tag/group: `readiness`

Purpose: return per-topic readiness scores for the current user in a workspace.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `200 OK` with `ReadinessSnapshotResponse`

`ReadinessSnapshotResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `workspace_id` | integer | workspace scope |
| `user_id` | integer | user scope |
| `topics` | array | list of `ReadinessTopicState` |

`ReadinessTopicState` fields:

| Field | Type | Notes |
|---|---|---|
| `concept_id` | integer | canonical concept ID |
| `concept_name` | string | canonical concept name |
| `readiness_score` | number | `0.0..1.0`, exponential-decay adjusted |
| `recommend_quiz` | boolean | true when readiness < 0.5 and mastery >= 0.3 |
| `last_assessed_at` | datetime/null | last mastery assessment timestamp |

Error responses:

- `401 Unauthorized` when not authenticated

### POST /workspaces/{ws_id}/research/sources

Tag/group: `research`

Purpose: register a new research source URL for the workspace.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `url` | JSON body | string | yes | non-empty URL |
| `label` | JSON body | string | no | optional display label |

Success responses:

- `201 Created` with `ResearchSourceSummary`

`ResearchSourceSummary` fields:

| Field | Type | Notes |
|---|---|---|
| `source_id` | integer | source row ID |
| `url` | string | source URL |
| `label` | string/null | display label |
| `active` | boolean | whether source is active |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `422 Unprocessable Entity` for validation failures

### GET /workspaces/{ws_id}/research/sources

Tag/group: `research`

Purpose: list registered research sources for the workspace.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `200 OK` with array of `ResearchSourceSummary`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### DELETE /workspaces/{ws_id}/research/sources/{source_id}

Tag/group: `research`

Purpose: deactivate (soft-delete) a research source.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `source_id` | path | integer | yes | source ID |
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `204 No Content`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### POST /workspaces/{ws_id}/research/runs

Tag/group: `research`

Purpose: trigger a new research run (actual crawling is async).

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |

Success responses:

- `201 Created` with `ResearchRunSummary`

`ResearchRunSummary` fields:

| Field | Type | Notes |
|---|---|---|
| `run_id` | integer | run row ID |
| `status` | string | run lifecycle state |
| `candidates_found` | integer | number of candidates discovered |
| `started_at` | datetime | run start timestamp |
| `finished_at` | datetime/null | run completion timestamp |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### GET /workspaces/{ws_id}/research/runs

Tag/group: `research`

Purpose: list recent research runs for the workspace.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `limit` | query | integer | no | default `10`, range `1..50` |

Success responses:

- `200 OK` with array of `ResearchRunSummary`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### GET /workspaces/{ws_id}/research/candidates

Tag/group: `research`

Purpose: list research candidates, optionally filtered by run or status.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `workspace_id` | query | integer | yes | `> 0` |
| `run_id` | query | integer | no | filter by run ID |
| `status` | query | string | no | filter by candidate status |

Success responses:

- `200 OK` with array of `ResearchCandidateSummary`

`ResearchCandidateSummary` fields:

| Field | Type | Notes |
|---|---|---|
| `candidate_id` | integer | candidate row ID |
| `source_url` | string | origin source URL |
| `title` | string/null | extracted title |
| `snippet` | string/null | text snippet |
| `status` | string | `pending`, `approved`, `rejected`, `ingested` |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member

### PATCH /workspaces/{ws_id}/research/candidates/{candidate_id}

Tag/group: `research`

Purpose: approve or reject a research candidate.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `candidate_id` | path | integer | yes | candidate ID |
| `workspace_id` | query | integer | yes | `> 0` |
| `status` | JSON body | string | yes | `"approved"` or `"rejected"` |

Success responses:

- `200 OK` with `ResearchCandidateSummary`

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
- `404 Not Found` when candidate not found

---

## Onboarding

### GET /workspaces/{ws_id}/onboarding/status

Tag/group: `onboarding`

Purpose: check workspace readiness and get suggested starting topics.

Request contract:

| Field | Location | Type | Required | Constraints / Notes |
|---|---|---|---|---|
| `ws_id` | path | string | yes | workspace public ID |
| `topic_limit` | query | integer | no | default 5, range 1–20 |

Success responses:

- `200 OK` with `OnboardingStatusResponse`

`OnboardingStatusResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `has_documents` | boolean | true if workspace has uploaded docs |
| `has_active_concepts` | boolean | true if workspace has active graph concepts |
| `suggested_topics` | array | top-N concepts by degree |

Error responses:

- `401 Unauthorized` when not authenticated
- `403 Forbidden` when not a workspace member
