# Phase 2 Handoff - Local Trail Generation Endpoint

## Repository

`lcwlouis/Colearni`, branch `rebuild`.

Before starting:

```bash
git checkout rebuild
git status --short
```

Do not overwrite unrelated local changes.

## Current State

Phase 1 is in place:

- SQLAlchemy async setup in `backend/app/db.py`.
- ORM models in `backend/app/models/`.
- Pydantic schemas in `backend/app/schemas/`.
- Alembic initial migration in `backend/alembic/versions/0001_initial.py`.
- Model tests use in-memory SQLite and pass without a live DB.

Important Phase 1 schema detail:

- Use `TrailGenerateRequest` for the public request body.
- Use `TrailInsert` for service/database insertion after the server has a title.
- Do not reintroduce `TrailCreate`.

## Phase 2 Goal

Add local-ready Trail generation:

```http
POST /api/workspaces/{workspace_id}/trails/generate
```

Request body must match `docs/API.md` exactly:

```json
{
  "topic": "Linear Algebra",
  "goal": "Understand enough for machine learning",
  "target_depth": "apply"
}
```

`workspace_id` comes from the URL path. `title` is generated server-side.

Response:

```json
{
  "trail": "Trail",
  "graph": {
    "nodes": ["ConceptNode"],
    "edges": ["ConceptEdge"]
  }
}
```

## Hard Scope

Do:

- Add one API router for Trail generation.
- Add service-layer code for graph generation, validation, repair/fallback handling, and storage.
- Add prompt file(s) under `backend/app/agents/prompts/`.
- Add tests for route behavior, graph validation, and service storage.
- Keep tests independent of live LLM providers by injecting a fake generator.

Do not add:

- Frontend.
- Tutor chat.
- Mastery or quiz tables.
- Conversation tables.
- PDF ingestion.
- Auth, billing, marketplace, or SaaS concerns.
- Public Trail Pack export/import.

## Suggested File Structure

```text
backend/app/
  api/
    trails.py
  services/
    __init__.py
    graph_validation.py
    trail_generation.py
  agents/
    __init__.py
    prompts/
      trail_generation.v1.md
tests/
  test_graph_validation.py
  test_trail_generation_service.py
  test_trails_api.py
```

## Implementation Requirements

Route layer:

- Register the router from `backend/app/main.py`.
- Prefix routes with `/api`.
- Route signature should use `workspace_id: uuid.UUID` from the path and `TrailGenerateRequest` from the body.
- Route must stay thin: validate request, call service, return response.

Service layer:

- Verify the workspace exists before inserting.
- Generate or derive a Trail title server-side.
- Insert the Trail and all graph rows in one transaction.
- Commit only after the graph validates.
- Roll back on validation or storage failure.

Graph generation:

- Generated graph should contain 10-30 nodes for normal generation.
- If malformed output is returned, attempt one repair call.
- If repair still fails, fail clearly or fall back to a smaller valid graph.
- No live LLM calls in tests. Use an injectable generator/protocol.

Graph validation:

- Every node has `slug`, `title`, `node_type`, `concept_level`, `difficulty`, `bloom_level`, and `mastery_check_labels`.
- `concept_level` must be `umbrella`, `topic`, `subtopic`, or `granular`.
- Node slugs must be unique within the generated Trail.
- Edges must point to existing node slugs.
- `prerequisite` edges must be acyclic.
- Graph must have at least one entry node at `umbrella` or `topic`.
- Normal generation must cap at 30 nodes.

Prompt:

- Store prompt text in `backend/app/agents/prompts/trail_generation.v1.md`.
- Do not inline long prompt strings in services or routes.
- Prompt output should include a server-side `title`, plus `nodes` and `edges`.

## Suggested Response Schemas

Add only what Phase 2 needs. A compact option:

```python
class TrailGraphRead(BaseModel):
    nodes: list[ConceptNodeRead]
    edges: list[ConceptEdgeRead]


class TrailGenerateResponse(BaseModel):
    trail: TrailRead
    graph: TrailGraphRead
```

If `docs/API.md` requires `node_count` and `edge_count` on `Trail`, either add them to a dedicated API response schema or document why Phase 2 returns them separately. Do not add database columns for counts.

## Tests Required

Use TDD. Add focused tests before implementation.

Required route/service tests:

- Valid request creates one Trail, nodes, and edges.
- Request body rejects `workspace_id` and `title`.
- Invalid `target_depth` returns a validation error.
- Missing workspace returns 404.
- Generator validation failure returns a clear error and does not insert partial rows.
- Malformed first output triggers exactly one repair attempt.

Required graph validation tests:

- Duplicate slugs are rejected.
- Unknown `concept_level` is rejected.
- Edges pointing to missing slugs are rejected.
- Prerequisite cycles are rejected.
- Too-large graph is rejected or fallback path is tested.
- A valid graph with `contains`, `prerequisite`, `application`, and `related` edges passes.

Manual topic checks after tests:

```text
Linear Algebra
Computer Networks
FastAPI
Operating Systems
Photography Exposure Triangle
```

## Verification Commands

Run and report:

```bash
pytest -v
ruff check .
git diff --check
alembic upgrade head
```

If live LLM credentials are not configured, document that manual live generation was skipped and show that fake-generator tests cover route/service behavior.

## Review Notes For GPT 5.5

After Claude finishes Phase 2, ask GPT 5.5 to review:

- API path matches `docs/API.md`.
- `TrailGenerateRequest` is the only request-body schema for generate.
- No client-provided `workspace_id` or `title` is accepted in the body.
- Route has no business logic.
- Graph validation happens before commit.
- Repair is attempted once, not in an unbounded loop.
- No partial Trail graph is persisted on failure.
- No frontend, tutor, mastery, quiz, auth, PDF, or export/import scope was added.
