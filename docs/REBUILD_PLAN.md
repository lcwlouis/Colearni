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
5. Phase 3.5 hardening + docs alignment
6. Tutor chat backend for one concept
7. Tutor chat frontend with assistant-ui
8. Mastery + level-up quiz
9. Source provenance + export sanitizer
10. Trail Pack export
11. Research trace
12. Hydration
13. Trail Pack import
14. Guided graph navigation + source sandbox
15. Demo polish
16. Deployment
17. SaaS prep

Do not start with PDF ingestion, SaaS billing/auth, or a public marketplace.

## Plan Maintenance

This file is a living build plan, not a historical snapshot. Agents and humans should update it in the same PR/turn whenever implementation changes the current build state, phase status, API contracts, or deferred work.

Update rules:

- Keep the **Current Build Snapshot** below accurate.
- Add short current implementation notes under the affected phase when scope changes.
- Mark deferred work explicitly instead of leaving stale requirements that imply it is done.
- Keep detailed contracts in `docs/API.md`, `docs/FRONTEND.md`, and domain docs; use this file for status, sequence, and phase-level scope.

## Current Build Snapshot

Last updated: 2026-05-19.

Implemented:

- Local workspace bootstrap with workspace-scoped API paths.
- Workspace CRUD/list basics.
- Trail generation via normal response and temporary progress SSE stream.
- Trail list/detail/delete.
- Per-Trail graph viewer using `@xyflow/react` plus `dagre`, search/filter controls, side-panel concept details, and Start Learning flow.
- Concept detail API with graph context and safe source metadata.
- Tutor backend for one concept with conversation persistence, thin FastAPI routes, prompt registry, mode classifier, SSE streaming, provider thinking events, and optional persisted assistant reasoning traces.
- Tutor frontend using assistant-ui `LocalRuntime`, SSE adapter, persisted history hydration, reasoning trace rendering, Markdown/GFM, KaTeX math, fenced `mermaid` diagrams, copyable code blocks, and concept-level source chips.
- Mastery records and quiz attempts persisted in the DB, with real concept/trail mastery reads, first tutor turn `not_started -> learning`, level-up/practice quiz generation from `mastery_check_labels`, grading, and mastery updates on level-up pass/fail only.
- LLM client support for OpenAI Responses API, OpenAI-compatible providers including OpenRouter/DeepSeek/Gemini/custom, and optional Anthropic SDK.

Not implemented yet:

- True per-message citation/source parts and quote support.
- Guided agentic graph progression across multiple concepts/topics.
- Containerized file-search/source-inspection tooling for agentic source understanding.
- Trail Pack export/import, research trace APIs, hydration, durable generation jobs, dark mode, deployment, auth, and SaaS features.

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

- Add `POST /api/workspaces/{workspace_id}/trails/generate`.
- Generate concept nodes with prerequisites, hierarchy level, difficulty, Bloom target, and mastery check labels.
- Normal generation should target 10-30 nodes; the implemented local-ready API also accepts `max_nodes` for larger graphs up to the per-Trail viewer cap of 100.
- Validate and store graph JSON.
- Repair malformed LLM output once, then fail clearly or fall back to a smaller graph.

Input example:

```json
{
  "topic": "Linear Algebra",
  "goal": "Understand enough for machine learning",
  "target_depth": "apply",
  "max_nodes": 40
}
```

`max_nodes` is optional, defaults to the backend's configured generation size, and must stay within the graph budgets in `docs/GRAPH.md`.

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

Current implementation note:

- `POST /api/workspaces/{workspace_id}/trails/generate/stream` exists as a progress-streaming helper for the frontend. It is intentionally refresh-fragile for now and should be superseded by the durable job-based generation flow in demo polish.

## Phase 3: Graph Viewer

Goal: learners can see, search, and click the Trail.

Implementation scope:

