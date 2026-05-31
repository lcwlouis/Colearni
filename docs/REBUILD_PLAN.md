# CoLearni Rebuild Plan

## Summary

CoLearni is a local-ready, graph-first learning system.

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

CoLearni is not a generic RAG chatbot. The graph, mastery model, and source provenance model are product primitives.

Product spine:

```text
Create Trail
-> Learn concept
-> Level-up quiz
-> Graph mastery update
-> Safe Trail Pack export
-> Trail Pack import/fork
-> Optional research trace/hydration
```

Dashboard, Learn/Inspect graph UX, source ingestion, retrieval tools, provider-native tools, and future visualisers improve this Trail experience. They must not replace or outrank safe Trail sharing/import.

## Build Order

1. Foundation cleanup
2. Workspace + Trail database models
3. Trail generation endpoint
4. Graph viewer
5. Phase 3.5 hardening + docs alignment
6. Tutor chat backend for one concept
7. Tutor chat frontend with assistant-ui
8. Mastery + level-up quiz
9. Source provenance + safe Trail Pack export
10. Trail Pack import + research trace/hydration
11. Provider tool abstraction foundation
12. Learning dashboard + Learn/Inspect graph UX
13. Source ingestion
14. Retrieval + context tooling
15. Guided graph navigation / recommended next concept
16. Conversation summaries + learner state
17. Onboarding & cold-start pedagogy
18. App shell + cross-Trail navigation wiring (Trails/Graph overlap resolved)
19. Tutor-suggested quiz cards
20. Deferred visualiser / artifact templates
21. Graph gardener + manual graph editing + cluster search
22. Demo polish/user testing
23. Safety + content guardrails (layered, post-core)
24. Product / marketing site
25. Deployment
26. SaaS prep

Do not start with PDF ingestion, SaaS billing/auth, or a public marketplace.

## Plan Maintenance

This file is a living build plan, not a historical snapshot. Agents and humans should update it in the same PR/turn whenever implementation changes the current build state, phase status, API contracts, or deferred work.

Update rules:

- Keep the **Current Build Snapshot** below accurate.
- Add short current implementation notes under the affected phase when scope changes.
- Mark deferred work explicitly instead of leaving stale requirements that imply it is done.
- Keep detailed contracts in `docs/API.md`, `docs/FRONTEND.md`, and domain docs; use this file for status, sequence, and phase-level scope.

Implementation overlay:

- `docs/CURRENT_VARIANT.md` records the current tutor/quiz implementation details and deferred items that landed after the original phase wording.
- If a phase description here drifts from shipped behavior, follow `docs/CURRENT_VARIANT.md` first and update the stale phase text in the same change.

## Current Build Snapshot

Last updated: 2026-05-31.

Implemented:

