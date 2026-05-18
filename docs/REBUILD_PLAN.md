# CoLearni Rebuild Plan

## Summary

CoLearni is being rebuilt as a local-ready, graph-first learning system.

Recommended strategy:

```text
Build local-ready first.
Keep SaaS compatibility in the architecture.
Do not build SaaS-first.
```

The first rebuild must prove the learning experience before it adds hosted product concerns. The hard product risks are whether the tutor feels useful, whether graph-guided learning helps, whether mastery gating feels motivating, whether Trail sharing can be safe, and whether retrieval stays scoped and cheap.

SaaS concerns such as auth, billing, rate limits, pack moderation, public marketplace operations, abuse prevention, and multi-tenancy come after the local-ready loop is useful.

Core product shape:

```text
CoLearni = personal learning workspace
         + concept graph / Trail
         + Socratic tutor
         + mastery state
         + source-aware retrieval
         + safe community Trail sharing
```

The MVP is not a generic RAG chatbot. The graph, mastery model, and source provenance model are product primitives.

## Build Order

1. Foundation cleanup
2. Workspace + Trail database models
3. Trail generation endpoint
4. Graph viewer
5. Tutor chat for one concept
6. Mastery + level-up quiz
7. Source provenance + export sanitizer
8. Trail Pack export
9. Research trace
10. Hydration
11. Trail Pack import
12. Demo polish
13. SaaS prep

Do not start with PDF ingestion, SaaS billing/auth, or a public marketplace.

## Phase 0: Foundation Cleanup

Goal: get the repo into a clean rebuild state that can run locally.

Implementation scope:

- Keep FastAPI, PostgreSQL + pgvector, SQLAlchemy + Alembic, Pydantic, Next.js, openai SDK, pytest, and local Docker Compose.
- Preserve the layer rule: routes validate input, call services, and return responses.
- Make `.env.example` accurate.
- Provide one command for local infra, backend, and frontend.
- Add or confirm `/health`.
- Confirm the frontend can call the backend.

Requirements:

- Backend has a health endpoint returning an explicit ok status.
- DB migrations apply cleanly.
- Local infra starts without hidden manual steps.
- Frontend API base URL is documented.
- Phoenix tracing remains optional, not day-one mandatory.

Tests:

- `pytest` passes for available backend tests.
- Health endpoint returns ok.
- Alembic migration applies cleanly.
- Frontend typecheck passes when `apps/web/` exists.
- Basic page renders and can call backend health.

Acceptance criteria:

- A new developer can start local infra, backend, and frontend from documented commands.
- Environment variables match the actual app.

## Phase 1: Workspace + Trail Model

Goal: create the core data model before LLM features.

Implementation scope:

- Add tables for workspaces, trails, concept nodes, concept edges, source records, and concept-source links.
- A Trail can exist without documents.
- A concept can exist without prose content.
- Every source has explicit provenance and access metadata.

Recommended tables:

```sql
workspaces
- id
- name
- created_at

trails
- id
- workspace_id
- title
- topic
- goal
- target_depth
- created_at

concept_nodes
- id
- trail_id
- slug
- title
- node_type
- concept_level
- difficulty
- bloom_level
- metadata_json

concept_edges
- id
- trail_id
- source_node_id
- target_node_id
- relation_type

source_records
- id
- workspace_id
- origin
- access
- title
- url
- license
- include_on_public_export
- metadata_json

concept_source_links
- id
- concept_id
- source_id
- relation
```

Requirements:

- User-uploaded sources default to non-public export.
- Research-agent sources can be exported as links and metadata only.
- Relation types are explicit enough for prerequisite, application, visual, and reference links.
- Slugs are unique within a Trail.
- Concept levels are explicit: `umbrella`, `topic`, `subtopic`, and `granular`.

Tests:

- Create workspace.
- Create Trail.
- Add nodes and edges.
- Add research source.
- Add user-upload source.
- Public export excludes user-upload source.
- Public export includes research source metadata only.

Acceptance criteria:

- The database can store a content-light Trail with safe source metadata.

## Phase 2: Local Trail Creation

Goal: a user enters a topic and gets a usable concept graph.

Implementation scope:

- Add `POST /api/trails/generate`.
- Generate 10-30 concept nodes with prerequisites, hierarchy level, difficulty, Bloom target, and mastery check labels.
- Validate and store graph JSON.
- Repair malformed LLM output once, then fail clearly or fall back to a smaller graph.

Input example:

```json
{
  "topic": "Linear Algebra",
  "goal": "Understand enough for machine learning",
  "target_depth": "apply"
}
```

Requirements:

- Generated graphs have entry nodes.
- Every generated node has a `concept_level`: `umbrella`, `topic`, `subtopic`, or `granular`.
- Hierarchy is represented by node levels plus optional `contains` edges, not by parent/child edges alone.
- Prerequisite edges are acyclic unless explicitly allowed.
- Obvious duplicate concepts are rejected or merged.
- Every node has title, slug, node type, Bloom target, and mastery check labels.
- Generation obeys graph resolver budgets from `docs/GRAPH.md`.

Tests:

