# docs/API.md

## Backend HTTP API Reference

This document is the canonical reference for all FastAPI HTTP endpoints exposed by `apps/api`.

### Conventions

- Base URL: `http://localhost:8000`
- Authentication: none currently required
- Transport: JSON unless otherwise noted
- Validation errors are returned as HTTP `422` (`HTTPValidationError` schema)

### Endpoint Index

- `GET /healthz`
- `POST /chat/respond`
- `POST /documents/upload`
- `GET /graph/concepts/{concept_id}`
- `GET /graph/concepts/{concept_id}/subgraph`
- `GET /graph/lucky`
- `POST /quizzes/level-up`
- `POST /quizzes/{quiz_id}/submit`
- `POST /practice/flashcards`
- `POST /practice/quizzes`
- `POST /practice/quizzes/{quiz_id}/submit`

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

### POST /chat/respond

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

### GET /graph/concepts/{concept_id}

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

### GET /graph/concepts/{concept_id}/subgraph

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

### GET /graph/lucky

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

### POST /quizzes/level-up

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

### POST /quizzes/{quiz_id}/submit

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

### POST /practice/flashcards

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

### POST /practice/quizzes

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

### POST /practice/quizzes/{quiz_id}/submit

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
