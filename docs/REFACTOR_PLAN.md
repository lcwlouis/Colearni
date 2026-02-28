# CoLearni Refactor Plan

Last updated: 2026-02-28

## Purpose

This document is the implementation plan for the post-fix refactor audit described in `docs/RUN_VERIFY_FIXES.md` section `G) Refactor and maintainability (NO behavior change)`.

This plan is intentionally concrete:

- it names the current hotspots
- it proposes exact module splits
- it sequences work into PR-sized slices
- it defines what must stay stable during each slice
- it lists verification gates so implementation does not drift

Use this document as the source of truth when the refactor begins. If implementation discovers a new constraint, update this file before widening scope.

## Inputs Used

This plan is based on:

- `docs/RUN_VERIFY_FIXES.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`
- current repository layout and test suite status as of 2026-02-28

## Executive Summary

The repository is not in rewrite territory. The architecture still has a valid backbone:

- backend separation into `apps/`, `domain/`, `adapters/`, and `core/`
- a reasonably complete automated test suite
- no detected `core -> apps` or `domain -> apps` import boundary violations

The refactor is justified because complexity has started to pool in a small number of files and because the documented patterns are only enforced inconsistently.

The biggest problems are:

1. Large orchestration modules own too many responsibilities.
2. Several API routes still contain SQL and business logic directly.
3. The web app has page-level components that own too much data loading, UI state, and behavior.
4. Global styling is too centralized in one file.
5. There are stale or duplicated surfaces that make the codebase harder to reason about.

The right move is an incremental refactor in small PRs, not a redesign.

## Non-Negotiable Constraints

These constraints apply to every refactor slice:

1. No intentional behavior change unless the slice is explicitly marked as a bug fix prerequisite.
2. Keep PRs small. Target `<= 400 LOC net` per PR wherever possible.
3. Preserve public API contracts and route paths during refactor.
4. Preserve current CSS class names unless the slice is explicitly the CSS split.
5. Add or update tests for every extracted behavior that gains a new module seam.
6. Keep FastAPI routes thin by the end of the route refactor slices.
7. Do not mix schema redesign with module moves in the same PR.
8. Prefer facade modules and staged re-exports while imports are being migrated.

## Current-State Findings

### Backend hotspots

Largest behavior-heavy backend files:

- `domain/learning/level_up.py`
- `adapters/db/graph_repository.py`
- `domain/learning/practice.py`
- `domain/chat/respond.py`
- `domain/graph/resolver.py`
- `domain/graph/explore.py`
- `core/ingestion.py`
- `core/schemas.py`

Observed issues:

- `domain/learning/level_up.py` combines quiz creation, generation retries, MCQ normalization, grading, mastery updates, observability, and payload shaping.
- `domain/learning/practice.py` partly duplicates level-up concerns and already aliases level-up exception classes, which is a strong sign that the current module boundary is wrong.
- `domain/chat/respond.py` builds retrievers, loads session context, resolves concepts, assembles evidence, chooses tutor behavior, verifies output, and persists the turn in one orchestration path.
- `adapters/db/graph_repository.py` is acting like several repositories merged into one file: concepts, edges, candidate lookup, merge logs, provenance, and gardener support.
- `core/ingestion.py` mixes ingestion validation, document dedup, chunk insertion, embedding population, summary generation, graph building, and background-task behavior.

### Route-layer drift

Routes that are relatively thin already:

- `apps/api/routes/chat.py`
- `apps/api/routes/practice.py`

Routes that still own too much SQL or workflow:

- `apps/api/routes/workspaces.py`
- `apps/api/routes/research.py`
- `apps/api/routes/knowledge_base.py`

Observed issues:

- direct `text(...)` SQL in route files
- route handlers assembling response objects themselves
- repeated transaction and error-handling patterns
- duplicate ingestion surfaces between `/documents/upload` and workspace-scoped KB upload

### Frontend hotspots

Main page/component hotspots:

- `apps/web/app/tutor/page.tsx`
- `apps/web/app/kb/page.tsx`
- `apps/web/app/graph/page.tsx`
- `apps/web/components/global-sidebar.tsx`
- `apps/web/components/concept-graph.tsx`
- `apps/web/app/globals.css`