- Add `/trails` and `/trails/[id]`.
- Render nodes, edges, status colors, selected-node side panel, and a start-learning action.
- Concept details are currently side-panel based inside `/trails/[id]`; a deep-link route such as `/trails/[id]/concepts/[conceptId]` can be added later if shareable concept URLs become necessary.
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

## Phase 3.5: Hardening + Docs Alignment

Goal: stabilise the implemented Phase 1-3 surfaces before adding tutor and mastery behavior.

Implementation scope:

- Resolve backend diagnostics/type issues introduced by Phase 1-3 work.
- Keep the intentional local-ready decisions already implemented: workspace-scoped routes, `max_nodes`, streaming Trail generation progress, and side-panel concept details.
- Standardise prompt loading through `PromptRegistry` before adding tutor/quiz/research prompts.
- Ensure Trail generation persistence rolls back cleanly on database/storage failure.
- Remove unused frontend graph packages when safe; the per-Trail viewer uses `@xyflow/react`, not the legacy `reactflow` package.
- Align `docs/REBUILD_PLAN.md` and `docs/API.md` with the implemented Phase 1-3 API.

Requirements:

- The prompt registry loads versioned Markdown prompt files from `backend/app/agents/prompts/` and renders Jinja-style variables without inlining long prompts in services/routes.
- Trail graph persistence commits only after validation and rolls back explicitly if persistence fails.
- `/generate/stream` remains documented as a temporary progress-stream endpoint until Phase 9 durable jobs are implemented.
- Frontend dependency cleanup must not change graph behavior.

Tests:

- Backend tests pass.
- Frontend typecheck/test pass when frontend dependencies are changed.
- `ruff check .` and `git diff --check` pass.

Acceptance criteria:

- Phase 1-3 implementation, docs, and type diagnostics are aligned enough that Phase 4 can build on stable contracts.

## Phase 4A: Tutor Chat Backend For One Concept

Status: implemented for the local-ready slice; mastery side effects and automatic summarisation remain deferred.

Goal: make the first compelling learning loop available through the API.

Implementation scope:

- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat`.
- Add `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversation`.
- Add conversation persistence tables for conversations, turns, and summaries.
- Build tutor context from current concept, nearby graph context, mastery state, learning goal, safe source links, and conversation summary.
- Support tutor modes: `socratic`, `direct`, `repair`, `quiz_prompt`, and `explore`.
- Return a **streaming SSE response** from the chat endpoint so tokens render incrementally.
- Keep route code thin; prompt assembly, mode selection, streaming, and persistence belong in services.

Requirements:

- Default mode is Socratic.
- The tutor asks one good question at a time.
- The tutor can explain when the learner is stuck.
- The tutor does not pretend private sources exist.
- The tutor can reference public source links if present.
- The tutor can say it lacks source material.
- User-visible sourced claims include citations or refuse in strict grounded mode.
- Conversation history is persisted and retrievable for the selected concept.
- Provider-exposed `thinking` chunks stream to the client and are persisted as optional assistant `reasoning` for history rehydration.
- The first backend slice may defer mastery side effects until Phase 5 if `mastery_records` do not exist yet.

Tests:

- Prompt builder includes current concept.
- Prompt builder includes mastery state.
- Prompt builder excludes private sources from public context.
- Mode classifier returns valid mode.
- Chat endpoint streams events in the documented order: `mode`, `token`, `done`.
- Conversation turns are stored and retrieved in chronological order.
- Optional assistant reasoning traces are stored and returned in conversation history.
- Manual tests cover direct answers, incorrect answers, examples, ML links, and unrelated questions.

Acceptance criteria:

- The backend can support a concept-scoped tutor conversation without frontend-specific glue.

## Phase 4B: Tutor Chat Frontend

Status: implemented for the local-ready tutor panel; true per-message sources, quotes, artifacts, and broader assistant-ui add-ons remain deferred.

Goal: make the tutor usable from the graph/concept UI.

Implementation scope:

- Build the chat panel UI using `@assistant-ui/react` with a custom `LocalRuntime` adapter (see `docs/FRONTEND.md` — Tutor Chat UI section).
- The adapter calls `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat`; the library handles streaming, rendering, and local chat state.
- Customise the installed `Thread` component to show the tutor mode badge, concept context header, source citation chips, and mastery level-up prompt.
- Wire the existing concept side panel's Start Learning action to open the tutor UI.

Requirements:

- The chat UI is built with `@assistant-ui/react`; no bespoke chat shell is written from scratch.
- The custom runtime adapter is the only glue between the UI and the FastAPI backend.
- Runtime requests include workspace id, Trail id, concept id, current message, and conversation id when present.
- Streaming tokens appear incrementally in the chat UI.
- Persisted conversation history hydrates into assistant-ui messages when a concept is reopened.
- Tutor Markdown supports GFM, KaTeX math, fenced code blocks, and fenced `mermaid` diagrams.

Tests:

- Runtime adapter sends the correct workspace, Trail, concept, message, and conversation id data to the backend.
- Empty/loading/error states render clearly.
- Markdown/math/Mermaid/code rendering has focused test coverage.
- Manual checks cover Socratic, direct, repair, quiz prompt, and explore interactions.

Acceptance criteria:

- The tutor feels like a coach, not a search engine.
- A learner can start a concept-scoped tutor conversation from the graph.

## Phase 5: Mastery + Level-Up Quiz

Goal: make mastery a motivating product loop.

Implementation scope:

- Add `mastery_records` and `quiz_attempts`.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/level-up`.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/grade`.
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

- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/research`.
- Store search queries, selected public links, source types, license/access status, selection reasons, and excluded source notes.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/hydrate`.

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

- Add `POST /api/workspaces/{workspace_id}/trail-packs/import`.
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

## Phase 9: Guided Graph Navigation + Source Sandbox

Goal: move from isolated concept chat to a guided learning flow that can navigate a bounded part of the graph, decide what to tackle next, and use source-aware file search safely.

Implementation scope:

- Add a graph-progress guide that can work across multiple concepts in the current Trail rather than only inside one concept conversation.
- Let the system guide the learner through a subgraph or topic cluster until the learner finishes the relevant concepts, then suggest the next topic or entry point.
- Use mastery state, graph structure, recent chat history, and Trail goal to decide what to suggest next.
- Add agentic source/file-search capability only through a containerized sandbox scoped to the current workspace or imported pack.
- The sandbox may be Docker-based or equivalent, but it must not expose arbitrary host filesystem access.

Requirements:

- The learner can stay inside a guided flow that spans several connected concepts without losing graph context.
- The guide stays bounded to the current Trail or selected subgraph unless the learner explicitly asks to go broader.
- The guide suggests the next concept or topic based on mastery state and graph structure, not arbitrary LLM preference.
- Any file or source inspection used for deeper grounded explanations runs inside a containerized sandbox with scoped mounts, bounded budgets, and no host-wide filesystem access.
- Source/file search remains evidence-first and provenance-aware; it must not weaken export/privacy rules.

Tests:

- Completing a concept or topic can cause the guide to suggest the next appropriate graph target.
- Guided progression respects prerequisites and does not skip required concepts without justification.
- Guided progression behaves sensibly for mixed mastery states (`not_started`, `learning`, `needs_review`, `mastered`).
- Sandbox file search cannot read outside the mounted workspace scope.
- Sandbox/file-search failures degrade cleanly without crashing the tutor flow.

Acceptance criteria:

- CoLearni can guide a learner through a bounded portion of a Trail, then recommend where to go next.
- Agentic source understanding is possible without giving the model unrestricted filesystem access.

## Phase 10: Demo Polish/User Testing

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

## Phase 11: Deployment

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

## Phase 12: SaaS Prep

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