- Slug generation.
- Cycle detection.
- Duplicate title detection.
- Node and edge schema validation.
- Concept level validation.
- Invalid JSON rejection.
- Malformed JSON repair once.
- Too-large graph fallback.

Acceptance criteria:

- Manual topics such as Linear Algebra, Computer Networks, FastAPI, Operating Systems, and Photography Exposure Triangle produce usable graphs.

## Phase 3: Graph Viewer

Goal: learners can see, search, and click the Trail.

Implementation scope:

- Add `/trails`, `/trails/[id]`, and `/trails/[id]/concepts/[conceptId]`.
- Render nodes, edges, status colors, selected-node side panel, and a start-learning action.
- Use React Flow for speed unless the existing Sigma.js graph is already working and cheaper to preserve.

Requirements:

- Graph loads from backend.
- User can search nodes.
- User can filter or visually distinguish umbrella, topic, subtopic, and granular nodes.
- User can click a node.
- Side panel shows title, concept level, prerequisites, contained/related nodes, mastery checks, and sources when present.
- Graph remains usable at 100 nodes.

Tests:

- Empty state renders.
- Sample Trail renders.
- Clicking a node opens the side panel.
- Search filters or focuses the node.
- Status colors match mastery state.
- Concept level styling/filtering works.
- Manual checks at 10, 50, and 100 nodes.

Acceptance criteria:

- A learner can understand what to learn next from the graph.

## Phase 4: Tutor Chat For One Concept

Goal: make the first compelling learning loop.

Implementation scope:

- Add `POST /api/tutor/chat`.
- Build tutor context from current concept, nearby graph context, mastery state, learning goal, safe source links, and conversation summary.
- Support tutor modes: `socratic`, `direct`, `repair`, `quiz_prompt`, and `explore`.
- Build the chat panel UI using `@assistant-ui/react` with a custom `LocalRuntime` adapter (see `docs/FRONTEND.md` — Tutor Chat UI section). The adapter calls `POST /api/tutor/chat`; the library handles all streaming, rendering, and state.
- Return a **streaming response** from `POST /api/tutor/chat` (SSE or chunked transfer) so tokens render incrementally. A non-streaming response is acceptable for the first iteration but should be upgraded before demo polish.
- Customise the installed `Thread` component to show the tutor mode badge, concept context header, source citation chips, and mastery level-up prompt.

Requirements:

- Default mode is Socratic.
- The tutor asks one good question at a time.
- The tutor can explain when the learner is stuck.
- The tutor does not pretend private sources exist.
- The tutor can reference public source links if present.
- The tutor can say it lacks source material.
- User-visible sourced claims include citations or refuse in strict grounded mode.
- The chat UI is built with `@assistant-ui/react`; no bespoke chat shell is written from scratch.
- The custom runtime adapter is the only glue between the UI and the FastAPI backend.

Tests:

- Prompt builder includes current concept.
- Prompt builder includes mastery state.
- Prompt builder excludes private sources from public context.
- Mode classifier returns valid mode.
- Runtime adapter sends correct `concept_id` and `workspace_id` to the backend.
- Manual tests cover direct answers, incorrect answers, examples, ML links, and unrelated questions.

Acceptance criteria:

- The tutor feels like a coach, not a search engine.
- Streaming tokens appear incrementally in the chat UI.

## Phase 5: Mastery + Level-Up Quiz

Goal: make mastery a motivating product loop.

Implementation scope:

- Add `mastery_records` and `quiz_attempts`.
- Add `POST /api/concepts/{id}/level-up`.
- Add `POST /api/concepts/{id}/grade`.
- Generate a short level-up card from mastery check labels.

Requirements:

- Passing updates concept status to `mastered`.
- Failing sets status to `needs_review`.
- Quiz attempts are stored.
- Feedback is specific and useful.
- The learner can retry.
- The tutor cannot mark mastery without a quiz or explicit mastery policy.

Tests:

- Passing answer updates mastery.
- Failing answer does not mark mastered.
- Quiz attempt is stored.
- Graph status changes after mastery update.
- Manual tests include good, vague, wrong, and gaming attempts.

Acceptance criteria:

- Mastery gating feels motivating, not punitive.

## Phase 6: Source Provenance + Safe Export

Goal: build sharing safely from the start.

Implementation scope:

- Add Trail Pack export.
- Implement export sanitizer based on source provenance and access.
- Generate an export report with included and excluded data.

Trail Pack structure:

```text
trail-pack/
  manifest.yaml
  graph.yaml
  concepts/
  sources.yaml
  research_trace.yaml
```

Requirements:

- Public export includes graph structure, learning objectives, abstract mastery check labels, public research source metadata, and research trace.
- Public export excludes uploaded files, chunks, embeddings, private notes, chat history, user mastery, and private/source-derived generated content.
- User-uploaded sources are removed automatically.
- Research-agent sources remain as links and metadata only.

Tests:

- User-upload source never appears in public export.
- Private notes never appear.
- Chunks never appear.
- Embeddings never appear.
- Chat history never appears.
- Public source URL appears.
- Research trace appears.