Observed issues:

- `apps/web/app/tutor/page.tsx` owns session resolution, message loading, graph drawer state, quiz drawer state, onboarding state, concept switching, local storage, and submission flows.
- `apps/web/app/kb/page.tsx` owns document polling, queue state, upload execution, action confirmation, and status reconciliation.
- `apps/web/app/graph/page.tsx` owns concept search, full-graph loading, detail loading, lucky picks, practice state, stateful flashcards, and graph control state.
- `apps/web/components/global-sidebar.tsx` owns nav, session list, context menu, workspace creation, workspace rename, collapsed-mode behavior, and footer actions in one file.
- `apps/web/components/concept-graph.tsx` directly mixes rendering, D3 setup, zoom behavior, focus mode, search highlighting, and reset wiring.
- `apps/web/app/globals.css` is a monolith containing design tokens, shell, sidebar, tutor, KB, graph, cards, and state styles.

### Tooling and hygiene findings

Current verification status:

- `pytest -q`: passing
- `npm --prefix apps/web test`: passing
- `npm --prefix apps/web run typecheck`: failing

Current typecheck failures:

- `apps/web/app/tutor/page.tsx`: wrong argument passed to `onSubmitChat`
- `apps/web/components/concept-graph.tsx`: D3 selection typing issue on `.transition()`

Tracked generated or low-signal artifacts:

- `apps/web/tsconfig.tsbuildinfo`
- `colearni_backend.egg-info/PKG-INFO`
- `colearni_backend.egg-info/SOURCES.txt`

Likely stale or confusing surfaces:

- legacy upload route in `apps/api/routes/documents.py` while the web app uses only workspace-scoped KB routes
- stale `/practice` nav entry in `apps/web/components/global-sidebar.tsx`
- stale rename TODO in `apps/web/components/global-sidebar.tsx`

## Refactor Objectives

The refactor must achieve the following:

1. Make module ownership obvious.
2. Make API routes uniformly thin.
3. Reduce file size by splitting on behavior seams, not arbitrary line counts.
4. Preserve existing behavior and contracts while code moves.
5. Make future fixes in `RUN_VERIFY_FIXES` cheaper to implement.
6. Reduce duplicate ingestion and quiz logic.
7. Make frontend pages mostly container-level code.
8. Make CSS navigable and feature-scoped without restyling the app.

## Target Architecture After Refactor

### Backend target

Keep the current top-level layering, but split large feature modules inside each layer.

Target shape:

```text
apps/api/routes/
  chat.py
  practice.py
  quizzes.py
  workspaces.py
  research.py
  knowledge_base.py
  documents.py                # either removed later or narrowed to compatibility wrapper

apps/api/contracts/
  chat.py
  practice.py
  workspaces.py
  research.py
  knowledge_base.py

domain/chat/
  respond.py                  # thin facade/orchestrator only
  response_service.py
  retrieval_context.py
  evidence_builder.py
  social_turns.py
  session_memory.py
  sessions.py

domain/learning/
  level_up.py                 # public facade
  quiz_generation.py
  quiz_grading.py
  quiz_context.py
  quiz_persistence.py
  practice.py                 # public facade
  practice_flashcards.py
  practice_quizzes.py
  practice_novelty.py
  spaced_repetition.py

domain/knowledge_base/
  service.py
  status.py

domain/workspaces/
  service.py

domain/research/
  service.py
  runner.py

domain/ingestion/
  service.py
  document_status.py
  post_ingest.py

domain/graph/
  resolver.py                 # public facade
  resolver_candidates.py
  resolver_decision.py
  resolver_apply.py
  explore.py
  gardener.py

adapters/db/
  workspaces.py
  research.py
  knowledge_base.py
  documents.py
  chat.py
  graph/
    __init__.py
    concepts.py
    edges.py
    merge_map.py
    provenance.py
    candidates.py
    gardener.py

core/
  settings.py
  observability.py
  verifier.py
  schemas/
    __init__.py
    assistant.py
    chat.py
    graph.py
    knowledge_base.py
    practice.py
    quizzes.py
    research.py
    workspaces.py
```

Notes:

- Do not make this folder move all at once.
- Use facade modules first so imports can migrate gradually.
- `core/schemas.py` should become a package only after its imports are mapped and tested.