- Local workspace bootstrap with workspace-scoped API paths.
- Workspace CRUD/list basics.
- Trail generation via normal response and temporary progress SSE stream.
- Trail list/detail/delete.
- Per-Trail graph viewer using `@xyflow/react` plus `dagre`, search/filter controls, side-panel concept details, and Start Learning flow.
- Concept detail API with graph context and safe source metadata.
- Tutor backend for one concept with conversation persistence, thin FastAPI routes, prompt registry, single-agent mode selection, mastery-gated direct/free_explore tool continuation, SSE streaming, provider thinking events, public `status` / `tool_call` / `tool_result` trace events, hidden persisted tool turns for prompt replay, ordered `reasoning_parts`, and one retry without provider thinking when reasoning produces no visible answer.
- Tutor frontend using assistant-ui `LocalRuntime`, concept-side-panel chat, persisted history hydration, ordered reasoning/tool trace rehydration, learner-safe reasoning-summary default with full-trace toggle, Markdown/GFM, KaTeX math, fenced `mermaid` diagrams, copyable code blocks, and concept-level source chips.
- Mastery records, quiz attempts, and quiz drafts persisted in the DB, with real concept/trail mastery reads, first tutor turn `not_started -> learning`, tutor-stream mastery updates, mixed-format level-up/practice quiz generation from `mastery_check_labels`, per-question grading feedback, backend draft reuse with `force_new` refresh, duplicate-request protection (frontend dedupe plus backend advisory lock), practice retry-in-place, and mastery updates on level-up pass/fail only.
- Source provenance sanitizer and safe JSON Trail Pack export, plus backend Trail Pack import/fork, imported research trace preservation/retrieval, and a narrow private hydration-placeholder API.
- LLM client support for OpenAI Responses API, OpenAI-compatible providers including OpenRouter/DeepSeek/Gemini/custom, and optional Anthropic SDK.
- Provider-tool abstraction foundation with explicit internal tool definitions/calls/results, provider registration/normalization helpers, normalized stream events, fake-provider test coverage, and a compatibility adapter for the tutor instruction tool.
- Learning dashboard home with Continue Learning, recent/older Trail sections, delete confirmation, per-Trail progress summaries, and backend-backed recommended-next UI.
- Per-Trail graph Learn/Inspect mode split with `?concept=<id>` deep-link opening, neighbourhood focus in Learn Mode, inspect-only graph controls and edge-label toggle, mastery-aware concept-panel CTAs, and mobile concept sheet refinement.
- Source ingestion foundation: workspace-scoped private upload API, local private object storage root, source revision records with immutable identity fields and mutable parser status/error metadata, concept-source linking API, minimal concept-panel upload/link UI, and export/import safety regressions for revision artifacts.
- Parser pipeline (Phase 10 / Consolidation Item 2): PDF (pdfplumber), markdown, and plaintext parsing into canonical markdown with content-type + extension resolution, heading-aware chunking with line-anchored offsets, `SourceChunk` storage, best-effort embeddings (pgvector column sized from `EMBEDDING_DIM`, ILIKE fallback when absent/disabled), and `trail_id`-driven auto-linking of uploaded sources to concepts.
- Retrieval tooling (Phase 11 / Consolidation Item 3): multi-turn LLM tool-calling loop with per-turn budget, sequential shared-session execution (the per-response tool calls run sequentially against the request's single `AsyncSession`; parallel `asyncio.gather` dispatch was reverted because one asyncpg connection cannot run concurrent operations), dedupe, and workspace/concept scoping, exposing `search_sources`, `read_document_section`, `get_concept_sources`, and `get_graph_neighbourhood`.
- Deterministic backend next-concept recommendation service and per-Trail API endpoint.
- Conversation summaries + learner state (Phase 13): automatic post-turn conversation summarisation (detached follow-up), quiz attempt summaries, mutable learner state updated by both quiz grading and a tutor-driven observer, and multiple conversation threads per concept.
- Onboarding & cold-start pedagogy (Phase 13.5): cached concept primers + key terms, worked-example-first tutor opening, suggested graph entry point, and prior-knowledge capture.
- Tutor-suggested quiz cards (Phase 14): the `suggest_quiz` provider tool (offered every turn), `suggest_quiz` SSE event + `reasoning_parts` kind, and the opt-in CTA reusing the `quiz_drafts` path. Sibling `suggest_flashcards` and `suggest_artifact` tools follow the same opt-in contract.
- Artifact templates + flashcards + pins (Phase 15a–15f): artifacts table + builder sub-agent + detached generation + `/artifacts/build(/stream)`, the `kind -> component` registry (`worked_example`, `comparison_card`, `timeline`, `mini_graph`, `simulation_slider`), the polymorphic pins surface, and the dedicated flashcards subsystem (Leitner scheduler, recall-first review, CSV/JSON export).
- Public product / marketing site route group with fake login (Phase 17.6).

Not implemented yet:

- True per-message citation/source parts and quote support.
- Automated research-agent search, real hydration fetching/indexing, durable background generation jobs, dark mode, deployment, auth, and SaaS features.
- Guided graph focus controls, graph gardener / manual graph editing, and semantic node-cluster search (Phase 16).
- Content-safety guardrails: trail-generation topic gate, tutor runtime scope/refusal hardening, runtime input/output moderation, and a child-safe default mode (see Phase 17.5).
- App shell navigation wiring: the persistent sidebar/mobile-nav shell is real and the app-shell destinations are wired to real pages/data (Dashboard, Trails, Explore, Quizzes, Progress, Sources, Bookmarks, Settings). The remaining cross-Trail/workspace graph surface stays deferred to Phase 16.
- DOCX/PPTX source parsers (PDF/Markdown/plaintext are implemented).

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
- `/generate/stream` remains documented as a temporary progress-stream endpoint until Phase 17 durable jobs are implemented.
- Frontend dependency cleanup must not change graph behavior.

Tests:

- Backend tests pass.
- Frontend typecheck/test pass when frontend dependencies are changed.
- `ruff check .` and `git diff --check` pass.

Acceptance criteria:

- Phase 1-3 implementation, docs, and type diagnostics are aligned enough that Phase 4 can build on stable contracts.

## Phase 4A: Tutor Chat Backend For One Concept

Status: implemented for the local-ready slice; the tutor now uses a single base prompt plus mastery-gated tool continuation, ordered public reasoning/tool traces, and empty-completion retry, while automatic summarisation remains deferred.

Goal: make the first compelling learning loop available through the API.

Implementation scope:

- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat`.
- Add `GET /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/conversation`.
- Add conversation persistence tables for conversations, turns, and summaries.
- Build tutor context from current concept, nearby graph context, mastery state, learning goal, safe source links, and conversation summary.
- Support tutor modes: `socratic`, `direct`, `repair`, `quiz_prompt`, `explore`, and mastery-gated `free_explore`.
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
- Provider-exposed `thinking` chunks, tutor `status` milestones, and public `tool_call` / `tool_result` events stream to the client. Assistant turns persist optional full `reasoning` plus ordered `reasoning_parts` for history rehydration, while raw tool turns stay internal.
- `mode` is emitted before visible `token` events, but gated-mode `status` and `tool_*` activity may appear earlier.
- If reasoning consumes the completion without visible text, retry once without provider thinking before failing.
- Tutor-side mastery effects are implemented in the current slice: first tutor turn sets `learning`, and a tutor retry from `needs_review` resets the concept to `learning`.

Tests:

- Prompt builder includes current concept.
- Prompt builder includes mastery state.
- Prompt builder excludes private sources from public context.
- Tutor stream emits a valid mode before visible tokens.
- Chat endpoint emits documented `status`, `thinking`, `tool_call`, `tool_result`, `mode`, `token`, and `done` events with the documented relative ordering guarantees.
- Conversation turns are stored and retrieved in chronological order.
- Optional assistant reasoning traces and ordered `reasoning_parts` are stored and returned in conversation history.
- Hidden tutor tool-call history is stored for prompt replay but excluded from the public conversation history API.
- Manual tests cover direct answers, incorrect answers, examples, ML links, and unrelated questions.

Acceptance criteria:

- The backend can support a concept-scoped tutor conversation without frontend-specific glue.

## Phase 4B: Tutor Chat Frontend

Status: implemented for the local-ready tutor panel; the tutor stays in the concept side panel with learner-safe reasoning summaries by default, while true per-message sources, quotes, artifacts, and broader assistant-ui add-ons remain deferred.

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
- Rehydrated assistant traces use `reasoning_parts` first so ordered `status` / `thinking` / `tool_call` / `tool_result` boundaries survive refresh.
- The learner-facing reasoning UI defaults to a compact summary with an explicit full-trace toggle.
- Tutor Markdown supports GFM, KaTeX math, fenced code blocks, and fenced `mermaid` diagrams.

Tests:

- Runtime adapter sends the correct workspace, Trail, concept, message, and conversation id data to the backend.
- Runtime rehydration preserves ordered `reasoning_parts` instead of flattening them into one reasoning block.
- Empty/loading/error states render clearly.
- Markdown/math/Mermaid/code rendering has focused test coverage.
- Manual checks cover Socratic, direct, repair, quiz prompt, explore, and ordered reasoning/tool trace interactions.

Acceptance criteria:

- The tutor feels like a coach, not a search engine.
- A learner can start a concept-scoped tutor conversation from the graph.

## Phase 5: Mastery + Level-Up Quiz

Status: implemented, including tutor-side mastery updates, mixed-format quizzes, backend quiz drafts with `force_new`, duplicate-request hardening, per-question grading feedback, practice retry behavior, and mastery-gated tutor direct/free-explore modes.

Goal: make mastery a motivating product loop.

Implementation scope:

- Add `mastery_records` and `quiz_attempts`.
- Add server-side `quiz_drafts` so ungraded quiz cards can be reopened and reused.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/level-up`.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/grade`.
- Generate a short level-up card from mastery check labels.

Requirements:

- Passing updates concept status to `mastered`.
- Failing sets status to `needs_review`.
- Quiz attempts are stored.
- Unsubmitted quiz cards are backend-owned and portable across devices until grading or explicit `force_new` refresh.
- Quiz cards can mix `multiple_choice`, `short_answer`, and `long_answer` questions with adaptive `light` / `standard` / `challenge` difficulty.
- Feedback is specific and useful.
- The learner can retry.
- The tutor cannot mark mastery without a quiz or explicit mastery policy.
- Tutor direct explanation and broader free exploration are mastery-gated to `mastered`, while normal Socratic / repair / bounded explore behaviour remains available earlier.
- Tutor-side internal tool history may be persisted for prompt replay but must not leak through the public conversation API.
- Duplicate quiz-generation requests must safely reuse one draft rather than producing competing cards.

Tests:

- Passing answer updates mastery.
- Failing answer does not mark mastered.
- Quiz attempt is stored.
- Quiz draft is reused unless `force_new` is requested.
- Mixed question types render and grade correctly.
- Graph status changes after mastery update.
- Per-question quiz feedback is returned.
- Hidden tutor tool-call history is excluded from public conversation history.
- Manual tests include good, vague, wrong, and gaming attempts.

Acceptance criteria:

- Mastery gating feels motivating, not punitive.

## Phase 6: Source Provenance + Safe Export

Goal: make safe Trail sharing a core product capability, not a later polish item.

Implementation scope:

- Add Trail Pack export.
- Implement export sanitizer based on source provenance, access, and artifact inheritance rules.
- Generate an export report with included and excluded data.
- Keep export content-light and suitable for public sharing by default.

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

- Public export includes graph structure, learning objectives, abstract mastery check labels, public research source metadata, and research trace when present.
- Public export excludes uploaded files, chunks, embeddings, private notes, chat history, user mastery, private quiz attempts, and private/source-derived generated content.
- User-uploaded sources are removed automatically.
- Research-agent sources remain as links and metadata only.
- Export safety is enforced in backend sanitizer code, not only in UI state.

PR-sized breakdown:

- Provenance/export report service and tests.
- Trail Pack serializer and API endpoint.
- Minimal export UI and manual red-team checklist.

Tests:

- User-upload source never appears in public export.
- Private notes never appear.
- Chunks never appear.
- Embeddings never appear.
- Chat history never appears.
- Mastery records and quiz attempts never appear.
- Public source URL appears as metadata only.
- Research trace appears when present.
- Export report explains included and excluded records.

Acceptance criteria:

- Export cannot leak private or source-derived content by default.
- A learner can export a safe Trail Pack after completing the current learning loop.

Non-goals:

- No public marketplace or moderation workflow yet.
- No redistribution of uploaded, hydrated, or copied source content.

## Phase 7: Trail Pack Import + Research Trace/Hydration

Goal: let learners fork shared Trails and optionally make them locally useful without sharing copyrighted or private content.

Implementation scope:

- Add `POST /api/workspaces/{workspace_id}/trail-packs/import`.
- For V1, import by forking into the current workspace.
- Validate manifest, graph, concepts, sources, and research trace before persistence.
- Current slice adds `GET /api/workspaces/{workspace_id}/trails/{trail_id}/research` for imported trace retrieval. Automated `POST /research` is deferred until real search/provider-tool support exists.
- Store search queries, selected public links, source types, license/access status, selection reasons, and excluded source notes.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/hydrate` as a Phase 7 implementation that creates private hydration placeholder records from allowed public links and/or model-knowledge intent. It does not fetch, chunk, embed, or index content yet.

Requirements:

- Invalid packs are rejected.
- Duplicate slugs are handled deterministically.
- Missing sources are shown clearly.
- Imported packs can be edited locally.
- Imported packs can be hydrated later.
- Research trace stores links and metadata, not copied content.
- Hydration content stays private to the workspace.
- Unknown license means no content redistribution.
- Learners can skip hydration and still learn from the graph, tutor, and model knowledge where allowed.

PR-sized breakdown:

- Import validator and fork persistence.
- Import API and basic UI.
- Research trace model/API.
- Hydration and export-regression tests.

Tests:

- Valid pack imports.
- Malformed pack is rejected.
- Pack with raw chunks is rejected.
- Pack with embeddings is rejected.
- Pack with uploaded files or private notes is rejected.
- Missing sources are reported.
- Graph is created correctly.
- Research trace is created.
- Public URL and selection reason are stored.
- Hydration creates private evidence records.
- Hydrated evidence is not included in public export.
- Unknown-license source is marked no-redistribution.

Acceptance criteria:

- A learner can import a safe content-light Trail Pack, fork it into a workspace, and start learning.
- Imported Trail Packs can become locally useful without making hydrated content public.

Non-goals:

- No marketplace ranking, moderation, account identity, or creator analytics.
- No broad file ingestion beyond the current hydration scope.

Current implementation note:

- Backend import/fork accepts raw JSON packs and the Phase 6 `{ "pack": ..., "report": ... }` wrapper, validates unsafe fields explicitly, creates new Trail/concept/edge/source/link ids, and preserves only safe public source metadata.
- Export includes additive `manifest.topic`, `manifest.goal`, `manifest.target_depth`, `graph.nodes[].difficulty`, and `graph.nodes[].bloom_level` for honest round-trip imports. Older packs without these fields import with documented conservative defaults and warnings.
- Research trace preservation is import-time only for now, stored trail-scoped and retrievable by `GET /research`; no fake search agent is exposed.
- Hydration currently records private placeholder `SourceRecord` rows only. Real fetching, parsing, chunking, embeddings, retrieval indexes, and tutor use of hydrated evidence remain deferred to ingestion/retrieval phases.

## Phase 8: Provider Tool Abstraction Foundation

Status: implemented for the backend foundation slice; provider-native retrieval/research/hydration/quiz/learner-state tools remain deferred.

Goal: add provider-native tool calling early enough that research, hydration, retrieval, guided learning, quiz suggestions, and learner-state updates do not grow ad-hoc JSON plumbing.

Implementation scope:

- Define an internal provider-agnostic tool schema for tool definitions, calls, arguments, results, and safe public previews.
- Normalize tool call/result events across OpenAI Responses API, OpenAI-compatible Chat Completions providers including OpenRouter, and Anthropic Claude.
- Preserve the existing direct provider approach in `LLMClient`; do not introduce LiteLLM.
- Add fake provider/tool tests that do not call live LLMs.
- Migrate one low-risk internal flow if appropriate, likely the tutor `get_tutor_instructions` flow.
- Preserve tutor SSE streaming, reasoning trace UI, hidden tool turns, sanitized public `tool_call` / `tool_result` events, and conversation replay behaviour.
- Document how future retrieval/source/quiz/learner-state tools plug into the abstraction.

Requirements:

- The abstraction is a small provider-tool layer, not a full agent framework rewrite.
- Tool execution stays service-owned and budgeted.
- Tool schemas are explicit and testable.
- Provider-specific quirks stay behind adapters.
- Existing tutor behavior remains compatible during migration.
- Raw internal tool results never leak through public APIs unless explicitly sanitized.

PR-sized breakdown:

- Internal tool schema and fake tool executor.
- Provider adapter tests for normalized call/result shapes.
- Tutor instruction-tool migration or a no-op compatibility adapter.
- Architecture/API documentation for future tools.

Tests:

- OpenAI Responses tool call maps to normalized tool call/result records.
- OpenAI-compatible Chat Completions/OpenRouter tool call maps to the same normalized records.
- Anthropic tool use maps to the same normalized records.
- Fake provider can stream text, reasoning, tool calls, tool results, and final text.
- Tutor streaming event order remains compatible with `docs/API.md`.
- Hidden tool turns are persisted for replay but excluded from public conversation history.
- Invalid tool arguments fail safely without an unbounded retry loop.

Acceptance criteria:

- Future source/retrieval/quiz/learner-state tools can be added without provider-specific parsing in each service.
- Current tutor streaming and replay behavior are preserved.

Current implementation note:

- `backend/app/agents/provider_tools.py` defines the internal tool schema, strict argument validation subset, normalized calls/results, sanitized public previews, provider tool-definition adapters, and normalized stream events.
- `backend/app/agents/llm_client.py` keeps direct provider calls and can register/normalize tools for OpenAI Responses API, OpenAI-compatible Chat Completions/OpenRouter, and Anthropic.
- The existing tutor `get_tutor_instructions` flow is wrapped by the normalized tool schema through a compatibility adapter. It intentionally preserves legacy tagged prompt replay, public SSE `tool_call` / `tool_result` payloads, hidden tool turns, ordered `reasoning_parts`, and empty-completion retry behavior.
- Tool execution remains service-owned. No retrieval/search/hydration/provider-tool loop was added in this slice.

Non-goals:

- No LiteLLM.
- No complex multi-agent framework.
- No unbounded autonomous tool loops.

## Phase 9: Learning Dashboard + Learn/Inspect Graph UX

Status: implemented for the current frontend slice.

Goal: make CoLearni feel approachable to non-technical learners while preserving the current technical graph for inspect and power-user use.

Implementation scope:

- Turn home into a learning dashboard, not only a Trail list.
- Add Continue Learning, mastery progress per Trail, Recommended Next action/card, recent Trails, older Trail search/list, and a create-new-Trail entry point.
- Split the per-Trail graph experience into Learn Mode and Inspect Mode without replacing React Flow.
- Make Learn Mode the approachable default with fewer visible controls, selected-node neighbourhood focus, progressive disclosure, and concept-panel-first next actions.
- Preserve Inspect Mode as the current technical graph surface with full edge types, filters, layout controls, legend, and optional edge labels.
- Keep mobile focused on clear next actions and selected concept details over dense graph controls.

Learn Mode requirements:

- Hide global graph clutter by default.
- Show relationship meaning through the side panel, selected/hovered neighbourhood, and focus states.
- Keep existing line styles for relationship types.
- Do not show all edge labels globally.
- Use neighbourhood focus around the selected concept.
- Concept panel answers: What is this? Why does it matter? What should I do next? What is connected to it? What sources support it?

Inspect Mode requirements:

- Preserve the existing React Flow graph implementation.
- Keep full edge types, filters, layout controls, and legend available.
- Add optional `show edge labels` toggle only in Inspect Mode.
- Keep graph usable at the documented per-Trail cap.

Concept panel CTA hierarchy:

| Mastery state | Primary CTA |
|---|---|
| `not_started` | Start Learning |
| `learning` | Continue Tutor |
| `needs_review` | Review Weak Points |
| `mastered` | Practice / Explore Further |

PR-sized breakdown:

- Dashboard shell and Trail progress cards.
- Learn/Inspect mode toggle with preserved Inspect defaults.
- Concept panel CTA hierarchy and mobile bottom sheet refinement.
- Edge-label toggle limited to Inspect Mode.

Tests:

- Dashboard renders empty, loading, populated, and error states.
- Continue Learning chooses a valid in-progress or recently touched Trail.
- Trail mastery summaries render correctly.
- Learn Mode hides advanced controls by default.
- Inspect Mode exposes current filters/layout/legend controls.
- Edge labels are not globally visible by default.
- Optional edge labels only appear in Inspect Mode.
- Concept panel CTA changes by mastery status.
- Mobile graph/concept interactions remain usable.

Acceptance criteria:

- The home page pulls learners back into progress.
- The graph remains central without overwhelming the default learning view.
- Power-user graph inspection remains available.

Non-goals:

- No heavy gamification before the learning loop, sharing, ingestion, and retrieval work are stable.
- XP/streaks may be future polish, but are not core in this phase.

Current implementation note:

- Home computes per-Trail progress and Continue Learning selection from Trail detail records, while recommended-next concept UI is populated from the backend `/next` endpoint.
- Learn Mode is the default graph surface with simplified controls and selected-neighbourhood focus; Inspect Mode preserves filters/layout/legend plus the edge-label toggle, and `?concept=<id>` opens the concept sheet directly.

## Phase 10: Source Ingestion

Status: foundation slice, concept-source linking, and the parser pipeline (PDF/markdown/plaintext parsing, heading-aware chunking, best-effort embeddings, and `trail_id` auto-linking) are implemented (see `docs/archive/CONSOLIDATION_PLAN.md` Item 2). Durable background ingestion jobs remain deferred.

Goal: ingest common learner documents into private, provenance-aware source records that can later power controlled retrieval.

Priority formats:

- PDF.
- DOCX.
- PPTX.

Deferred formats:

- CSV/Excel.
- Arbitrary file types.
- Raw filesystem-browsing agent as the primary retrieval path.

Preferred ingestion flow:

```text
Uploaded file
-> private object storage
-> parser
-> markdown-like canonical text
-> source revision
-> chunks
-> embeddings / full-text index
-> concept-source links
-> controlled retrieval/open tools
```

Implementation scope:

- Store uploaded files as private objects with object keys and content hashes.
- Create source revision records with parser version and parse metadata.
- Convert parsed output to markdown-like canonical text before chunking.
- Build chunks and full-text/vector indexes behind bounded jobs.
- Link sources or chunks to concepts through explicit concept-source links.
- Preserve export sanitizer rules so private uploads and derived artifacts never enter public Trail Packs.

Requirements:

- Do not use git internally for user source tracking in V1.
- Use content hashes, parser version, source revision records, object keys, and database/object-storage versioning.
- Ingestion failures leave the source in a clear failed/skipped state.
- Uploaded and parsed source content is private by default.

PR-sized breakdown:

- Source object/revision schema and upload storage. Implemented as upload-only foundation with `parser_name="none"`, `parser_version="upload-only-v1"`, and no parsed text/chunks/indexes.
- Parser pipeline for one format, then extend to the other priority formats.
- Chunk/index job and source status UI.
- Concept-source linking and export safety regressions.

Tests:

- Generic upload-only storage creates private source records; PDF/DOCX/PPTX parser support is deferred.
- Content hash and parser version are stored.
- Source revisions are immutable records.
- Parser failure is visible and does not create partial public content.
- Chunks and embeddings are excluded from export.
- Concept-source links can be created and read.
- No endpoint exposes raw private source text without workspace scope.

Acceptance criteria:

- A learner can upload common study material, see ingestion status, and attach it to a Trail/concept without weakening Trail Pack safety.

Non-goals:

- No broad filesystem browsing.
- No public redistribution of uploaded or parsed content.

## Phase 11: Retrieval + Context Tooling

Status: retrieval service, tool definitions, and the multi-turn LLM tool-calling loop are implemented (vector search with pgvector plus ILIKE fallback; `search_sources`, `read_document_section`, `get_concept_sources`, `get_graph_neighbourhood`; see `docs/archive/CONSOLIDATION_PLAN.md` Item 3 and `docs/CURRENT_VARIANT.md`). `open_source_chunk` is superseded by `read_document_section` and remains deferred.

Goal: provide scoped, budgeted retrieval tools that support tutor grounding without whole-workspace search by default.

Tutor context priority:

1. Current concept.
2. Mastery state.
3. Learner state summary, when available.
4. Prerequisites, containing, contained, and related nodes.
5. Explicitly linked sources.
6. Recent turns or conversation summary.
7. Source chunks only when needed.

Controlled tools:

- `search_sources(query, concept_id?)`.
- `open_source_chunk(chunk_id)`.
- `get_concept_sources(concept_id)`.
- `get_graph_neighbourhood(concept_id)`.

Implementation scope:

- Register retrieval tools through the provider tool abstraction.
- Enforce workspace, Trail, concept, source, and token budgets.
- Prefer concept-linked sources before broad workspace search.
- Return citation-ready source metadata and chunk ids.
- Keep chunk opening explicit instead of dumping large source text into every prompt.

Requirements:

- Avoid whole-workspace retrieval by default.
- Retrieval must be evidence-first and provenance-aware.
- Tool calls must have deterministic stop reasons and bounded result sizes.
- Strict grounded mode either cites allowed evidence or refuses.

PR-sized breakdown:

- Retrieval service with deterministic budgets.
- Tool wrappers and fake-provider tests.
- Tutor context integration behind feature flags or narrow triggers.
- Citation/source-part API contract update when answer-level citations are emitted.

Tests:

- Retrieval scopes to current concept and linked sources first.
- Whole-workspace retrieval does not run unless explicitly requested and budgeted.
- Tool result sizes are capped.
- Private sources from other workspaces cannot be read.
- Chunk opening requires a valid chunk id in scope.
- Sourced tutor answers cite allowed evidence or refuse in strict mode.
- Tool failures degrade without crashing tutor streaming.

Acceptance criteria:

- The tutor can use private ingested sources when useful while keeping context bounded and export safety intact.

Non-goals:

- No raw filesystem browsing as the primary retrieval architecture.
- No unbounded source-search loops.

## Phase 12: Guided Graph Navigation / Recommended Next Concept

Status: recommendation service, API endpoint, dashboard consumption, and Trail-detail recommendation UI implemented. Guided focus controls remain deferred.

Goal: guide the learner through the Trail with deterministic graph/mastery heuristics before adding LLM-based navigation.

Recommended next concept V1 heuristic:

- Choose a concept with status `not_started` or `needs_review`.
- Prefer concepts whose prerequisites are `mastered` or already `learning`.
- Prefer `topic` or `subtopic` over `umbrella` or `granular`.
- Prefer lower difficulty first.
- If all concepts are mastered, suggest review, adjacent exploration, or generating an extension.

Implementation scope:

- Add a deterministic recommendation service for one Trail.
- Expose the recommendation to the dashboard, graph side panel, and Trail detail view.
- Add guided graph navigation that focuses the selected or recommended neighbourhood.
- Keep recommendations explainable with short reasons.
- Add LLM-based planning only after deterministic behavior is validated.

Requirements:

- Recommendations are based on mastery state, graph structure, difficulty, and concept level.
- The guide stays bounded to the current Trail or selected subgraph unless the learner explicitly asks to go broader.
- The guide must not skip prerequisites without an explainable reason.
- No LLM call is required for the V1 recommendation.

PR-sized breakdown:

- Recommendation service and tests.
- API endpoint and dashboard/graph consumption.
- Guided focus controls in Learn Mode.
- Manual validation on sample Trails.

Tests:

- Mixed mastery states produce expected recommendations.
- Prerequisites are respected.
- `needs_review` concepts can be prioritized for repair.
- Topic/subtopic preference wins over umbrella/granular when otherwise tied.
- All-mastered Trails return review/explore/extension guidance.
- Dashboard and concept panel render recommendation reasons.

Acceptance criteria:

- CoLearni can suggest a reasonable next concept without relying on arbitrary LLM preference.

Non-goals:

- No autonomous cross-Trail learning agent.
- No unbounded graph traversal.

## Phase 13: Conversation Summaries + Learner State

Status: LLM conversation summarizer prompt/service, quiz attempt summaries, mutable learner state, tutor learner-state/active-quiz context, prior-attempt quiz generation context, prior-attempt API, and quiz result/history UI implemented. Learner state is now updated by BOTH triggers: quiz grading and a tutor-driven post-`done` observer pass (see Phase 13.5d below and `docs/CURRENT_VARIANT.md` → Tutor Runtime). Automatic conversation summarisation now runs as a detached post-turn follow-up. Multiple conversation threads per concept are implemented (migration `0018`, `POST/GET .../conversations`; see `docs/API.md`).

Goal: keep tutor context useful over time without permanently over-weighting old failed attempts after the learner improves.

Implementation scope:

- Generate automatic conversation summaries per concept/thread.
- Generate quiz attempt summaries from immutable quiz attempts.
- Add mutable learner state summaries that reflect current understanding, misconceptions, strengths, and next repair targets.
- Plan for multiple threads per concept/topic later, without requiring it in the first summary PR.

Important distinction:

- Quiz attempts are immutable records.
- Learner state summary is mutable and should reflect current understanding.
- Old failed quizzes should not permanently bias the tutor after the learner improves.

Requirements:

- Summaries are workspace-scoped.
- Summary jobs are bounded and idempotent.
- The tutor reads learner state before raw long history when available.
- Learner state updates are triggered by tutor turns, quiz attempts, and explicit resets only through owned services/tools.

PR-sized breakdown:

- Conversation summary generation and tests.
- Quiz attempt summary records.
- Mutable learner state model/service.
- Tutor context integration.

Tests:

- Summaries cover the intended turn range and record `turns_covered_to`.
- Re-running summary generation is idempotent.
- Quiz attempts remain immutable.
- Learner state updates after pass/review events.
- Improved learner state can supersede old failed-quiz bias.
- Tutor prompt uses learner state summary within context budget.

Acceptance criteria:

- Longer-running tutor use stays focused and adaptive without leaking private history or overloading prompts.

Non-goals:

- No global cross-workspace memory.
- No opaque profile updates outside explicit learner-state services.

## Phase 13.5: Onboarding & Cold-Start Pedagogy

Goal: fix the "pure Socratic from a cold start feels painful, and the learner does not know what they do not know" problem by adding orientation before interrogation. Socratic questioning stays the steady-state teaching mode, but the cold-start experience leads with brief teaching. The primary audience is intentional adult and young-adult learners, so the tutor should explain generously as teaching while still not degrading into an answer/cheatsheet machine.

Pedagogy framing: this phase operationalizes "I do -> we do -> you do" (gradual release of responsibility) and scaffolding within the learner's zone of proximal development. Exposition is allowed and encouraged at the start of a concept; Socratic questioning takes over once the learner has the raw material to reason with.

Sub-phases:

13.5a — Concept primers + key-terms glossary (independent; build first):

Status: backend implemented (now `concept_primer.v2.md` with `sample_questions`, streaming generation, and a single repair attempt for small/local models) + `ConceptPrimerOutput`/`ConceptPrimerRead` schemas + idempotent per-concept `generate_concept_primer` service (cached in `ConceptNode.metadata_json["primer"]`, `force_new` to regenerate) + `POST .../concepts/{concept_id}/primer` and `.../primer/stream` routes + concept-detail wiring (`primer` field) + frontend primer panel + tests. See `docs/CURRENT_VARIANT.md` → Concept Primer Variant. Background pre-generation loop remains out of scope.
- Add a versioned `concept_primer` prompt that, given a concept (title, concept level, Bloom target, mastery labels) plus the Trail topic/goal, returns a short overview paragraph and 3-6 key terms with one-line definitions.
- Generate primers in a separate pass after graph generation, NOT inlined into `trail_generation`. Keeping graph JSON lean preserves generation reliability on smaller/local models, which struggle with large structured outputs and parallel tool calls.
- Provide an idempotent per-concept service that generates and caches the primer on the concept (e.g. `metadata_json` or dedicated columns). The same service supports both lazy generation on first concept open and a bounded background pre-generation pass, so the eventual pre-generate-vs-lazy choice is a calling-side decision, not a rewrite.
- The concept detail API returns the primer/glossary when present.
- Primers and glossary are abstract concept-level content (not source-derived), so they are eligible for Trail Pack export.

13.5b — Worked-example-first opening move:
- On a `not_started` or `learning` concept, the tutor's opening turn briefly teaches (frame the concept plus one worked example) before shifting into Socratic questioning.
- Direct explanation remains allowed as teaching, but full answer-dumping stays mastery-gated. After any exposition the tutor loops back to a short check.

13.5c — Suggested graph entry point (suggestion only):
- On a fresh Trail with nothing started, surface a recommended starting concept using the existing deterministic recommender (`services/recommendation.py` / the `/next` endpoint), clearly framed as a suggestion.
- The learner can still start from any node; the suggestion never forces a path.

13.5d — Prior-knowledge capture into learner state:

Status: implemented. The create-Trail prior-knowledge field is captured and fed to the tutor classifier, and the tutor now updates mutable learner state over time through an owned post-`done` observer pass (`maybe_update_learner_state_from_chat` + `learner_state_update.v1.md`), gated by `LEARNER_STATE_UPDATE_INTERVAL` and failure-isolated. See `docs/CURRENT_VARIANT.md` → Tutor Runtime.
- Add an optional prior-knowledge / self-rated familiarity field to the create-Trail input.
- Store it as part of mutable learner state (Phase 13). The tutor updates it over time through an owned tool, so the exposition-vs-Socratic ramp adapts as the learner demonstrates understanding.
- Depends on Phase 13 learner state. If Phase 13 is not yet implemented, store the initial value as a simple field and migrate it into learner state when Phase 13 lands.

Requirements:

- Graph generation stays lean; primer generation is a separate, bounded pass with a short token budget and low reasoning effort.
- Primer generation is idempotent and cached; repeated requests for the same concept do not re-call the model.
- The suggested entry point is advisory only and never blocks free navigation.
- Exposition must not become unlimited answer-dumping; mastery gating on full direct mode is preserved.

PR-sized breakdown:

- 13.5a: `concept_primer` prompt + schema + idempotent per-concept generate/cache service + concept-detail wiring + tests.
- 13.5b: tutor opening-move prompt/behaviour change + tests.
- 13.5c: fresh-Trail suggested entry point in the recommender/UI.
- 13.5d: create-Trail prior-knowledge field + learner-state integration.

Tests:

- Primer generation returns a valid overview + key terms and is cached idempotently (fake generator, no live model).
- Concept detail returns the primer/glossary when present and omits it cleanly when absent.
- The tutor opens a fresh concept with a brief teach-then-question turn rather than a cold question.
- A fresh Trail surfaces a suggested entry concept without restricting navigation.
- Primers and glossary are eligible for export but never leak source-derived content.

Acceptance criteria:

- A learner opening a brand-new Trail gets an orienting starting point, a concept primer/glossary, and a tutor that teaches before it questions, without the experience feeling like an interrogation or a cheatsheet.

Non-goals:

- No inlining of primers into the graph-generation call.
- No removal of mastery gating on full direct-answer mode.
- No forced learning path; the entry point stays a suggestion.

## Phase 13.7: App Shell + Cross-Trail Navigation Wiring

Goal: turn the new persistent app shell (sidebar + mobile nav under the `(app)` route group) into wired surfaces backed by real data, while keeping the future cross-Trail/workspace graph deferred. The owner built the shell and the app-shell destinations as a visual direction; this phase wires each surface to backend data or marks it explicitly deferred.

Status: app shell SHIPPED and wired (sidebar, mobile nav, `(app)/layout.tsx`, `UserProfileChip`, and routed pages). The only remaining Phase 13.7 deferral is the future cross-Trail/workspace graph surface under Explore (Phase 16).

### Trails vs Graph overlap — RESOLUTION

The sidebar currently lists both "Trails" and "Graph", and both point at `/trails` (the "Graph" item uses a `__never__` match-prefix hack so it never highlights). This is a genuine conceptual overlap, not just a routing bug: per `docs/FRONTEND.md` and `docs/GRAPH.md`, a Trail IS a concept graph, and the per-Trail graph viewer lives at `/trails/[id]`. There is no standalone graph surface today, and a cross-Trail/workspace-level graph is an explicit FUTURE feature (the "Sigma.js trigger" in `docs/FRONTEND.md`; the semantic cluster work in Phase 16).

Decision (LOCKED):

- The per-Trail graph is a VIEW of a Trail (`/trails/[id]`), never a separate top-level destination. Remove the standalone "Graph" sidebar item so two items no longer point at `/trails`.
- The future cross-Trail / workspace-level graph belongs under "Explore", NOT a revived top-level "Graph" item. Explore is the home for cross-Trail discovery (workspace-level concept graph, Trail Pack import/fork, cross-Trail concept search). This keeps React Flow per-Trail and reserves the Sigma.js-class surface for Explore when it is built.
- "Trails" remains the canonical entry to the list + per-Trail graph viewer. The `__never__` hack is removed with the duplicate item.

### Surface wiring map

Each placeholder maps to existing backend data or an explicit deferral. None of these introduce new tutor-event mechanisms.

| Surface | Wiring | Backing data / phase |
|---|---|---|
| Home (`/dashboard`) | Already real | Phase 9/12 dashboard + `/next` recommendation |
| Trails (`/trails`, `/trails/[id]`) | Already real | Phase 1–3 trail list + graph viewer |
| Explore | Cross-Trail discovery hub | Trail Pack import/fork (Phase 7); cross-Trail concept search + future workspace graph (Phase 16). Current surface: Trail Pack import CTA + a cross-Trail concept search list. |
| Quizzes | Cross-Trail quiz history + practice hub | Quiz attempts (Phase 5) surfaced through the workspace quiz-history page. |
| Progress | Cross-Trail mastery/progress overview | Mastery summaries aggregated across the workspace's Trails. |
| Sources | Workspace source library | Source ingestion API (Phase 10) — list workspace sources + revisions + ingestion status. |
| Bookmarks | Saved/Pinned surface | Pin system (Phase 15b) with artifacts, quiz attempts, flashcard decks, and concept pins. |
| Settings | Workspace/profile/theme settings | Workspace endpoints + theme toggle (dark mode, Phase 17). Current surface: workspace name + theme; auth-scoped settings deferred. |

### Implementation scope

- Keep Explore as the future home for any cross-Trail graph. The shipped surfaces are already wired; the remaining Phase 13.7 follow-up is the future workspace-level graph surface in Explore.
- Preserve thin FastAPI routes and service-owned aggregation logic for the workspace quiz-history and progress views.
- Explore currently = Trail Pack import entry + cross-Trail concept search; the workspace-level graph is explicitly deferred to Phase 16.
- Bookmarks now renders saved artifacts, quiz attempts, flashcard decks, and concept pins. Settings ships a minimal workspace-name + theme surface (full settings deferred with auth).

### PR-sized breakdown

- Completed: nav cleanup and placeholder wiring; the remaining follow-up is the Phase 16 workspace graph in Explore.
- Sources surface: workspace source-library list reusing `sources.py`.
- Progress surface: workspace progress aggregation endpoint (service + thin route) + page.
- Quizzes surface: workspace quiz-attempt history endpoint (concept->trail->workspace join) + page.
- Explore surface: Trail Pack import entry + cross-Trail concept search.
- Settings surface: workspace name + theme toggle.

### Requirements

- No new tutor-event mechanisms here; this is navigation + read surfaces over existing data.
- New aggregation endpoints stay workspace-scoped and bounded (no whole-workspace unbounded traversal; obey `docs/GRAPH.md`).
- Public Trail Pack content rules are unchanged; Explore import/export stays provenance-gated.
- Quiz/progress aggregation must scope via `concept -> trail -> workspace` until quiz tables gain `workspace_id` (tracked as P1 tech-debt).

### Tests

- The sidebar exposes exactly one destination for the per-Trail graph (no duplicate `/trails` item) and no `__never__` hack remains.
- The workspace quiz-history endpoint returns only attempts whose concept's trail belongs to the workspace.
- The workspace progress endpoint aggregates mastery only across that workspace's Trails.
- The Sources surface lists only the active workspace's sources.

### Acceptance criteria

- The app shell's navigation reflects real product surfaces: the Trails/Graph overlap is resolved, already-backed surfaces (Sources, Progress, Quizzes) show real workspace data, Explore hosts cross-Trail discovery, and Bookmarks/Settings are honestly scoped (stub vs. minimal) with clear deferrals recorded.

### Non-goals

- No workspace-level/cross-Trail GRAPH rendering yet (Sigma.js-class surface is deferred to Phase 16/Explore).
- No auth-scoped settings (waits for SaaS prep).
- No new tutor events or quiz/artifact generation paths.

## Phase 14: Tutor-Suggested Quiz Cards

Goal: let the tutor suggest an appropriate quiz card at the right moment without inline-generating, opening, or grading it.

Status: SHIPPED (backend + frontend implemented and tested). The `suggest_quiz` provider tool is offered every turn, surfaced as a `suggest_quiz` SSE event, persisted in `reasoning_parts` (kind `suggest_quiz`), and rendered as an opt-in CTA that reuses the existing `quiz_drafts` path.

Event/tool flow:

```text
tutor emits suggest_quiz(quiz_type, reason)   # concept_id is trusted backend context, not a model arg
-> client renders an opt-in suggest_quiz SSE card
-> learner clicks the CTA (never auto-opened)
-> existing backend-owned quiz_drafts generate/reuse path runs
```

Implementation scope:

- `suggest_quiz` is a REAL normalized provider tool registered through `backend/app/agents/provider_tools.py` (same registration path as the retrieval tools), surfaced to the client as a new `suggest_quiz` SSE event.
- The tool is available on EVERY tutor turn (NOT gated on the concept having sources, unlike the retrieval tools).
- Tool args are exactly `quiz_type` (enum: `level_up` | `practice`) and `reason` (a short, learner-visible string). `concept_id` is NOT a model argument — the backend always uses the trusted current concept (the same pattern as the retrieval tools, where the schema deliberately omits `concept_id`).
- Trigger is model-decided but mastery-aware via PROMPT guidance only: suggest `practice` anytime it would help; suggest `level_up` only when mastery looks near-ready. There is no hard backend mastery gate in v1.
- The CTA is opt-in: the learner clicks it to act; the client NEVER auto-opens the quiz. Clicking reuses the existing backend-owned `quiz_drafts` generate/reuse path — no new quiz endpoint is required.
- The `reason` is persisted on the assistant turn's `reasoning_parts` under a new part kind `suggest_quiz`, so the CTA rehydrates on reload alongside the rest of the turn trace.

Requirements:

- The tutor cannot grade or update mastery. This stays structurally enforced — grading and mastery updates live in the quiz service, and `suggest_quiz` only emits an intent.
- Suggested quiz cards must not include private/source-derived content unless the backend quiz system explicitly allows it under current safety rules.
- Dedupe is layered: the backend `(concept_id, quiz_type)` uniqueness already guarantees a single draft, and the frontend collapses to a single active CTA per `quiz_type`, so duplicate suggestions focus the same draft rather than spawning competing cards.
- Suggestions include a short learner-visible `reason`, persisted as above.

PR-sized breakdown:

- `suggest_quiz` provider-tool definition + backend validation (trusted `concept_id`, `quiz_type` enum, `reason`) + the `suggest_quiz` SSE event.
- `suggest_quiz` `reasoning_parts` persistence/rehydration (new part kind).
- Frontend opt-in CTA/card rendering + single-active-CTA-per-`quiz_type` collapse.
- Draft reuse integration (click → existing `quiz_drafts` generate/reuse path).
- Prompt guidance (mastery-aware suggest rules) + tutor/tool tests.

Tests:

- `suggest_quiz` is offered on a turn with no sources (not gated on sources).
- A `suggest_quiz` tool call emits a frontend-visible CTA without generating, opening, or grading anything.
- Clicking the CTA reuses the existing backend draft when present.
- The model cannot pass `concept_id`; the backend always scopes to the trusted current concept.
- The tutor cannot update mastery through the suggestion event.
- Duplicate suggestions of the same `quiz_type` collapse to one active CTA.
- The `reason` persists on `reasoning_parts` (kind `suggest_quiz`) and rehydrates on reload.

Acceptance criteria:

- The tutor can nudge learners toward level-up or practice at the right moment while the backend remains the owner of quiz cards and mastery, and the learner stays in control of whether the quiz opens.

Non-goals:

- No inline tutor-generated quiz that bypasses quiz drafts.
- No auto-opening of the quiz from a suggestion.
- No tutor-owned mastery decisions and no hard backend mastery gate in v1.

## Phase 15: Deferred Visualiser / Artifact Templates

Goal: add helpful learning artifacts using trusted, validated templates — never arbitrary LLM-generated JavaScript. Artifacts are persisted, retrievable, and provenance-gated just like quizzes.

Status: decisions LOCKED; **15a–15f SHIPPED** (implemented + tested). Frontend swipe UI for flashcards (15c) and tutor `suggest_artifact` (15f) are wired. The remaining UX follow-up is the richer inline-in-chat trigger experience for `suggest_flashcards` / `suggest_artifact`; today both remain CTA-first. See `docs/CURRENT_VARIANT.md` for the authoritative implementation overlay.

Guiding philosophy (unchanged): trusted templates only, no arbitrary JS, no live code/formula execution from the model. The LLM emits a validated data payload; the BACKEND owns generation, IDs, citations, persistence, and provenance/export gating; the frontend renders through a fixed component registry that degrades to text on any failure.

### Phase 15a: Artifact foundation + builder sub-agent

Status: **SHIPPED** (foundation + builder sub-agent + detached generation + concept-panel artifacts surface). The artifact-builder service (`backend/app/services/artifact_builder.py`) runs a bounded retrieval loop reusing `execute_retrieval_tool` under `tutor_tool_call_budget`, does exactly one repair attempt, drops citations not matching a retrieved `source_revision_id`, downgrades zero-citation payloads to `local_only`, and persists via `create_artifact`. `ArtifactGenerationManager` mirrors `PrimerGenerationManager` (own DB session, cancel-safe, in-process single-flight + `pg_advisory_xact_lock`, lifespan teardown). Endpoints `POST .../artifacts/build` and `POST .../artifacts/build/stream` (SSE; `force_new` rejected on stream). Frontend `ArtifactsPanel` lists + generates artifacts via the SSE path. (Originally only the foundation — table/migration `0014_artifacts`, envelope schemas, list/get endpoints, registry with `worked_example`/`comparison_card` — was shipped; the builder, detached generation, dedupe, and renderer wiring are now complete.)

Implementation scope:

- A new `artifacts` table: workspace-scoped, `concept_id` nullable, `trail_id` (artifacts are BOTH concept-attached AND trail-attached), `artifact_type` (discriminated), a validated typed payload, `source_refs[]`, and advisory-lock dedupe (mirroring `quiz_drafts`). List/retrieval endpoints + a history UI — persisted and retrievable just like past quizzes.
- A shared artifact ENVELOPE schema: `{ artifact_version, kind, title, caption?, text_fallback (REQUIRED), provenance{source_ids, visibility, citations[]}, data{kind-specific} }`. Strict Pydantic output schema (`extra="forbid"`) plus a versioned lenient read schema, mirroring `ConceptPrimerOutput`/`ConceptPrimerRead`. Every payload carries a mandatory `text_fallback`.
- A frontend component REGISTRY (`kind -> component`) generalizing the existing `{type:"data", name}` dispatch, wrapped in an error boundary that degrades to `text_fallback` (like the existing Mermaid `catch -> textContent` path). Unknown or invalid `kind` renders `text_fallback`.
- A dedicated artifact-builder SUB-AGENT exposed as a tool: its own specialised prompt + its own BOUNDED retrieval loop reusing the existing retrieval tools (`search_sources`, `read_document_section`, `get_graph_neighbourhood`, `get_concept_primer`) under the existing `tutor_tool_call_budget` (3). Structured JSON output + exactly ONE repair attempt, then fail. The BACKEND owns generation, IDs, citations, persistence, and provenance/export gating — the model returns a validated payload only. Every citation must map to a real retrieved `source_revision_id` or be dropped. On-demand only; it returns a reference, not a blob streamed through chat. (Rationale: small/local LLMs cannot juggle tutoring + retrieval + per-template JSON in one context; this is the orchestrator-worker pattern, kept as a small direct-provider adapter, NOT an agent framework.)
- Background/detached generation with LIVE status in chat (shimmer / SSE status events) that CONTINUES if the learner leaves the page or refreshes — mirroring the existing `PrimerGenerationManager` detached-task + subscription pattern (its own DB session from the app sessionmaker; cancel-safe; lifespan shutdown owns clean teardown). The SSE response only subscribes; the background task persists independently.
- Export/provenance: concept-level (non-source-derived) artifacts stay LOCAL-ONLY like the primer (NOT in public Trail Pack export) for now. Source-derived artifacts inherit provenance gating: public-export-eligible only if EVERY contributing source passes `_can_include_source_in_public_export` AND none is `user_upload` (all-or-nothing).
- Ship 2 read-only templates first to prove the pipeline: `worked_example` and `comparison_card`.

Requirements:

- No arbitrary LLM-generated JavaScript as the artifact path.
- Artifacts inherit source provenance restrictions; concept-level artifacts are local-only.
- Every artifact payload validates against the strict envelope and carries a mandatory `text_fallback`.
- Rendering failures degrade to `text_fallback`; unknown kinds degrade safely.
- Citations map to real retrieved `source_revision_id`s or are dropped.

PR-sized breakdown:

- `artifacts` table + migration + list/retrieval endpoints.
- Envelope strict/read schemas + frontend registry + error-boundary fallback.
- Artifact-builder sub-agent (prompt + bounded retrieval loop + one repair).
- Detached generation manager + SSE status subscription.
- `worked_example` + `comparison_card` templates + provenance/export tests.

Tests:

- A valid artifact payload renders through the expected registry component.
- Unknown/invalid `kind` falls back to `text_fallback`.
- Source-derived private artifacts (any `user_upload` or non-public source) are excluded from public export; all-or-nothing gating holds.
- Concept-level artifacts are excluded from public export.
- The builder sub-agent stays within `tutor_tool_call_budget` and fails after one repair.
- A citation with no matching retrieved `source_revision_id` is dropped.
- Detached generation completes and persists after the SSE subscription is cancelled.

Acceptance criteria:

- CoLearni can generate, persist, retrieve, and safely render two read-only artifact templates without any code-execution or provenance risk.

Non-goals:

- No arbitrary React/JS artifact generation.
- No external sandbox requirement for V1 templates.
- No tutor-emitted artifacts yet (deferred to 15f).

### Phase 15b: Pin system

Implementation scope:

- A polymorphic `pins` table: `(workspace_id, trail_id, item_type, item_id, pinned_at)`, `item_type in {artifact, quiz_attempt}`. Pin/unpin endpoints + a "Saved/Pinned" surface aggregating artifacts and past quiz attempts, scoped per-Trail. Per-USER == per-workspace for now (becomes user-scoped when auth lands).

Requirements:

- Pins are workspace + Trail scoped and aggregate across supported item types.
- Pin/unpin is idempotent.

PR-sized breakdown:

- `pins` table + pin/unpin endpoints.
- Saved/Pinned aggregation surface.

Tests:

- Pinning/unpinning an artifact and a quiz attempt round-trips per-Trail.
- The Saved surface aggregates both item types scoped to the Trail.

Note: concept/source "pinning" as a PRIORITISATION signal (a retrieval/recommendation weight) is a DIFFERENT mechanism, deferred and scoped with the retrieval/gardener track (see Future Exploration / Backlog).

### Phase 15c: Flashcards subsystem (dedicated)

Flashcards are a DEDICATED subsystem, not a generic artifact.

Implementation scope:

- Storage: canonical JSON/relational (`flashcard_decks` + `flashcards`). CSV export is Anki-compatible export only, plus JSON export. CSV is an export format, NOT the source of truth.
- Card schema: `front`, `back`, `hint`, `source_ref`, `card_type (basic|cloze|reverse)` + scheduling state `{box, interval_days, last_reviewed, due, reps, lapses}`.
- Scheduling v1 = LEITNER (5–6 boxes, geometric intervals e.g. 1/3/7/16/35 days), recall-first swipe yes/no: yes => box+1 (capped), no => back to box 1 (`lapses++`). The schema is FSRS-ready (stores interval/lapses/last_reviewed) but v1 logic is Leitner. (FSRS is overkill for a binary swipe in v1.)
- Generation: source-grounded, atomic, dedup-aware. The generator RETURNS `{cards, exhausted: bool, reason}` so it can declare "no more useful cards" instead of padding garbage. Cap ~3–8 cards/concept; deck soft-cap. Bake card-writing rules into the prompt: one fact per card (minimum information / atomic); specific & unambiguous; no yes/no fronts; answer not inferable from the question; cloze for lists (one blank at a time); add why/how cards; self-contained with minimal context; source-grounded only (never invent); no duplicates of existing cards; STOP when facts are exhausted.
- Incremental extension: feed existing card FRONTS back as exclusion context + a deterministic embedding-similarity gate to drop paraphrase-duplicates. APPROVED: optionally use the learner's repeated-"no" (struggle) signal to bias new cards toward weak sub-areas (distinct from dedup).
- Pinnable + retrievable like quizzes.

Requirements:

- Canonical store is relational/JSON; CSV/JSON are export only.
- Generation is source-grounded and never invents facts; duplicates are dropped by the similarity gate.
- v1 scheduling is Leitner; the schema must remain FSRS-ready.

PR-sized breakdown:

- `flashcard_decks` + `flashcards` tables + schema.
- Leitner scheduler + recall-first swipe UI.
- Source-grounded generator with `{cards, exhausted, reason}` + dedup gate.
- Anki-compatible CSV + JSON export.
- Pin/retrieve integration.

Tests:

- A correct ("yes") swipe promotes the box; a wrong ("no") swipe resets to box 1 and increments `lapses`.
- Geometric intervals compute correctly per box.
- The generator returns `exhausted: true` rather than padding when facts run out.
- Paraphrase duplicates are dropped by the embedding-similarity gate.
- CSV export imports cleanly into Anki; JSON round-trips.

Pedagogy basis (for the future Pedagogy page): Wozniak "Twenty rules of formulating knowledge", Matuschak "How to write good prompts", Leitner/SM-2/FSRS, Bjork (testing effect, desirable difficulties, spacing, interleaving).

### Phase 15d: Remaining read-only templates

Implementation scope:

- `timeline` + `mini_graph` read-only templates. `mini_graph` reuses the Mermaid strict-mode / `@xyflow` rendering already used in the graph viewer.

Tests:

- `timeline` and `mini_graph` payloads render through the registry and degrade to `text_fallback` on invalid data.

### Phase 15e: Interactive "simulation slider" artifact

IN SCOPE for Phase 15 (per owner). Interactive but still trusted-template, never arbitrary code.

Implementation scope:

- Implemented as a CLOSED ENUM of trusted `sim_kind`s (e.g. `linear`, `quadratic`, `exponential`, `supply_demand`), each backed by a HARDCODED, vetted, unit-tested compute+render function in the frontend registry. The LLM only emits a validated data payload — the chosen `sim_kind` + named coefficients within validated finite ranges + axis labels + <=3 parameters + a predict-then-check `prompt` — NEVER code or a formula string.
- The BACKEND pre-computes baseline sample points and validates coefficient ranges (finite, no NaN, bounded `y`); it ships `precomputed.{at_defaults, y_bounds}` as a render hint + validation oracle. Client live-eval on slider drag uses the trusted hardcoded function, clamped to `y_bounds`, otherwise it degrades to the static plot / `text_fallback`.
- NO arbitrary JS, NO live mathjs in the browser. If arbitrary formulas are ever needed, the future path is a jsep-based whitelist interpreter on the BACKEND emitting sampled points (recorded as future, NOT v1 — see Future Exploration / Backlog).

Minimal schemas to add (field lists summarized here; full schema lives in API/contract docs later):

- `simulation_slider`: `sim_kind` (closed enum), named coefficients (validated finite ranges), axis labels, <=3 parameters, predict-then-check `prompt`, `precomputed.{at_defaults, y_bounds}`, `text_fallback`.
- `worked_example`: ordered steps, optional final answer, `source_refs`, `text_fallback`.
- `timeline`: ordered events (label + date/order + optional note), `source_refs`, `text_fallback`.
- `comparison_card`: compared items, criteria rows, per-cell values, `source_refs`, `text_fallback`.

Pedagogy to bake in: PhET implicit-scaffolding & direct-manipulation/immediate-feedback, the worked-example effect (Sweller), Mayer multimedia principles (contiguity, coherence, signaling, segmenting); pair each sim with a predict-then-check prompt.

Tests:

- An out-of-range/NaN coefficient is rejected by backend validation.
- Client live-eval matches the backend `precomputed` oracle within tolerance and clamps to `y_bounds`.
- An unknown `sim_kind` degrades to the static plot / `text_fallback`.

Non-goals:

- No arbitrary formula strings or browser-side math evaluation in v1.

### Phase 15f: Tutor integration (after Phase 14)

Implementation scope:

- The tutor emits a `suggest_artifact` / build request via the artifact-builder sub-agent tool.

Deferred deliberately so we don't stand up two new tutor-event mechanisms at once; sequenced AFTER Phase 14's `suggest_quiz`.

Acceptance criteria (Phase 15 overall):

- CoLearni can generate, persist, pin, retrieve, and safely render trusted read-only and interactive artifacts plus a dedicated flashcards subsystem, all without code-execution or provenance risk, with tutor-emitted artifacts wired only after Phase 14.


## Phase 16: Graph Gardener + Manual Graph Editing + Semantic Cluster Search

Goal: let learners grow and correct the concept graph safely — from ingested source dumps or by hand — with a human-approved changeset model, scoped subgraph context for small/local LLMs, and full reuse of the validation budgets in `docs/GRAPH.md`. The gardener never auto-applies; the learner accepts or rejects every change.

Status: design-locked, not yet implemented.

Implementation scope:

- **Semantic node-cluster search (FOUNDATIONAL — build first).** Embed concept nodes (pgvector already exists for source chunks), then vector-search the nearest nodes and expand by a 1-hop neighbourhood so only a SCOPED subgraph enters the prompt (the small/local-LLM enabler). This same search also serves entity-resolution / dedup against the existing graph.
- **Graph-mutation toolset** (none exists today — only concept-source linking exists): `add_node`, `add_edge`, `link_source`, `propose_merge` (+ optional `propose_split`). Validation reuses the rules in `docs/GRAPH.md`: reject duplicate slugs, reject edges to missing nodes, allow only known concept levels, detect prerequisite cycles, and enforce node-count caps. Every new node/edge must carry >=1 grounding source reference (no ungrounded nodes).
- **Changeset / approval model.** The gardener emits a PROPOSED changeset (ordered ops + rationale + source refs + a computed diff) for the learner to ACCEPT/REJECT; it NEVER auto-applies. On budget exhaustion it returns an explicit stop reason plus a valid partial changeset.
- **Source-dump auto-gardener.** Dump sources -> ingest (resolver: chunk->concept, budgets 3 LLM calls/chunk, 50/doc) -> gardener PROPOSES node/edge/link changes (budgets 30 LLM calls/run, 50 clusters/run, per `docs/GRAPH.md`) -> learner approves.
- **Doc-grounded Trail creation.** Create a Trail FROM ingested documents; the graph is derived from the sources' own structure / cross-references (and references between sources). The model may add structure ONLY when strictly necessary and should avoid unsupported structures. Add a "no orphan clusters" validation that flags unlinked nodes / disjoint subgraphs for review rather than silently emitting a disjoint forest.
- **Manual Trail/graph editing.** Add/rename/delete nodes & edges and edit concept fields, using the SAME apply/validate APIs the gardener uses. This manual surface is also the human-in-the-loop correction surface for the gardener.
- Wire all budgets from `docs/GRAPH.md` (chunk/doc resolver budgets, gardener per-run LLM-call and cluster caps, node-count caps).

Implementation scope ordering: cluster search lands first (it is the context enabler), then the mutation toolset + validation, then the changeset/approval model, then the source-dump auto-gardener and doc-grounded Trail creation, then the manual editing surface over the shared apply/validate APIs.

Requirements:

- No node or edge is ever applied without explicit learner approval of a changeset.
- Every new node/edge carries >=1 grounding source reference; ungrounded structure is rejected.
- All mutations pass `docs/GRAPH.md` validation (duplicate slugs, missing-node edges, known levels, prerequisite-cycle detection, node-count caps).
- All loops obey the `docs/GRAPH.md` resolver and gardener budgets; budget exhaustion yields an explicit stop reason + a valid partial changeset (no unbounded loops).
- Only scoped subgraphs (cluster search + 1-hop) enter prompts; the whole graph is never dumped into context.
- "No orphan clusters" validation flags disjoint subgraphs for review.
- Manual editing and gardener apply share the same validate/apply APIs.

PR-sized breakdown:

- Concept-node embeddings + semantic cluster search (vector NN + 1-hop expansion) + entity-resolution/dedup lookup.
- Graph-mutation toolset (`add_node`, `add_edge`, `link_source`, `propose_merge`, optional `propose_split`) + `docs/GRAPH.md` validation.
- Changeset/approval model (proposed ordered ops + diff + accept/reject + partial-on-exhaustion).
- Source-dump auto-gardener pipeline (ingest resolver budgets -> gardener run budgets -> proposed changes).
- Doc-grounded Trail creation + "no orphan clusters" validation.
- Manual graph-editing UI over the shared apply/validate APIs.

Tests:

- Cluster search returns a scoped subgraph (NN + 1-hop) and resolves an existing duplicate concept.
- `add_node`/`add_edge` reject duplicate slugs, edges to missing nodes, unknown levels, prerequisite cycles, and node-cap violations.
- An ungrounded node/edge (no source ref) is rejected.
- A gardener run that hits the LLM-call or cluster budget returns an explicit stop reason + a valid partial changeset.
- A proposed changeset is never applied without an explicit accept; reject discards it cleanly.
- A source dump produces proposed (not applied) node/edge/link changes within ingest + gardener budgets.
- Doc-grounded Trail creation flags orphan clusters / disjoint subgraphs for review.
- Manual edits go through the same validation as gardener-proposed edits.

Acceptance criteria:

- A learner can dump sources or create a Trail from documents, review a grounded, validated, budget-bounded proposed changeset, accept or reject it, and additionally edit the graph by hand through the same safe apply/validate path — with the whole-graph never entering a single prompt.

Non-goals:

- No auto-applied graph mutations.
- No ungrounded nodes/edges.
- No unbounded resolver/gardener loops or whole-graph prompting.
- Concept/source PRIORITY pinning as a retrieval/recommendation weight is out of scope here (see Future Exploration / Backlog).

## Phase 17: Demo Polish/User Testing

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
8. Export safe Trail Pack
9. Import/fork that Trail Pack into a new workspace
10. Optionally run research trace/hydration for the imported Trail
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

Tests:

- Demo path passes end-to-end.
- Generation jobs survive page refresh and can be polled.
- Import/export regression tests still pass after polish.
- Dark mode covers dashboard, Trail graph, tutor, quiz, and import/export screens.
- User-facing errors are readable for generation, tutor, quiz, import/export, ingestion, and retrieval failures.

Acceptance criteria:

- A new user can create a Trail in under one minute.
- They can click a concept and start learning immediately.
- The graph updates after mastery.
- Export/import works without private leakage.
- Refreshing the browser during Trail generation does not permanently lose the Trail.

Non-goals:

- No broad SaaS marketplace work in demo polish.
- No heavy gamification beyond small UX experiments validated by user testing.

## Phase 17.5: Safety + Content Guardrails

Goal: add layered content-safety defenses after the core learning loop works. The primary audience is adults and young adults learning intentionally, but the system must assume an unknown user who may be a minor, so it should be safe by default.

Sequencing note: this phase is deliberately placed after the core loop and demo polish so safety iteration does not inflate LLM token/test cost during earlier product iteration. Within the phase, the cheapest, highest-leverage control (trail-generation topic gating) lands first; per-turn runtime moderation and the child-safe default follow as separate steps. This phase must land before the product is exposed to real external users in Phase 18.

Layered scope (in build order):

1. Trail-generation topic gate (first, cheapest):
   - Classify the `topic`/`goal` at trail creation, before graph generation.
   - Refuse to generate Trails whose primary intent is disallowed (e.g. explicit sexual content, self-harm methods, weapons/explosives instructions, illicit drug synthesis).
   - Allow legitimate sensitive educational topics (e.g. sex education, history of conflict) but tag the Trail with a `sensitivity` flag that tightens downstream tutor behaviour.
   - One classification call; fail closed to a clear, non-judgmental refusal message.
   - Rationale: a learner in a C++ or Linear Algebra Trail has no in-scope path to unsafe content, so gating intent at creation removes most risk cheaply.

2. Tutor runtime scope + refusal (cheap; prompt + structural):
   - Reinforce that the tutor is bound to the current concept; off-topic unsafe requests are redirected back to learning, never fulfilled.
   - Provide a safe refusal/redirect template that never exposes internal policy.
   - Sensitivity-flagged Trails use stricter tutor instructions.

3. Runtime input/output moderation gate (deferred sub-step):
   - Moderate learner input and assistant output around the SSE stream in `backend/app/services/conversations.py`.
   - Use a provider/hosted moderation classifier kept model-agnostic (OpenRouter-hosted classifier, OpenAI moderation endpoint, or LlamaGuard).
   - On a hit: stop the stream, emit a safe refusal event, and log the event. No partial unsafe tokens are emitted.

4. Child-safe default mode (deferred sub-step):
   - Default to a safe profile that assumes a possibly-minor user.
   - A future adult/account-based mode (post-auth, Phase 19) may relax it.

5. Documentation + red-team tests:
   - Add `docs/SAFETY.md` capturing the policy, the layered design, and the disallowed/allowed-sensitive matrix.
   - Add a regression battery of red-team prompts that must refuse, mirroring the rigor of the export-safety tests.

Requirements:

- Safety controls must not depend on prompt instructions alone.
- Sensitive-but-educational topics are supported, not blanket-banned.
- Refusals are clear and suggest a safe next action.
- Moderation and classifier failures fail closed.
- Internal safety policy and gating logic are never revealed in learner-visible output.

PR-sized breakdown:

- Trail-generation topic gate + sensitivity flag + tests.
- Tutor scope/refusal prompt hardening + sensitivity plumbing.
- Runtime moderation gate (separate PR).
- Child-safe default + `docs/SAFETY.md` + red-team test battery.

Tests:

- A disallowed Trail topic is refused at generation.
- A legitimate sensitive topic generates but is sensitivity-flagged.
- The tutor redirects off-topic unsafe requests within an otherwise normal Trail.
- The moderation gate stops the stream and emits a safe refusal on flagged output.
- The red-team prompt battery refuses across tutor modes.

Acceptance criteria:

- A learner cannot easily drive the tutor into disallowed content, the system degrades safely under jailbreak attempts, and legitimate sensitive educational Trails still work.

Non-goals:

- No full SaaS moderation workflow or human review queue (Phase 19).
- No age verification or account-based mode switching before auth exists.

## Phase 17.6: Product / Marketing Site

Goal: a public-facing product/marketing site alongside the app, so prospective users understand what CoLearni is before they enter the workspace.

Implementation scope:

- Marketing routes in the existing Next.js frontend: Home, How it works, Pedagogy, Pricing, Contact.
- The Pedagogy tab tells the real teaching story: Bloom's Taxonomy as the target-depth dial, plus Socratic questioning, Bloom mastery learning, active recall/retrieval practice, and scaffolding along a prerequisite graph.
- Fake login: a login entry in the top-right header (and a centered call-to-action on Home, typical of consumer services) that reuses the existing localStorage workspace id. No real authentication yet; real auth lands in Phase 19.
- Pricing tab is explicitly TBC and marked as such. Anticipated tiers: a self-host / open-source tier, a free hosted tier, and a paid hosted tier. The exact free-vs-self-host boundary is undecided.
- Demos start as screenshots/GIFs; an embedded interactive demo can come later.

License note:

- The repository license is not finalized and is intentionally NOT MIT. The intended direction is source-available with a commercial starter advantage for the hosted service (e.g. a BSL/FSL-style or similarly restricted license). Do not assume or apply MIT, and do not document a specific license until it is chosen.

Requirements:

- Marketing pages are public and do not require a workspace.
- The fake login does not introduce real credential handling or secrets.
- Pricing copy clearly signals TBC rather than committing to numbers.
- The site is consistent with the app's theming (including dark mode from Phase 17).

PR-sized breakdown:

- Marketing route scaffolding + shared layout/nav.
- Home + How it works + Pedagogy content.
- Pricing (TBC) + Contact.
- Fake login entry wired to the existing localStorage workspace id.

Tests:

- Marketing routes render without a workspace.
- The fake login entry navigates into the app using the existing workspace id.
- Pages render in both light and dark themes.

Acceptance criteria:

- A first-time visitor can read what CoLearni is, how it teaches, and rough pricing intent, then enter the app through a familiar-looking login affordance.

Non-goals:

- No real authentication, accounts, or billing (Phase 19).
- No public pack marketplace.
- No committed pricing numbers or final license text.

## Phase 18: Deployment

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

## Phase 19: SaaS Prep

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

## Future Exploration / Backlog

CoLearni is a real product, not a throwaway. This section tracks penned-down ideas and known tech debt so they are prioritised, not lost. Items here are intentionally not yet scheduled into a numbered phase.

Product / pedagogy ideas:

- **Interleaved flashcard review across concepts within a Trail** — evidence-favored (Bjork interleaving); UI/UX still to be explored before committing to a review surface.
- **FSRS upgrade from Leitner** — swap the Phase 15c scheduler once graded ratings + real review history exist (the v1 schema is already FSRS-ready).
- **Concept/source PRIORITY pinning as a retrieval/recommendation weight** — a prioritisation signal that biases retrieval/recommendation, DISTINCT from the Phase 15b artifact/quiz pin (saved-items) system; scope with the retrieval/gardener track.
- **Struggle-aware generation generalized beyond flashcards** — reuse the repeated-"no"/struggle signal (first applied to flashcards in 15c) to bias quizzes, primers, and artifacts toward weak sub-areas.
- **Tutor-emitted artifacts (Phase 15f)** — wire the tutor to request artifact builds via the sub-agent tool once Phase 14's `suggest_quiz` mechanism has landed.
- **Inline artifacts/flashcards/quizzes in the tutor chat thread** — let the tutor trigger artifacts, flashcards, and quizzes that render INLINE within the chat thread (not only in their separate panels/tabs) and become part of the tutor chat context. Today these live in separate panels (`ArtifactsPanel`, `FlashcardsPanel`, `QuizPanel`) opened from the concept action row; the chat only emits a CTA that switches surfaces. Rationale: inline rendering keeps the learning moment in one flow and makes generated content part of the conversation the tutor reasons over. NOTE: significant chat-runtime change (new inline message-part kinds, context assembly, rehydration/replay, SSE ordering) — scope as its own phase later; NOT yet built. Related to but broader than 15f.
- **Multiple tutor chat threads per concept** — let a single concept support multiple distinct tutor conversations instead of the current one-thread-per-concept model. Threads share the same learner state and concept/mastery state but keep INDEPENDENT conversation context (messages + summary). Rationale: a single summarized context is sometimes insufficient; a learner may want a fresh thread (new angle, redo a topic) without losing per-concept progress. NOT yet built; needs a conversation-thread model + UI thread switcher and a decision on how learner-state observation aggregates across threads.
- **Reveal.js slide decks as a learning artifact** — explore generating reveal.js slide decks as another artifact type for learners. Explicitly FUTURE / LOW-PRIORITY: not to be built while current tech debt is being paid down. Recorded so the idea is not lost; revisit after the artifact subsystem and background-job debt settle.
- **Sandboxed jsep whitelist expression interpreter (backend)** — the future path for arbitrary-formula sims, emitting sampled points server-side; v2 only, never browser-side eval.

Tech debt (flagged in review; surface for prioritisation now that this is a real product):

- **P0 — Durable background-job queue** to replace detached `asyncio.create_task` work (primer generation, tutor follow-ups, and the new artifact builder). The current pattern silently loses in-flight work on restart/crash and breaks under multiple workers.
- **P0 — Tenant isolation**: workspace routes only check existence, not ownership, and `GET /api/workspaces` lists ALL workspaces. Add an auth principal + workspace-access dependency before any multi-user / SaaS exposure.
- **P0 — `EMBEDDING_DIM` has no migration path** and is read from two config sources (`os.environ` in the model vs `settings`); changing it corrupts the vector column.
- **P1 — pgvector ANN index** (hnsw/ivfflat) on `source_chunks.embedding` (currently a sequential scan).
- **P1 — Object-storage abstraction** (S3/GCS) to replace local-filesystem upload storage (won't survive multi-replica / ephemeral deploys; also a hardcoded `revisions/1/` object key).
- **P1 — Promote status/mode/type `str` columns** guarded only by CheckConstraints to Python `StrEnum`s (single source of truth); consider adopting a static type-checker (pyright/basedpyright) gate — the repo currently only runs ruff, so editor-surfaced type errors (e.g. `trail_pack_export.py` str-vs-Literal, test-double protocol mismatches) are ungated.
- **P1 — Quiz tables (`QuizAttempt`, `QuizDraft`) scoped only by `concept_id`**, not `workspace_id` — inconsistent with other workspace-scoped tables.
- **P2 — Broad `except Exception` swallows without logging** in several services (embedding fallback, primer cache read, DB health) — add structured logging/metrics.
