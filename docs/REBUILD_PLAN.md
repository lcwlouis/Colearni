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

MVP spine:

```text
Create Trail
-> Learn concept
-> Level-up quiz
-> Graph mastery update
-> Safe Trail Pack export
-> Trail Pack import/fork
-> Optional research trace/hydration
```

Dashboard, Learn/Inspect graph UX, source ingestion, retrieval tools, provider-native tools, and future visualisers improve this Trail experience. They must not replace or outrank safe Trail sharing/import in the MVP.

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
10. Trail Pack import + research trace/hydration MVP
11. Provider tool abstraction foundation
12. Learning dashboard + Learn/Inspect graph UX
13. Source ingestion MVP
14. Retrieval + context tooling
15. Guided graph navigation / recommended next concept
16. Conversation summaries + learner state
17. Tutor-suggested quiz cards
18. Deferred visualiser / artifact templates
19. Demo polish/user testing
20. Deployment
21. SaaS prep

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

Last updated: 2026-05-25.

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
- Learning dashboard home with Continue Learning, recent/older Trail sections, delete confirmation, per-Trail progress summaries, and a deterministic frontend recommended-next helper.
- Per-Trail graph Learn/Inspect mode split with `?concept=<id>` deep-link opening, neighbourhood focus in Learn Mode, inspect-only graph controls and edge-label toggle, mastery-aware concept-panel CTAs, and mobile concept sheet refinement.
- Source ingestion foundation: workspace-scoped private upload API, local private object storage root, source revision records with immutable identity fields and mutable parser status/error metadata, concept-source linking API, minimal concept-panel upload/link UI, and export/import safety regressions for revision artifacts.

Not implemented yet:

- True per-message citation/source parts and quote support.
- Automatic conversation summarisation and full provider-native tool execution loops beyond the current tutor compatibility adapter.
- Automated research-agent search, real hydration fetching/indexing, durable generation jobs, dark mode, deployment, auth, and SaaS features.
- Parsing into canonical text, chunks, embeddings/indexes, controlled retrieval tools, guided graph navigation beyond the current frontend recommendation helper, conversation summaries, mutable learner state, tutor-suggested quiz cards, and artifact templates.

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
- `/generate/stream` remains documented as a temporary progress-stream endpoint until Phase 16 durable jobs are implemented.
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

Status: implemented for the current MVP slice, including tutor-side mastery updates, mixed-format quizzes, backend quiz drafts with `force_new`, duplicate-request hardening, per-question grading feedback, practice retry behavior, and mastery-gated tutor direct/free-explore modes.

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

Goal: make safe Trail sharing a core MVP capability, not a later polish item.

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

## Phase 7: Trail Pack Import + Research Trace/Hydration MVP

Goal: let learners fork shared Trails and optionally make them locally useful without sharing copyrighted or private content.

Implementation scope:

- Add `POST /api/workspaces/{workspace_id}/trail-packs/import`.
- For V1, import by forking into the current workspace.
- Validate manifest, graph, concepts, sources, and research trace before persistence.
- Current slice adds `GET /api/workspaces/{workspace_id}/trails/{trail_id}/research` for imported trace retrieval. Automated `POST /research` is deferred until real search/provider-tool support exists.
- Store search queries, selected public links, source types, license/access status, selection reasons, and excluded source notes.
- Add `POST /api/workspaces/{workspace_id}/trails/{trail_id}/hydrate` as a narrow MVP that creates private hydration placeholder records from allowed public links and/or model-knowledge intent. It does not fetch, chunk, embed, or index content yet.

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
- Hydration MVP and export-regression tests.

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
- No broad file ingestion beyond the hydration MVP.

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

- Home now computes per-Trail progress and the Continue Learning / recommended-next card client-side from Trail detail records using deterministic mastery/graph heuristics.
- Learn Mode is the default graph surface with simplified controls and selected-neighbourhood focus; Inspect Mode preserves filters/layout/legend plus the edge-label toggle, and `?concept=<id>` opens the concept sheet directly.

## Phase 10: Source Ingestion MVP

Status: foundation slice and concept-source linking implemented. Parser pipeline, chunks, embeddings, and full-text indexes remain deferred.

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

Status: retrieval service and tool definitions implemented.
LLM tool calling loop, open_source_chunk, and full-text/vector search remain deferred.

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

## Phase 14: Tutor-Suggested Quiz Cards

Goal: let the tutor suggest an appropriate quiz card without inline-generating or grading it.

Event/tool flow:

```text
tutor emits suggest_quiz(concept_id, quiz_type, reason)
-> frontend shows quiz CTA/card
-> backend-owned quiz draft system generates/reuses the card
```

Implementation scope:

- Add a provider-tool or event-style `suggest_quiz` output through the tool abstraction.
- Show a learner-safe quiz suggestion card in the tutor UI.
- Reuse the backend-owned `quiz_drafts` system for generation and persistence.
- Keep grading and mastery updates in the existing quiz services.

Requirements:

- The tutor cannot mark mastery directly.
- Suggested quiz cards must not include private/source-derived content unless the backend quiz system explicitly allows it under current safety rules.
- Duplicate suggestions must reuse or focus the same draft rather than spawning competing cards.
- Suggestions include a short learner-visible reason.

PR-sized breakdown:

- Tool/event contract and backend validation.
- Frontend CTA/card rendering.
- Draft reuse integration.
- Tutor prompt/tool tests.

Tests:

- `suggest_quiz` creates a frontend-visible CTA without grading.
- Clicking the CTA reuses existing backend draft when present.
- Tutor cannot update mastery through the suggestion event.
- Duplicate suggestion events dedupe safely.
- Suggestion reason is persisted or included in the client event as appropriate.

Acceptance criteria:

- The tutor can nudge learners toward level-up or practice at the right moment while the backend remains the owner of quiz cards and mastery.

Non-goals:

- No inline tutor-generated quiz that bypasses quiz drafts.
- No tutor-owned mastery decisions.

## Phase 15: Deferred Visualiser / Artifact Templates

Goal: add helpful learning artifacts later using trusted templates, not arbitrary LLM-generated JavaScript.

Trusted templates:

- Comparison card.
- Timeline.
- Flashcards.
- Mini graph.
- Simulation slider.
- Worked example.

Implementation scope:

- Define an artifact payload schema and frontend component registry.
- Let services emit structured artifacts only from approved templates.
- Add export/privacy rules for artifacts derived from private or uploaded sources.
- Start with read-only artifacts before interactive stateful artifacts.

Requirements:

- No arbitrary LLM-generated JavaScript as the default artifact path.
- Artifacts inherit source provenance restrictions.
- Artifact rendering failures degrade to readable text.

PR-sized breakdown:

- Artifact schema and renderer registry.
- One or two trusted templates.
- Provenance/export tests.
- Tutor/source integration later.

Tests:

- Valid artifact payload renders through the expected component.
- Unknown artifact type falls back safely.
- Source-derived private artifacts are excluded from public export.
- No raw script execution is allowed.

Acceptance criteria:

- CoLearni can show richer learning aids without creating a code-execution or provenance risk.

Non-goals:

- No arbitrary React/JS artifact generation.
- No external sandbox requirement for V1 templates.

## Phase 16: Demo Polish/User Testing

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

## Phase 17: Deployment

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

## Phase 18: SaaS Prep

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