### Frontend target

Preserve `app/`, `components/`, and `lib/`, but introduce feature folders for page-owned behavior.

Target shape:

```text
apps/web/app/
  tutor/page.tsx              # container only
  graph/page.tsx              # container only
  kb/page.tsx                 # container only
  layout.tsx

apps/web/features/tutor/
  hooks/
    use-tutor-page.ts
    use-tutor-messages.ts
    use-level-up-flow.ts
  components/
    tutor-layout.tsx
    tutor-toolbar.tsx
    tutor-timeline.tsx
    tutor-graph-drawer.tsx
    tutor-quiz-drawer.tsx
    concept-switch-banner.tsx

apps/web/features/graph/
  hooks/
    use-graph-page.ts
    use-graph-practice.ts
  components/
    graph-controls.tsx
    graph-detail-panel.tsx
    graph-practice-panel.tsx

apps/web/features/kb/
  hooks/
    use-kb-documents.ts
    use-kb-upload-queue.ts
  components/
    kb-header.tsx
    kb-empty-state.tsx
    kb-table.tsx
    kb-row-actions.tsx

apps/web/features/sidebar/
  components/
    global-sidebar.tsx        # wrapper only
    sidebar-nav.tsx
    sidebar-sessions.tsx
    sidebar-workspaces.tsx
    sidebar-collapsed-controls.tsx

apps/web/components/
  concept-graph.tsx           # either stays generic or becomes a wrapper over a feature-local graph canvas
  level-up-card.tsx
  practice-quiz-card.tsx
  stateful-flashcard-list.tsx

apps/web/styles/
  tokens.css
  base.css
  shell.css
  sidebar.css
  tutor.css
  graph.css
  kb.css
  shared-components.css
```

## Implementation Sequencing

The work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### Slice 0: Baseline and Guardrails

Purpose:

- make the repository safe to refactor
- remove obvious noise that will confuse future diffs

Changes:

- fix current TS typecheck failures in:
  - `apps/web/app/tutor/page.tsx`
  - `apps/web/components/concept-graph.tsx`
- stop tracking generated artifacts:
  - `apps/web/tsconfig.tsbuildinfo`
  - `colearni_backend.egg-info/*`
- add or tighten `.gitignore` coverage if needed
- add a lightweight architecture test to prevent `core`/`domain` importing from `apps`

What stays the same:

- no route, API, or UI behavior changes

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`

Exit criteria:

- typecheck is green
- generated artifacts no longer create noise in routine diffs

### Slice 1: Schema Decomposition

Purpose:

- split `core/schemas.py` before adding more feature contracts

Files involved:

- create `core/schemas/` package
- migrate content out of `core/schemas.py`
- update imports across backend modules and tests

Exact split:

- `assistant.py`: `AssistantResponseEnvelope`, `AssistantDraft`, citations, evidence, grounding types
- `chat.py`: `ChatRespondRequest`, conversation metadata, chat payload models
- `graph.py`: graph concept and subgraph response models
- `knowledge_base.py`: KB list and summary models
- `practice.py`: flashcard and practice quiz payloads
- `quizzes.py`: level-up quiz create/submit payloads
- `research.py`: research source/run/candidate payloads
- `workspaces.py`: workspace request/response payloads

Migration rule:

- keep `core/schemas.py` temporarily as a compatibility facade that re-exports from the new package
- once all imports are updated and green, remove the facade in a later cleanup slice

What stays the same:

- import names
- payload shapes
- API docs

Verification:

- all current tests
- `tests/core/test_schemas.py`
- `tests/api/test_response_contracts.py`

Exit criteria:

- schema files are feature-scoped
- no payload contract changes

### Slice 2: Thin Routes Pass I - Workspaces and Research

Purpose:

- remove direct SQL from the simpler route files first

Files involved:

- create `adapters/db/workspaces.py`
- create `domain/workspaces/service.py`
- create `adapters/db/research.py`
- create `domain/research/service.py`
- slim:
  - `apps/api/routes/workspaces.py`
  - `apps/api/routes/research.py`

Moves:

- all SQL from workspace routes into adapter functions
- all multi-step workspace actions into domain service functions
- all SQL from research routes into adapter functions
- all response shaping and transaction handling into domain service functions

Route target shape:

- validate request
- call one service function
- translate domain errors to HTTP
- return response model

What stays the same:

- route paths
- request and response models
- auth and workspace guard behavior

Verification:

- `tests/api/test_auth.py`
- `tests/api/test_response_contracts.py`
- add targeted route/service tests for workspaces and research

Exit criteria:

- `apps/api/routes/workspaces.py` and `apps/api/routes/research.py` contain no direct SQL

### Slice 3: Thin Routes Pass II - Knowledge Base and Upload Surface Unification

Purpose:

- remove the most confusing route duplication in the repo

Files involved:

- create `adapters/db/knowledge_base.py`
- create `domain/knowledge_base/service.py`
- slim:
  - `apps/api/routes/knowledge_base.py`
  - `apps/api/routes/documents.py`

Required decisions:

1. Choose one canonical upload surface.
2. Keep the legacy surface only as a compatibility wrapper or remove it completely if no clients use it.

Recommended decision:

- keep workspace-scoped KB routes as canonical
- convert `apps/api/routes/documents.py` into:
  - a deprecated compatibility wrapper around the same service, or
  - a removed route if tests and docs confirm no active use

Moves:

- document listing query
- delete cascade logic
- reprocess validation
- upload request assembly
- background task scheduling helpers

What stays the same:

- KB UI behavior
- workspace-scoped route paths
- ingestion API contract for current frontend

Verification:

- `tests/api/test_documents_upload.py`
- `tests/db/test_document_ingestion_integration.py`
- `tests/api/test_response_contracts.py`

Exit criteria:

- only one real upload implementation exists
- route-level SQL is removed from KB handlers

### Slice 4: Ingestion Split

Purpose:

- isolate document ingestion workflow and status logic from `core/ingestion.py`

Files involved:

- create:
  - `domain/ingestion/service.py`
  - `domain/ingestion/post_ingest.py`
  - `domain/ingestion/document_status.py`
- slim `core/ingestion.py`

Exact split:

- `service.py`
  - request validation
  - document dedup flow
  - document insert and chunk insert orchestration
- `post_ingest.py`
  - embedding population
  - document summary generation
  - graph build invocation
- `document_status.py`
  - future home for persisted lifecycle state machine
  - central status transition helpers

Keep in `core/ingestion.py` only:

- public compatibility entrypoints
- exception classes
- thin wrapper functions calling the new domain services

Why now:

- `RUN_VERIFY_FIXES` already points to document lifecycle truthfulness and async ingestion as ongoing concerns
- the current file is both orchestration and implementation

Verification:

- `tests/core/test_ingestion_embeddings.py`
- `tests/db/test_document_ingestion_integration.py`
- `tests/core/test_ingestion_pdf.py`

Exit criteria:

- `core/ingestion.py` is a facade, not the implementation center

### Slice 5: Chat Orchestration Split

Purpose:

- reduce risk in `domain/chat/respond.py`

Files involved:

- create:
  - `domain/chat/response_service.py`
  - `domain/chat/retrieval_context.py`
  - `domain/chat/evidence_builder.py`
  - `domain/chat/social_turns.py`
- slim `domain/chat/respond.py`

Exact split:

- `social_turns.py`
  - social intent fast-path
  - social fallback generation
- `retrieval_context.py`
  - retriever construction
  - ranked chunk retrieval
  - concept-bias application
- `evidence_builder.py`
  - evidence conversion
  - citation assembly
  - related helper filters
- `response_service.py`
  - top-level orchestration for grounded tutor flow

Keep in `respond.py`:

- `generate_chat_response()` as a thin stable facade

What stays the same:

- chat route behavior
- verifier usage
- persistence shape
- observability fields

Verification:

- `tests/api/test_chat_respond.py`
- `tests/domain/test_tutor_agent.py`
- `tests/domain/test_prompt_kit.py`
- `tests/domain/test_chat_context_for_quiz.py`

Exit criteria:

- `generate_chat_response()` is orchestration only
- retriever creation and evidence shaping are no longer embedded inline

### Slice 6: Quiz and Practice Split

Purpose:

- separate reusable quiz primitives from feature-specific wrappers

Files involved:

- create:
  - `domain/learning/quiz_generation.py`
  - `domain/learning/quiz_grading.py`
  - `domain/learning/quiz_context.py`
  - `domain/learning/quiz_persistence.py`
  - `domain/learning/practice_flashcards.py`
  - `domain/learning/practice_quizzes.py`
  - `domain/learning/practice_novelty.py`
- slim:
  - `domain/learning/level_up.py`
  - `domain/learning/practice.py`

Exact split:

- shared generation helpers move out of `level_up.py`
- grading and mastery update logic move out of `level_up.py`
- practice quiz generation stops depending on `level_up.py` as an implicit internal library
- exception types become explicit shared quiz errors rather than aliases

Important rule:

- first create shared quiz modules and keep `level_up.py`/`practice.py` as facades
- only remove duplicated helpers after both flows are using the new shared modules

What stays the same:

- route contracts
- quiz payloads
- mastery behavior
- practice remains non-leveling

Verification:

- `tests/db/test_level_up_quiz_flow_integration.py`
- `tests/db/test_practice_flow_integration.py`
- `tests/domain/test_level_up_feedback_contract.py`
- `tests/domain/test_spaced_repetition.py`

Exit criteria:

- practice no longer depends on level-up through aliased exceptions and hidden helper reuse

### Slice 7: Graph Repository Split

Purpose:

- make graph data access navigable and safer to modify

Files involved:

- create `adapters/db/graph/` package
- split `adapters/db/graph_repository.py` into:
  - `concepts.py`
  - `edges.py`
  - `merge_map.py`
  - `provenance.py`
  - `candidates.py`
  - `gardener.py`
- keep `adapters/db/graph_repository.py` as a re-export facade until imports are migrated

Then split domain resolver helpers:

- `domain/graph/resolver_candidates.py`
- `domain/graph/resolver_decision.py`
- `domain/graph/resolver_apply.py`

What stays the same:

- `domain/graph/resolver.py` public behavior
- `domain/graph/gardener.py` public behavior
- graph tables and migrations

Verification:

- `tests/domain/test_graph_resolver.py`
- `tests/db/test_graph_resolver_integration.py`
- `tests/domain/test_graph_gardener.py`
- `tests/db/test_graph_gardener_integration.py`

Exit criteria:

- graph data access is split by concern
- resolver and gardener imports remain stable through a facade layer

### Slice 8: Tutor Page Split

Purpose:

- make the tutor page maintainable without changing UX

Files involved:

- create `apps/web/features/tutor/`
- move behavior from `apps/web/app/tutor/page.tsx` into:
  - `hooks/use-tutor-page.ts`
  - `hooks/use-tutor-messages.ts`
  - `hooks/use-level-up-flow.ts`
  - `components/tutor-layout.tsx`
  - `components/tutor-timeline.tsx`
  - `components/tutor-graph-drawer.tsx`
  - `components/tutor-quiz-drawer.tsx`
  - `components/concept-switch-banner.tsx`

Container target:

- `app/tutor/page.tsx` should mostly:
  - get auth context
  - invoke one page hook
  - render feature components

What stays the same:

- URL behavior
- local storage persistence semantics
- active chat session behavior
- level-up UX

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual tutor smoke test

Exit criteria:

- `apps/web/app/tutor/page.tsx` becomes a container, not a behavior monolith

### Slice 9: Graph Page, KB Page, and Sidebar Split

Purpose:

- finish the major frontend decomposition

Files involved:

- `apps/web/features/graph/`
- `apps/web/features/kb/`
- `apps/web/features/sidebar/`
- slim:
  - `apps/web/app/graph/page.tsx`
  - `apps/web/app/kb/page.tsx`
  - `apps/web/components/global-sidebar.tsx`

Exact split:

- Graph:
  - page data and UI control state into hooks
  - detail/practice/control panels into separate components
- KB:
  - polling and upload queue logic into hooks
  - document table and row actions into components
- Sidebar:
  - nav rail
  - recent sessions
  - workspace actions
  - collapsed footer controls

Cleanup to do during this slice:

- remove stale `/practice` nav entry unless a real page is being added
- remove stale rename TODO once split confirms the behavior already persists correctly

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual checks for tutor, graph, KB, and sidebar flows

Exit criteria:

- the three largest frontend containers are feature-composed rather than single-file implementations

### Slice 10: CSS Decomposition

Purpose:

- reduce `apps/web/app/globals.css` without changing styling behavior

Files involved:

- create:
  - `apps/web/styles/tokens.css`
  - `apps/web/styles/base.css`
  - `apps/web/styles/shell.css`
  - `apps/web/styles/sidebar.css`
  - `apps/web/styles/tutor.css`
  - `apps/web/styles/graph.css`
  - `apps/web/styles/kb.css`
  - `apps/web/styles/shared-components.css`
- slim `apps/web/app/globals.css`
- update `apps/web/app/layout.tsx` imports if needed

Rules:

- do not rename existing classes in the first CSS split
- first move blocks intact
- only consolidate duplicates after files are separated and visual regression has been checked

What stays the same:

- selectors
- visual design
- DOM structure

Verification:

- manual visual pass on tutor, graph, KB, login, sidebar
- `npm --prefix apps/web run typecheck`

Exit criteria:

- `globals.css` becomes a thin aggregator or minimal shell file

### Slice 11: Cleanup and Facade Removal

Purpose:

- remove compatibility layers only after all slices above are green

Targets:

- remove `core/schemas.py` facade if no longer needed
- remove `adapters/db/graph_repository.py` facade if no longer needed
- remove legacy upload route if confirmed unused
- delete dead imports and stale types
- remove redundant helpers discovered during earlier slices

Verification:

- full backend and frontend test suite
- API smoke pass

Exit criteria:

- no duplicate implementation paths remain

## Risks and How to Control Them

### Risk 1: Refactor accidentally changes API behavior

Mitigation:

- route refactors must preserve exact request and response models
- keep handlers thin but behaviorally identical
- run `tests/api/test_response_contracts.py` after every route slice

### Risk 2: Shared quiz extraction breaks grading or mastery

Mitigation:

- extract generation and grading separately
- keep `level_up.py` facade stable
- verify with integration tests before deleting old helpers

### Risk 3: Frontend split causes state reset regressions

Mitigation:

- move one state cluster at a time
- preserve URL, local storage keys, and reducer interfaces
- keep page-level integration manual checks after each frontend slice

### Risk 4: CSS split creates subtle layout regressions

Mitigation:

- move CSS by feature block, not selector-by-selector
- no class renames in the first pass
- visual smoke test every page before merge

### Risk 5: Facade modules become permanent debt

Mitigation:

- every facade added in a slice must have a removal target in Slice 11
- track removal explicitly in PR descriptions

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
```