Acceptance criteria:

- Export cannot leak private or source-derived content by default.

## Phase 7: Research Trace + Hydration

Goal: make Trail Packs useful without sharing copyrighted or private content.

Implementation scope:

- Add `POST /api/trails/{id}/research`.
- Store search queries, selected public links, source types, license/access status, selection reasons, and excluded source notes.
- Add `POST /api/trails/{id}/hydrate`.

Requirements:

- Research trace stores links and metadata, not copied content.
- Hydration content stays private to the workspace.
- Unknown license means no content redistribution.
- Learners can skip hydration and still learn.

Tests:

- Research trace is created.
- Public URL is stored.
- Hydration creates private evidence records.
- Hydrated evidence is not included in public export.
- Unknown-license source is marked no-redistribution.

Acceptance criteria:

- Imported Trail Packs can become locally useful without making their hydrated content public.

## Phase 8: Trail Pack Import

Goal: learners can start from community/shared Trails.

Implementation scope:

- Add `POST /api/trail-packs/import`.
- For V1, import by forking into the current workspace.
- Validate manifest, graph, concepts, sources, and research trace.

Requirements:

- Invalid packs are rejected.
- Duplicate slugs are handled.
- Missing sources are shown clearly.
- Imported packs can be edited locally.
- Imported packs can be hydrated later.

Tests:

- Valid pack imports.
- Malformed pack is rejected.
- Pack with raw chunks is rejected.
- Pack with embeddings is rejected.
- Missing sources are reported.
- Graph is created correctly.

Acceptance criteria:

- A learner can import a safe content-light Trail Pack and start learning.

## Phase 9: Demo Polish/User Testing

Goal: make the rebuild good enough to show people and let them try it themselves.

Demo path:

```text
1. Create Trail: "Learn Linear Algebra for ML"
2. See generated graph
3. Click "Vectors"
4. Learn through Socratic chat
5. Take level-up quiz
6. Node turns mastered
7. Click "Eigenvectors"
8. Research public sources
9. Export safe Trail Pack
10. Import that Trail Pack into a new workspace
```

Local product metrics:

- Time to first learning turn.
- Concepts started.
- Concepts mastered.
- Quiz pass rate.
- Tutor turns before quiz.
- Graph nodes clicked.
- Hydration used or skipped.
- Exports and imports.

Requirements:

- All demo path steps work end-to-end without errors.
- Trail generation is resilient to page refresh: if the user refreshes or navigates away mid-stream, the generation continues in a backend job and the result is retrievable on return. Implement as a simple async background task with a polling endpoint (`GET /api/jobs/{job_id}`); no heavy queue required.
- Dark mode: system-respecting, implemented with `next-themes` and Tailwind `dark:` variants. All pages, graph canvas, and chat panel must be themed. See `docs/FRONTEND.md` for the full scope.
- The backend logs actionable errors — not raw stack traces — for generation failures, LLM errors, and import/export problems.
- All user-facing error messages are readable and suggest a next action.

Acceptance criteria:

- A new user can create a Trail in under one minute.
- They can click a concept and start learning immediately.
- The graph updates after mastery.
- Export/import works without private leakage.
- Refreshing the browser during Trail generation does not permanently lose the Trail.

## Phase 10: Deployment

Goal: make the product deployable to a VPS or cloud instance so real users can try it.

Implementation scope:

- Production Docker Compose profile (separate from dev): Postgres with volume, backend, frontend behind a reverse proxy (Caddy or nginx).
- Environment variable documentation: every required and optional env var documented in `.env.example` with a comment.
- CORS locked to the deployed domain, not hardcoded to `localhost:3000`.
- Health check endpoint used by Docker to gate service readiness.
- LLM API key supplied via env, never baked into the image.
- Basic rate limiting on generation endpoints to prevent runaway LLM spend (simple in-process token bucket is fine for single-instance).
- One-command deploy: `docker compose -f docker-compose.prod.yml up -d` brings up the full stack.
- HTTPS via Caddy automatic TLS or equivalent.

Requirements:

- A fresh clone with a filled `.env` can be deployed to a VPS with a single command.
- No secrets are in the image or the repo.
- The frontend correctly points to the deployed backend URL via `NEXT_PUBLIC_API_BASE_URL`.
- The app is usable by someone who is not running it locally.

Tests:

- `docker compose -f docker-compose.prod.yml config` validates without errors.
- Health endpoint is reachable after container startup.
- CORS rejects requests from unlisted origins.

Acceptance criteria:

- A non-developer can open a URL and use the product end-to-end.

## Phase 11: SaaS Prep

Goal: add hosted product concerns only after the local version proves useful.

Implementation scope:

- Auth.
- Multi-user workspaces.
- Object storage.
- Rate limits.
- Billing.
- Hosted LLM key management.
- Pack registry.
- Public/private visibility.
- Moderation and safety checks.

SaaS-specific tables may include:

```sql
users
organizations
memberships
billing_accounts
usage_events
api_keys
pack_registry_entries
```

Acceptance criteria:

- SaaS work is a thin layer over the local-ready product core, not a rewrite.