Run these additionally when relevant:

```bash
ruff check .
```

Manual smoke checklist:

1. Tutor page loads, sends a message, reloads an existing session, and opens/closes graph and quiz drawers.
2. Graph page loads full graph, selects a concept, runs lucky pick, opens practice quiz and flashcards.
3. Sources page uploads, refreshes, deletes, and reprocesses documents.
4. Sidebar supports collapse/expand, session switch, session rename, and workspace switching.

## What Not To Do

Do not do the following during the refactor:

- do not introduce a new state management library
- do not switch to a CSS framework as part of this plan
- do not move to LangChain as part of this refactor
- do not redesign public API paths
- do not combine status-machine feature work with pure module moves unless the slice is explicitly a prerequisite bug fix

## Deliverables

At the end of the full refactor plan execution, the repo should have:

1. Thin API routes across all workspace-scoped endpoints.
2. Feature-scoped schema modules instead of one large `core/schemas.py`.
3. Quiz, practice, ingestion, and graph logic split along behavior seams.
4. Page-container frontend architecture for tutor, graph, KB, and sidebar.
5. Feature-scoped CSS files with `globals.css` reduced to a minimal entrypoint.
6. Removed duplicate or stale surfaces that currently confuse maintenance.

## Tracking During Implementation

When implementation starts, also maintain `docs/REFACTOR.md` as the running audit log required by `docs/RUN_VERIFY_FIXES.md`.

Use this file, `docs/REFACTOR_PLAN.md`, as the stable roadmap and use `docs/REFACTOR.md` as the live execution journal.
