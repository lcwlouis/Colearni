# WOW Release - Implementation Progress

> Last updated: Session 14

## Slice Status Overview

| Slice | Status | Notes |
|-------|--------|-------|
| S1 Auth + magic link | Done | Logout wired, redirects to /login |
| S2 Workspace CRUD + guard | Done | Membership guards on all routes |
| S3 UUID API cutover | Done | All API endpoints use UUID `public_id` in paths; frontend uses `string` workspace IDs |
| S4 Route auth + namespacing | Done | All workspace-scoped routes under `/workspaces/{ws_id}/...`; `WorkspaceContext` dependency handles auth + UUID resolution |
| S5 Login + workspace UI | Done | Auth on all pages, workspace switcher in nav, auto-create default workspace |
| S6 KB Explorer + Upload | Done | Upload endpoint + UI, list, delete, reprocess |
| S7 Assessment cards | Done | persist + load in session_memory |
| S8 Tutor context upgrade | Done | build_full_tutor_prompt wired into respond |
| S9 Readiness + CTA | Done | Half-life decay, cadence tiers, CTA actions |
| S10 Stateful flashcards | Done | Rating UI with Again/Hard/Good/Easy |
| S11 Novelty engine | Done | Fingerprint dedup on flashcards AND quizzes |
| S12 Research agent | Done | httpx fetch, HTML extraction, ingestion pipeline |
| S13 Prompt kit + persona | Done | Social hides citations, CTA buttons render |
| S14 Eval suite | Not Started | Separate PR scope |
| S15 KB ingestion + graph status UI | Done | Per-document `ingestion_status`, `graph_status`, `graph_concept_count` shown in KB |
| S16 KB confirmation + upload UX | Done | Removed browser popups; inline confirms; explicit `Choose file` + `Upload document` flow |
| S17 Header control layout stabilization | Done | Workspace/theme/logout moved out of top-right and into tutor sidebar bottom controls |
| S18 Model temperature env controls | Done | Added `APP_GRAPH_LLM_JSON_TEMPERATURE` and `APP_GRAPH_LLM_TUTOR_TEMPERATURE` |
| S19 Async ingestion lifecycle persistence | Not Started | Verified: lifecycle is still inferred from chunk count; no persisted document lifecycle field yet |
| S20 Graph ingestion SDK migration + schema hardening | Done | Schemas fixed for OpenAI strict mode; providers migrated to `openai`/`litellm` SDKs; graph errors surfaced as controlled 502s |
| S21 KB live upload queue + multi-file uploads | Done | KB now keeps in-page queue (`queued/uploading/uploaded/failed`) and supports uploading multiple files in one batch |
| S22 App Shell & Sidebar Redesign | Done | Moved page nav to global sidebar, standardized KB/Graph padding, implemented workspace Create/Rename |
| S23 Unified Graph & Practice UX | Done | Collapse Practice into Graph, default to full graph, stateful flashcards, arrows/weights |
| S24 Tutor Context Expansion & Quiz Grading UI | Done | Persistent practice quizzes, adjust grading UI for >= 0.7 scores, native UUID generation loops |
| S25 Layout & Tutor Graph Context | Done | Limit Tutor graph bounds (2 hops/mastery only), uncouple search filter, fix KB margins |
| S26 Document Summaries & Deletion Fixes | Done | Generate ingest summaries, show in KB table, pass to Tutor RAG context, fix DELETE endpoint |
| S27 UUID Navigation & Dashboard Widgets | Done | Migrate session IDs to UUIDs, persist Practice scores on screen minimised |
| S28 Sidebar & Layout Polish | Done | Sidebar overflow, context menu, profile, chat scroll, graph padding |
| S29 Graph & Knowledge Explorer Polish | Done | Suggestion randomization, weight normalization, tutor graph description |
| S30 Quiz Generation Quality & Statefulness | Done | Improved auto_items with concept-specific MCQs, randomized choices, better LLM prompt, auto-start new quiz |
| S31 Onboarding Flow | Done (via S38) | Backend onboarding status API done; frontend onboarding card with topic chips in tutor page |
| S32 Robustness & Testing | Done | Migration + major tests done; session CRUD round-trip tests added (10 new tests) |
| S33 Tutor UI Layout & Drawer Polish | Done | Code block frame polish, adaptive drawer width, close animations, sidebar collapse, footer clipping |
| S34 Quiz Lifecycle Automation & Concept Grounding | Done | Quiz status retrieval, mastered-neighbor context, tutor quiz context injection, quiz gardener job |
| S35 Scalable Graph Experience (LightRAG-Informed) | Done | Backend truncation signals, frontend node/edge limit controls, truncation messaging, adaptive graph rendering |
| S36 Documentation Integrity | Done | Comprehensive PROMPTS.md with 14 prompt catalog, flow diagrams, orchestration map |
| S37 Test Debt & Mock Infrastructure Cleanup | Done | Fixed all 12 pre-existing test failures, _FakeSession stubs, API docs sync, env cleanup |
| S38 Onboarding Flow | Done | Backend: `domain/onboarding/status.py`, topic suggestions endpoint. Frontend: onboarding card, topic chips, API client integration |
| S39 Spaced Repetition Foundation | Done | SM-2 scheduler (Again/Hard/Good/Easy multipliers), due flashcards endpoint, migration |
| S40 Quiz Gardener Operability & Testing | Done | Fixed build_engine→create_db_engine, 5 unit tests, Makefile targets |
| S45 (Urgent) Reasoning Controls + Full Context Envelope Integrity | Done | 4 reasoning control settings, flashcard progress in tutor context, labeled history sections |
| S41 Tutor Continuity, Context Memory, and Naming Reliability | Done | Auto session title gen, quiz history context injection, chat-aware quiz prompts. Frontend: composer anchoring, sidebar inline delete confirmation |
| S42 Markdown Rendering, Sidebar Footer Fit, and Collapsed Sidebar Quality | Done | Code block overflow-y:auto, sidebar footer no nested scroll, collapsed sidebar rail with CSS tooltips |
| S43 Graph UX Density + LightRAG-Informed Adaptation (Native) | Done | Responsive graph canvas (ResizeObserver), search/focus mode with highlight rings, neighbor-aware dimming |
| S44 Document Deletion vs Graph Retention Policy + Implementation | Done | Orphan pruner domain service, `prune_orphan_graph` query param on DELETE endpoint, 9 unit tests |

## Session 4 Changes

### S3 UUID API Cutover (Completed)
- `WorkspaceContext` dataclass in `apps/api/dependencies.py` resolves UUID path param → internal ID, verifies membership
- All workspace-scoped routes accept `{ws_id}` (UUID string) instead of numeric IDs
- Frontend `activeWorkspaceId` changed from `number` to `string`, uses `public_id`
- Frontend `client.ts` — all methods take `wsId: string` first param, URLs namespaced
- Frontend `types.ts` — removed `workspace_id`/`user_id` from 8 request interfaces
- All pages updated: tutor, graph, practice, kb

### S4 Route Namespacing (Completed)
- All workspace-scoped routes nested under `/workspaces/{ws_id}/...`
- Chat: `/workspaces/{ws_id}/chat/sessions`, `/workspaces/{ws_id}/chat/respond`
- Graph: `/workspaces/{ws_id}/graph/concepts`, `/workspaces/{ws_id}/graph/lucky`
- Practice: `/workspaces/{ws_id}/practice/flashcards`, `/workspaces/{ws_id}/practice/quizzes`
- Quizzes: `/workspaces/{ws_id}/quizzes/level-up`, `/workspaces/{ws_id}/quizzes/{id}/submit`
- KB: `/workspaces/{ws_id}/knowledge-base/documents`
- Research: `/workspaces/{ws_id}/research/sources`, runs, candidates
- Readiness: `/workspaces/{ws_id}/readiness/snapshot`
- Workspaces create/list stay at `/workspaces`

### Bug Fixes
- Migration 0004: Fixed `sa.false_()` → `sa.False_()` (SQLAlchemy 2.x API, 4 instances)
- Redirect-drops-auth: Set `redirect_slashes=False` on FastAPI app; workspace routes use no trailing slash
- Empty workspace chat: New onboarding fast-path guides users to upload documents instead of returning a confusing refusal
- Auto workspace creation: Auth context auto-creates "My Workspace" when user has none
- Missing `description` column: Added `description TEXT` to workspaces table (DB + migration 0004)
- Missing `owner_user_id` in INSERT: `create_workspace` now includes `owner_user_id` (NOT NULL column)

### Test Updates
- All Python tests updated for workspace-scoped routes
- Integration tests (`test_graph_exploration`, `test_level_up_quiz_flow`, `test_practice_flow`) fully rewritten:
  - Auth override via `get_current_user` dependency
  - `workspace_members` rows created in fixtures
  - All routes use `/workspaces/{public_id}/...` paths
  - Request bodies no longer contain `workspace_id`/`user_id`
- All frontend tests updated for new API signatures (37 pass)
- TypeScript clean (0 errors)
- `docs/API.md` updated with all new route paths

### All API Endpoints Verified (curl end-to-end)
- `POST /auth/magic-link` → 200
- `POST /auth/verify` → 200
- `GET /workspaces` → 200
- `POST /workspaces` → 201
- `GET /workspaces/{uuid}` → 200
- `POST /workspaces/{uuid}/chat/sessions` → 201
- `POST /workspaces/{uuid}/chat/respond` → 200 (social + onboarding modes)
- `GET /workspaces/{uuid}/knowledge-base/documents` → 200
- `GET /workspaces/{uuid}/graph/concepts` → 200
- `GET /workspaces/{uuid}/readiness/snapshot` → 200
- `GET /workspaces/{uuid}/research/sources` → 200

## Deferred to Future PRs

- S14: Eval suite (golden-answer datasets + prompt regression harness)

## Session 5 Changes

### Plan + Scope Updates
- Added Session 5 UX + operability requirements to `docs/PLAN.md`:
  - KB ingestion/graph status visibility in file list
  - No browser popups for reprocess/delete confirmations
  - Header control overflow fix (move workspace/theme/logout out of top-right)
  - Env-level temperature controls for different graph LLM cases

### Knowledge Base UX Improvements (Implemented)
- KB upload flow now uses explicit two-step actions:
  - `Choose file` selects local file
  - `Upload document` submits selected file
- Added upload result banner showing chunk count for immediate ingestion confirmation.
- Replaced popup confirmations (`confirm`/`alert`) with inline confirm controls and in-page status banners.
- KB table upgraded with operational status columns:
  - `ingestion_status` badge (`pending`/`ingested`)
  - `graph_status` badge (`disabled`/`pending`/`extracted`)
  - `graph_concept_count`

### Backend KB Status Contract (Implemented)
- `GET /workspaces/{ws_id}/knowledge-base/documents` now returns per-document:
  - `ingestion_status`
  - `graph_status`
  - `graph_concept_count`
- Status derivation is workspace-scoped and consistent with current sync ingestion flow.

### Layout Improvement (Implemented)
- Top-right header no longer carries workspace/theme/logout controls.
- Primary nav remains in topbar.
- Workspace selector, theme toggle, and logout moved into tutor sidebar bottom profile/settings area.

### Model Temperature Env Controls (Implemented)
- Added settings + wiring for:
  - `APP_GRAPH_LLM_JSON_TEMPERATURE`
  - `APP_GRAPH_LLM_TUTOR_TEMPERATURE`
- Temperatures are now configurable via `.env` and propagated through LLM factory/providers.

### Script Hygiene
- `tmp/rewrite_routes.py` is not present in workspace and is not needed after route migration completion.

## Test Results

- Python: 228 passed, 0 failed (1 pre-existing `test_settings_reads_observability_aliases` deselected)
- Frontend (vitest): 37 passed, 0 failed
- TypeScript: Clean (no errors)

## Remaining Incremental Work

- S19 remains pending:
  - Persist document lifecycle state on `documents` (`queued`/`processing`/`ingested`/`failed`) instead of deriving from `chunk_count`.
  - Implement real async reprocess execution path (current route still returns queued ack only).
- S20 remains pending:
  - Migrate graph LLM adapter to SDK-backed providers.
  - Fix strict JSON schema request shape used for graph extraction/disambiguation.
  - Add regression tests to prevent reintroduction of OpenAI `response_format` schema errors.

## Session 6 Verification + Updates

### WOW_PROGRESS Verification Corrections
- Re-verified current codebase state before updating this doc:
  - `apps/api/routes/knowledge_base.py` still derives KB `ingestion_status` from `chunk_count` and does not read persisted lifecycle states.
  - No document lifecycle persistence fields (`queued`/`processing`/`ingested`/`failed`) are present in current app-level ingestion path.
  - Reprocess endpoint still returns a queued acknowledgement stub.
- Corrected S19 status from `In Progress` to `Not Started` to match real implementation state.

### New KB Upload UX Improvements (Implemented)
- `apps/web/app/kb/page.tsx`
  - Added multiple file selection (`<input multiple>`).
  - Added sequential batch upload execution with per-file status tracking.
  - Added visible in-page upload queue showing `queued`, `uploading`, `uploaded`, `failed`.
- `apps/web/lib/kb/upload-queue.ts` + `apps/web/lib/kb/upload-queue.test.ts`
  - Added reducer/state helpers for upload queue behavior and unit tests.
- `apps/web/app/globals.css`
  - Added styling for upload queue and failure badge.

### Session 6 Validation Run
- Frontend typecheck: `npx tsc --noEmit` (pass)
- Frontend tests: `npx vitest run` (pass; now 41 tests total)

## Session 7 Changes

### S20 Graph Ingestion SDK Migration + Schema Hardening (Implemented)

#### Schema Fixes
- `adapters/llm/providers.py`
  - `_RAW_GRAPH_SCHEMA`: Added full `items` definitions for `concepts` and `edges` arrays, matching the domain-layer Pydantic models. This was the root cause of the OpenAI 400 error when `APP_INGEST_BUILD_GRAPH=true`.
  - `_DISAMBIGUATION_SCHEMA`: Made optional fields nullable (`["type", "null"]`), added all properties to `required` list for strict-mode compliance.

#### SDK Migration
- `adapters/llm/providers.py`
  - `OpenAIGraphLLMClient` now uses the official `openai.OpenAI` SDK client instead of hand-rolled `urllib`.
  - `LiteLLMGraphLLMClient` now uses `litellm.completion()` instead of raw HTTP requests.
  - Common `_BaseGraphLLMClient` ABC handles observability (spans, events, token tracking).
  - `GraphLLMClient` protocol interface unchanged — domain/core layers unaffected.
- `pyproject.toml`
  - Added `openai>=1.30.0,<3.0.0` to project dependencies.

#### Error Handling Hardening
- `core/ingestion.py`
  - Added `IngestionGraphProviderError(RuntimeError)` exception class.
  - `build_graph_for_chunks()` call wrapped in try/except: `RuntimeError` → `IngestionGraphProviderError`.
- `apps/api/routes/knowledge_base.py` + `apps/api/routes/documents.py`
  - Catch `IngestionGraphProviderError` → HTTP 502 (controlled error, no raw 500 traceback leaks).

#### Test Updates
- `tests/adapters/test_graph_llm_schemas.py` (NEW)
  - 6 regression tests validating OpenAI strict-mode schema compliance and payload round-trips.
- `tests/adapters/test_graph_llm_observability.py`
  - Updated to mock `litellm.completion` instead of `urllib.urlopen`.
- `tests/api/test_documents_upload.py`
  - Added test for graph provider failure → 502 response.
- `tests/core/test_wow_schemas.py`
  - Fixed pre-existing `TestKBDocumentSummary` test (missing S15 status fields).

### Session 7 Validation Run
- Backend: 229 passed, 0 failed (1 pre-existing `test_settings_reads_observability_aliases` deselected)
- Frontend typecheck: `npx tsc --noEmit` (pass)
- Frontend tests: vitest blocked by pre-existing macOS EPERM sandbox issue on temp dirs (no frontend files changed)

### Remaining Incremental Work
- S19 remains pending:
  - Persist document lifecycle state on `documents` (`queued`/`processing`/`ingested`/`failed`).
  - Implement real async reprocess execution path.

## Session 8 Changes

### S22 App Shell & Sidebar Redesign (Implemented)
- **Global Sidebar Architecture**: 
  - Created `GlobalSidebar` component to replace the old top navigation bar.
  - Hosted 'Recent Chats' fetching and selection in the sidebar to decouple it from `TutorPage`.
  - Moved User Profile, Theme toggle, and Workspace Selector to the bottom of the sidebar.
- **Workspace Management UI**:
  - Added frontend forms and backend API endpoint (`PATCH /workspaces/{id}`) for creating and renaming workspaces.
  - Added instantaneous visual switching mechanism.
- **Page Standardization**:
  - Updated `kb/page.tsx`, `graph/page.tsx`, and `practice/page.tsx` structural wrappers to fit within the new `layout.tsx` flex row sidebar format (`height: 100%`, `overflowY: "auto"`).
  - Resolved the duplicate "Choose files" button on the KB page.
- **Verification**: Verified using automated browser QA for rendering, click behaviors, and workspace flow operations.

## Session 9 Changes

### S25 Layout & Tutor Graph Context (Implemented)
- **Tutor Graph Filter**: `apps/web/app/tutor/page.tsx` — Sidebar graph drawer now limited to 2 hops + mastery-only concepts via `max_hops=2&mastery_only=true` query params.
- **Graph Search Layout**: `apps/web/app/graph/page.tsx` — Search input decoupled from the concept graph card into a standalone page header.
- **KB Margins**: `apps/web/app/globals.css` — Fixed right-margin and padding inconsistencies on KB table flex containers.

### S26 Document Summaries & Deletion Fixes (Implemented)
- **DB Migration**: `adapters/db/migrations/versions/20260227_0005_document_summary.py` — Added `summary TEXT` column to `documents` table.
- **Document Helpers**: `adapters/db/documents.py` — `DocumentRow` includes `summary` field; added `update_document_summary()` function.
- **Ingestion Summarization**: `core/ingestion.py` — Added `_generate_document_summary()` that takes first 5 chunks (≤3000 chars), calls LLM for 2-3 sentence summary, stores via `update_document_summary()`.
- **Tutor RAG Context**: `domain/chat/respond.py` — `_build_document_summaries_context()` extracts unique doc IDs from ranked chunks, loads documents, builds summary context string. `domain/chat/prompt_kit.py` — `build_system_prompt()` and `build_full_tutor_prompt()` accept `document_summaries` parameter and insert DOCUMENT SUMMARIES section into the system prompt.
- **KB Schema & Route**: `core/schemas.py` — `KBDocumentSummary` has `summary: str | None = None`. `apps/api/routes/knowledge_base.py` — List query SELECTs and maps `d.summary`.
- **KB UI**: `apps/web/lib/api/types.ts` — `KBDocumentSummary.summary` field. `apps/web/app/kb/page.tsx` — Conditional summary display below document title. `apps/web/app/globals.css` — `.kb-doc-summary` styles.
- **DELETE Cascade Fix**: `apps/api/routes/knowledge_base.py` — DELETE endpoint now cascade-deletes `edges_raw` and `concepts_raw` rows before provenance/chunks/documents, preventing FK constraint violations.

### S27 UUID Navigation & Dashboard Widgets (Implemented)
- **Backend UUID Session Routes**:
  - `adapters/db/chat.py` — `create_chat_session()` returns `public_id` in RETURNING clause. `list_chat_sessions()` SELECTs `s.public_id`. Added `resolve_session_by_public_id()` helper (UUID → internal int lookup).
  - `apps/api/routes/chat.py` — Session path params changed from `int` to `str`. All handlers resolve UUID via `resolve_session_by_public_id()` before domain calls. `ChatRespondAPIRequest.session_id` changed to `str | None`.
  - `apps/api/routes/quizzes.py` — `CreateLevelUpQuizRequest.session_id` changed to `str | None` with UUID resolution.
  - `apps/api/routes/practice.py` — `CreateQuizRequest.session_id` changed to `str | None` with UUID resolution.
  - `core/schemas.py` — `ChatSessionSummary.public_id: str = Field(min_length=1)`.
- **Frontend UUID Navigation**:
  - `apps/web/lib/api/types.ts` — `ChatSessionSummary.public_id`, session ID params changed to `string`.
  - `apps/web/lib/api/client.ts` — `getChatMessages()` and `deleteChatSession()` changed `sessionId: number` to `string`.
  - `apps/web/lib/tutor/chat-session-context.tsx` — Full rewrite: all session IDs use `string` (UUID). URL syncing uses `?chat=UUID`. `startNewSession()` returns `string | null`.
  - `apps/web/components/global-sidebar.tsx` — Session references changed from `session_id` (number) to `public_id` (string UUID) for keying, active checks, hrefs, and context menus.
  - `apps/web/app/tutor/page.tsx` — `ensureSession()` and `loadMessages()` updated for string session IDs.
- **Stateful Practice Widgets**:
  - `apps/web/components/practice-quiz-card.tsx` — Added minimize/expand state for submitted quiz cards. Compact summary shows score percentage, passed/failed coloring, and Expand/Next Quiz/Close buttons.
  - `apps/web/app/globals.css` — `.practice-minimized`, `.practice-minimized-row`, `.practice-minimized-score` (`.passed`/`.failed`), `.practice-minimized-label` styles.

### Test Updates
- `apps/web/lib/api/client.test.ts` — Updated `deleteChatSession` test to use string UUID.
- `tests/api/test_response_contracts.py` — Added `public_id` to `REQUIRED_FIELDS["ChatSessionSummary"]`, updated mock data with `public_id`, patched `resolve_session_by_public_id`, updated URL paths to use UUID strings.

### Session 9 Validation Run
- Frontend typecheck: `npx tsc --noEmit` — 0 errors
- Frontend tests: `npx vitest run` — 41/41 passed
- Backend tests: Pre-existing failures only (5 `_FakeSession` mock issues in `test_ingestion_embeddings.py`, 2 `test_api_docs_sync`/`test_response_contracts` schema mismatches)

## Session 10 Changes

### S28 Sidebar & Layout Polish (Implemented)
- **Sidebar overflow fix**: `.session-list` gets `flex: 1; min-height: 0; overflow-y: auto` for proper scroll containment.
- **Context menu fix**: `.session-context-menu` changed from `position: absolute` to `position: fixed; z-index: 100`. `global-sidebar.tsx` captures screen coordinates on right-click (`clientX`/`clientY`) and renders context menu at fixed position.
- **Profile block fix**: Sidebar profile uses `flexDirection: "row"` with `gap: 0.5rem`, email truncated with `minWidth: 0`, logout button fixed at `2rem × 2rem`.
- **Chat scroll fix**: `.chat-text` gets `overflow-wrap: break-word; word-break: break-word`. `.chat-content` gets `overflow: hidden`. `.markdown-content pre` gets `max-width: 100%`.
- **Graph page spacing**: `.graph-explorer > div` gets `gap: 1.5rem`. `.graph-detail-panel` and `.graph-viz-panel` get `margin: 0.5rem; padding: 1.5rem`.

### S29 Graph & Knowledge Explorer Polish (Implemented)
- **Suggestion randomization**: `domain/graph/explore.py` — `_pick_adjacent()` and `_pick_wildcard()` now `LIMIT 5` + `random.choice(candidates)` instead of deterministic `LIMIT 1`.
- **Graph weight normalization**: `adapters/llm/providers.py` schema changed weight to `"type": "integer"`. `domain/graph/extraction.py` — `_EdgePayload.weight` accepts float, clamped to `min(99, max(1, int(...)))` for `ExtractedEdge`. `domain/graph/types.py` — `ExtractedEdge.weight` changed to `int = 1`.
- **Tutor graph description**: `apps/web/app/tutor/page.tsx` — Graph drawer legend now shows concept description (truncated 200 chars) with muted styling.

### S30 Quiz Generation Quality & Statefulness (Implemented)
- **Fixed `_supports_quiz_generation`**: Now checks for both `extract_raw_graph` (full LLM client signal) AND `generate_tutor_text`.
- **Improved LLM quiz prompt**: Richer instructions with concept name, description, related concepts, progressive difficulty, specific MCQ requirements.
- **Rebuilt `_auto_items` fallback**: Short answer templates are shuffled each time. New `_build_auto_mcq_items()` generates concept-specific MCQ choices from description/keywords instead of generic placeholders. Choices are randomized so correct answer isn't always "a". Critical choice IDs validated to never equal correct answer.
- **Auto-start new quiz**: "Start new quiz" button now dispatches reset + auto-triggers `startLevelUp()` instead of requiring two clicks.

### Test Updates
- `tests/db/test_graph_exploration_integration.py` — Updated lucky pick assertions for randomized top-5 selection.
- `tests/db/test_level_up_quiz_flow_integration.py` — Added `_correct_mcq_answers()` and `_wrong_mcq_answers()` helpers for dynamic MCQ answer building (choices are no longer deterministically ordered).
- `tests/domain/test_graph_extraction.py` — Updated edge weight assertion from `1.2` to `1` (int clamping).

### Session 10 Validation Run
- Frontend typecheck: `npx tsc --noEmit` — 0 errors
- Frontend tests: `npx vitest run` — 41/41 passed
- Backend tests: All pass except pre-existing failures (test_api_docs_sync, test_response_contracts, test_ingestion_embeddings, test_document_ingestion_integration)

## Session 11 Planning Audit

### Verified State Before New Plan Expansion
- **Quiz auto-generation cron**: no in-app scheduler/job currently creates level-up quizzes on topic introduction. Existing background job is readiness analysis only (`apps/jobs/readiness_analyzer.py`).
- **Quiz attachment model**: level-up quizzes are already persisted with both `concept_id` and optional `session_id` in `quizzes`, so concept-level attachment exists today.
- **Tutor queryability gap**: tutor flow does not yet have an explicit concept-scoped quiz summary retrieval path baked into response composition, so this remains planned work.
- **S32 reconciliation**:
  - Completed: summary migration applied + major quiz/graph integration test coverage added.
  - Remaining: legacy API-doc/contract + ingestion test debt and additional integration scenarios (chat-doc lookup, sidebar CRUD, KB delete cascade).

## Session 11 Changes

### S33 Tutor UI Layout & Drawer Polish (Implemented)
- **Code block frame styling**: `apps/web/app/globals.css` — `.markdown-content pre` now has `border: 1px solid var(--line)`, `border-radius: var(--radius)`, `box-shadow: var(--shadow-sm)` for consistent framing.
- **Drawer adaptive width**: Right drawers (graph/quiz) use `clamp(20rem, 25vw, 32rem)` instead of fixed width, expanding on wider screens.
- **Close animations**: Added `@keyframes slideOutRight` animation. New `closingDrawer` state in `apps/web/app/tutor/page.tsx` drives `.closing` class on drawer `<aside>` elements with 240ms exit animation before state clear.
- **Sidebar collapse**: Added `collapsed` state to `apps/web/components/global-sidebar.tsx` with chevron toggle button. CSS `.global-sidebar.collapsed` hides nav/chat/profile content, shrinks width to `3.5rem`.
- **Footer clipping fix**: Sidebar footer gets `flex-shrink: 0; max-height: 40vh; overflow-y: auto`.
- **Files modified**: `apps/web/app/globals.css`, `apps/web/app/tutor/page.tsx`, `apps/web/components/global-sidebar.tsx`.

### S34 Quiz Lifecycle Automation & Concept Grounding (Implemented)
- **Quiz status retrieval**: Added `get_latest_quiz_summary_for_concept()` in `domain/learning/level_up.py` — queries latest quiz attempt (score, passed, created_at) for a concept/workspace/user.
- **Mastered-neighbor context**: Added `get_mastered_neighbor_context()` in `domain/learning/level_up.py` — returns top-K mastered neighboring concepts by edge weight for inclusion in quiz generation prompt.
- **Generation context enrichment**: Enhanced `_generation_context()` in `domain/learning/level_up.py` to fetch up to 3 document chunk excerpts (300 chars each) for richer quiz generation. Updated LLM prompt with `SOURCE MATERIAL EXCERPTS` block.
- **Tutor quiz context injection**: Added `_build_quiz_context()` to `domain/chat/respond.py` — builds formatted quiz status string for active concept. `_generate_tutor_text()` now accepts `quiz_context` parameter and merges into `combined_assessment` before calling `build_full_tutor_prompt`.
- **Quiz gardener job**: Created `apps/jobs/quiz_gardener.py` — background job that auto-generates level-up quizzes for concepts in 'learning' status without existing quizzes. Processes up to `MAX_CONCEPTS_PER_RUN=20` per invocation.
- **Files modified**: `domain/learning/level_up.py`, `domain/chat/respond.py`.
- **Files created**: `apps/jobs/quiz_gardener.py`.

### S35 Scalable Graph Experience (Implemented)
- **Backend truncation signals**: Added `is_truncated: bool` and `total_concept_count: int | None` to `GraphSubgraphResponse` in `core/schemas.py`. Updated `get_full_subgraph()` in `domain/graph/explore.py` to count total concepts and return truncation info when node count exceeds limit.
- **Frontend graph controls**: Added `maxNodes`/`maxEdges` state variables to `apps/web/app/graph/page.tsx`. Added select dropdowns (50/100/200/500/1000 nodes, 100/300/600/1000/2000 edges) in graph header. `useEffect` passes limits to `apiClient.getFullGraph()` call and re-fetches when changed.
- **Truncation banner**: When `fullGraph.is_truncated` is true, displays "Showing X of Y concepts (graph truncated)" banner.
- **Adaptive graph rendering**: Updated `apps/web/components/concept-graph.tsx` with size-aware optimizations:
  - Adaptive force parameters: reduced charge/distance/collide for large (>200 nodes) and huge (>500 nodes) graphs.
  - Edge weight labels hidden for large graphs; node labels hidden for huge graphs.
  - Adaptive node/selection radii and font sizes by graph size.
  - Shorter simulation timeout for large graphs (1500–2000ms vs 3000ms).
  - Alpha decay increased for large graphs to reach equilibrium faster.
- **CSS**: Added `.graph-controls`, `.graph-control-label`, `.graph-truncation-banner` styles.
- **Files modified**: `core/schemas.py`, `domain/graph/explore.py`, `apps/web/lib/api/types.ts`, `apps/web/app/graph/page.tsx`, `apps/web/components/concept-graph.tsx`, `apps/web/app/globals.css`.

### S36 Documentation Integrity (Implemented)
- **PROMPTS.md**: Rewrote `docs/PROMPTS.md` as comprehensive source-of-truth catalog of all 14 LLM prompts across the codebase. Includes per-prompt tables (file, function, purpose, inputs, output format), prompt flow diagram, and orchestration file map.

### Session 11 Validation Run
- Frontend typecheck: `npx tsc --noEmit` — 0 errors
- Frontend tests: `npx vitest run` — 41/41 passed
- Backend tests (domain + adapters): 95/95 passed, 0 failed
- Backend tests (full suite): 11 pre-existing failures (unchanged from Session 10):
  - `test_api_docs_sync` (1): API.md heading drift
  - `test_response_contracts` (1): Schema required-fields mismatch
  - `test_ingestion_embeddings` (5): `_FakeSession` lacks `.execute()` + env-dependent `ingest_build_graph`
  - `test_settings` (1): Observability alias env mismatch
  - `test_document_ingestion_integration` (3): Missing graph LLM client mock + `generate_tutor_text` stub
- No new test failures introduced by Session 11 changes.

### Session 12 Planning
- Added 5 slices to `docs/PLAN.md` (with urgent execution order):
  - **S45 (Urgent)**: Reasoning Controls + Full Context Envelope Integrity (toggleable reasoning by task + Phoenix-verified prompt context completeness)
  - **S37**: Test Debt & Mock Infrastructure Cleanup (fix all 11 pre-existing failures)
  - **S38**: Onboarding Flow (topic suggestions, onboarding card, tutor prompt path)
  - **S39**: Spaced Repetition Foundation (SM-2 scheduler, due flashcards, interval tracking)
  - **S40**: Quiz Gardener Operability & Testing (unit tests, Makefile target, docs)

### New Planning Tracks Added
- Added Session 11 slices in `docs/PLAN.md`: `S33` (UI layout/drawer polish), `S34` (quiz lifecycle automation + concept grounding), `S35` (LightRAG-informed graph scalability), `S36` (documentation integrity including prompt catalog).
- Clarified `S35` scope to external comparative analysis only: LightRAG is treated as a separate repo reference, and Colearni implementation remains native (no direct dependency/porting of LightRAG internals).

## Session 12 Changes

### S45 Reasoning Controls + Full Context Envelope Integrity (Implemented)
- **Reasoning control settings**: Added 4 toggleable settings in `core/settings.py`:
  - `llm_reasoning_chat` (default True), `llm_reasoning_quiz_grading` (default True)
  - `llm_reasoning_graph_generation` (default False), `llm_reasoning_quiz_generation` (default False)
  - Each with `APP_` and unprefixed `AliasChoices` for env-based configuration.
- **Session memory upgrade**: Enhanced `load_history_text()` in `domain/chat/session_memory.py` with labeled "COMPACTED PRIOR CONTEXT" / "RECENT CHAT HISTORY" sections.
- **Flashcard progress context**: Added `load_flashcard_progress()` to session_memory.py, wired through `respond.py` and `prompt_kit.py` with concept-scoped progress snapshot.
- **Prompt kit updates**: Renamed section headers ("TOPIC ASSESSMENT HISTORY"), added `flashcard_progress` parameter through build functions.

### S37 Test Debt & Mock Infrastructure Cleanup (Implemented)
- Fixed all 12 pre-existing test failures (from 201 passing to 233 passing):
  - `test_ingestion_embeddings.py`: Added `_FakeSession.execute()` stubs, `_StubGraphLLM.generate_tutor_text` method, pinned `ingest_build_graph=False`.
  - `test_settings.py`: Fixed `delenv` for competing observability aliases.
  - `test_response_contracts.py`: Corrected `GraphSubgraphResponse` required fields (`workspace_id`, `nodes`, `edges`), added `graph/full` and `onboarding` routes to `OPENAPI_ROUTES`.
  - `test_graph_resolver_integration.py`: Added `generate_tutor_text` to `IntegrationGraphLLM`.
  - `test_level_up_quiz_flow_integration.py`: Set `graph_llm_provider="mock"` in `_client_without_llm`.
  - `test_practice_flow_integration.py`: Fixed `_answers` to use actual `item["choices"][0]["id"]`.
  - `test_prompt_kit.py`: Updated assertions for renamed section headers.
  - `test_document_ingestion_integration.py`: Pass settings with `ingest_build_graph=False`.
  - `docs/API.md`: Added missing headings (PATCH workspaces, GET graph/full).

### S38 Onboarding Flow (Implemented)
- **Domain logic**: Created `domain/onboarding/status.py` with `suggest_starting_topics()` (top-N concepts by graph degree) and `get_onboarding_status()` (has_documents, has_active_concepts, suggested_topics).
- **API endpoint**: `GET /workspaces/{ws_id}/onboarding/status` returning `OnboardingStatusResponse`.
- **Schemas**: Added `OnboardingSuggestedTopic` and `OnboardingStatusResponse` to `core/schemas.py`.
- **Tests**: 5 unit tests in `tests/domain/test_onboarding.py`.
- **Files created**: `domain/onboarding/__init__.py`, `domain/onboarding/status.py`, `apps/api/routes/onboarding.py`.

### S39 Spaced Repetition Foundation (Implemented)
- **Migration**: `20260228_0006_spaced_repetition.py` adds `interval_days FLOAT NOT NULL DEFAULT 1.0` to `practice_flashcard_progress`.
- **SM-2 scheduler**: `domain/learning/spaced_repetition.py` with `compute_next_review()` (multipliers: Again 0.5×, Hard 1.0×, Good 2.5×, Easy 4.0×, minimum 0.25 days).
- **Wiring**: `rate_flashcard()` in `practice.py` now calls `update_flashcard_schedule()`, returns `interval_days` and `due_at`.
- **Due flashcards**: `get_due_flashcards(session, workspace_id, user_id, limit)` query + `GET /workspaces/{ws_id}/practice/flashcards/due` endpoint.
- **Tests**: 8 unit tests in `tests/domain/test_spaced_repetition.py`.

### S40 Quiz Gardener Operability & Testing (Implemented)
- **Bug fix**: `apps/jobs/quiz_gardener.py` — Fixed `build_engine` → `create_db_engine` import/call.
- **Unit tests**: 5 tests in `tests/jobs/test_quiz_gardener.py` with mocked DB.
- **Makefile**: Added `quiz-gardener` and `graph-gardener` targets.

### Session 12 Validation Run
- Python tests: **233 passed, 0 failed** (up from 201 passing + 12 failing)
- All Session 12 slices (S45, S37, S38, S39, S40) complete and verified.

## Session 13 Changes

### S41 Tutor Continuity, Context Memory, and Naming Reliability (Backend Implemented)
- **Auto session title generation**: Created `domain/chat/title_gen.py` with `generate_session_title(user_query, concept_name=None)` — regex-based prefix stripping (removes "can you explain", "what is", etc.), title-casing, 2–5 word clamping, concept_name priority when available.
- **Title wiring**: Updated `persist_turn()` in `session_memory.py` to accept `concept_name` parameter; `respond.py` passes resolved concept's `canonical_name`.
- **Chat-history-informed quiz generation**: Added `load_chat_context_for_quiz()` to `session_memory.py` — loads condensed recent exchanges (Learner/Tutor labeled, 200-char truncation per message, max 8 turns).
- **Quiz prompt injection**: Wired chat history through `_choose_items` → `_generate_level_up_items_with_retries` in `level_up.py`; added `CHAT_HISTORY_CONTEXT` block to quiz generation prompt so quizzes target areas the learner discussed or struggled with.
- **Tests**: 9 tests in `tests/domain/test_title_gen.py`, 7 tests in `tests/domain/test_chat_context_for_quiz.py`.
- **Frontend parts deferred**: Composer bottom anchoring, sidebar delete confirmation remain frontend-only scope.

### S42 Markdown Rendering (Deferred — Frontend Only)
- Requires CSS/layout work in Next.js frontend. Documented in plan; no backend changes needed.

### S43 Graph UX Density (Deferred — Frontend Only)
- Requires responsive visualization changes in Next.js frontend. Documented in plan; no backend changes needed.

### S44 Document Deletion vs Graph Retention Policy (Implemented)
- **Orphan pruner**: Created `domain/graph/orphan_pruner.py` with `find_orphan_concept_ids()`, `find_orphan_edge_ids()`, and `prune_orphan_graph_nodes()` — removes canonical concepts/edges with zero remaining provenance rows, cascading edge cleanup before concept removal, mastery row cleanup.
- **API**: Added `prune_orphan_graph` query parameter (default `false`) to `DELETE /workspaces/{ws_id}/knowledge-base/documents/{document_id}`. When true, runs orphan pruning after document deletion.
- **API.md**: Updated delete endpoint contract with new query parameter.
- **Tests**: 9 unit tests in `tests/domain/test_orphan_pruner.py`.

### Session 13 Validation Run
- Python tests: **258 passed, 0 failed** (up from 233 in Session 12)
- All backend-implementable Session 13 slices (S41 backend, S44) complete and verified.

### Session 14 Planning
- Added 5 new slices to `docs/PLAN.md` (S46–S50), drawing from SUGGESTIONS.md:
  - **S46**: Learning Path Generator — topological concept ordering by mastery + prerequisites (S4 foundation)
  - **S47**: Concept Strength Analytics & Weakness Detection — aggregate per-concept strength score (S2 foundation)
  - **S48**: Graph Curation: Duplicate Detection & Merge — alias/similarity-based dedup (S1 foundation)
  - **S49**: Spaced Repetition Review Session Orchestrator — batched due-card sessions with stats
  - **S50**: Mastery Decay Alerts & Tutor Proactive Nudges — first-message decay warnings

## Session 13.5 Changes (Bug Fix & Tech Debt)

### Root Cause: Chat 500 Error (`InFailedSqlTransaction`)
- **Symptom**: `POST /workspaces/{uuid}/chat/respond` returned 500 with `psycopg.errors.InFailedSqlTransaction`
- **Root cause**: `load_flashcard_progress()` in `session_memory.py` used wrong column names (`fp.rating`, `fp.is_passed`, `fp.created_at`), causing SQL failure. The bare `except Exception: return ""` swallowed the error but left SQLAlchemy session in a poisoned transaction state. All subsequent queries on the same session then failed.
- **Fix**: Corrected columns to `fp.self_rating`, `fp.passed`, `fp.updated_at` (matching migration 0004 schema)

### Safe Rollback Pattern (7 locations)
Added `if callable(getattr(session, "rollback", None)): session.rollback()` in all try/except blocks that touch SQL:
- `domain/chat/session_memory.py` — `load_flashcard_progress`
- `domain/chat/respond.py` — `build_readiness_actions`, `_workspace_has_no_chunks`, `_build_quiz_context`
- `domain/learning/practice.py` — `_record_item_fingerprints`, `rate_flashcard`
- `apps/jobs/quiz_gardener.py` — quiz generation loop
- `apps/jobs/readiness_analyzer.py` — readiness analysis loop
- `domain/research/runner.py` — `ingest_approved_candidates` error path

### Column/Schema Mismatches Fixed
- `domain/readiness/analyzer.py`: `m.mastery_score` → `m.score AS mastery_score` (mastery table column is `score`)
- `domain/research/runner.py`: Removed references to nonexistent `content_hash` and `source_id` columns on `workspace_research_candidates`; now uses `run_id` and `source_url` for dedup
- `domain/research/runner.py`: Changed `status = 'failed'` to `'rejected'` (check constraint only allows `pending/approved/rejected/ingested`)
- `domain/research/runner.py`: Added `session.commit()` after failed-candidate status update

### Import Fix
- `apps/jobs/readiness_analyzer.py`: `build_engine` → `create_db_engine` (function doesn't exist, was always broken)

### Session 13.5 Validation Run
- Python tests: **283 passed, 0 failed** (up from 258 in Session 13)
- All identified critical/high bugs from comprehensive SQL audit resolved

## Session 14 Changes (Frontend Completion + Tests)

### S41 Frontend (Completed)
- **Composer anchoring**: Replaced competing grid/inline-flex layouts on `.chat-main` with a single flex-column layout. Timeline gets `flex: 1`, composer dock gets `flex-shrink: 0`.
- **Sidebar delete confirmation**: Wired the already-declared `deleteConfirmId` state to show an inline "Delete? [Yes] [No]" bar instead of immediate deletion.

### S42 Frontend (Completed)
- **Code block clipping**: Changed `.markdown-content pre` from `overflow-y: hidden` to `overflow-y: auto` with `max-height: 36rem`.
- **Sidebar footer scroll**: Removed `max-height: 40vh; overflow-y: auto` from `.sidebar-footer`.
- **Collapsed sidebar rail**: Added CSS tooltips via `::after` pseudo-element with `content: attr(title)`, hover effects, icon sizing, hidden non-essential elements. Added `title` attributes to nav Links.

### S43 Frontend (Completed)
- **Responsive graph canvas**: Added `ResizeObserver` in `ConceptGraph` component with container ref, removed hardcoded 700×500 dimensions.
- **Graph search/focus**: Added `searchHighlight` prop with yellow `#eab308` ring rendering and `focusNodeId` prop with neighbor-aware dimming (`opacity: 0.2` for non-focused nodes).
- **Graph page**: Added "Highlight node..." search input and "Clear focus" button in graph header.

### S38 Frontend — Onboarding Card (Completed)
- Added `OnboardingSuggestedTopic` and `OnboardingStatusResponse` types to `apps/web/lib/api/types.ts`.
- Added `getOnboardingStatus(wsId)` method to API client.
- Added onboarding card in tutor page: shows when timeline is empty and workspace has documents with suggested topics. Renders topic chips that populate the query input and set concept context.
- Added CSS for `.onboarding-card`, `.onboarding-chips`, `.onboarding-chip` with hover effects.

### S32 — Session CRUD Tests (Completed)
- New test file: `tests/api/test_session_crud.py` with 10 tests covering:
  - Create returns 201 with public_id
  - Create without title returns null title
  - List returns created sessions
  - List respects limit
  - Delete returns 204
  - Delete then messages returns 404
  - Delete nonexistent returns 404
  - Deleted session disappears from list
  - Empty session returns empty messages
  - Messages for nonexistent session returns 404
- Uses in-memory store with monkeypatched route-level imports.

### Session 14 Validation Run
- Python tests: **293 passed, 0 failed** (up from 283 in Session 13.5)
- Frontend tests (vitest): **41 passed, 0 failed**
- TypeScript: Clean (0 errors)

### Session 15 — Run-Verify Fixes

#### C1 — Upload/Async Ingestion (Completed)
- Root cause: `upload_kb_document` in `knowledge_base.py` called `ingest_text_document()` which runs embeddings, summary, and graph extraction synchronously — blocking the HTTP request for 10–60s.
- Fix: Switched to `ingest_text_document_fast()` (parse + chunks only) + `BackgroundTasks` + `run_post_ingest_tasks()`. Endpoint returns 202 immediately.
- Files: `apps/api/routes/knowledge_base.py`

#### B2 — Queue Auto-Clear (Completed)
- Root cause: Upload queue was purely client-side fire-and-forget — items stayed in `uploaded` phase forever, requiring manual Refresh.
- Fix: Added `processing`/`done` phases to upload queue, polls `listKBDocuments` every 4s while items are processing, auto-marks items as `done` when `ingestion_status === "ingested"`, auto-dismisses done items after 5s.
- Files: `apps/web/app/kb/page.tsx`, `apps/web/lib/kb/upload-queue.ts`, `apps/web/lib/kb/upload-queue.test.ts`

#### E1 — Chat State Persistence (Completed)
- Root cause: When user sends a chat message and navigates to another session, the in-flight `respondChat` fetch continues unaborted. On completion it calls `setMessages()` targeting stale state. When user returns, `loadMessages()` reloads from backend — but if the API call hasn't completed yet, messages are lost. No `AbortController`, no cleanup, no stale-request guarding existed.
- Fix: Added `AbortController` ref (`chatAbortRef`) + request-id counter (`activeRequestIdRef`). Session-change effect aborts in-flight requests and increments the counter. After `respondChat` succeeds, messages are reloaded from backend (not optimistic append) ensuring persistence. Stale callbacks guarded with `requestId !== activeRequestIdRef.current`. Converted `loadMessages` to `useCallback` for stable reference.
- Files: `apps/web/app/tutor/page.tsx`

#### E2 — Async Status Indicators (Completed)
- Root cause: Only a static "Thinking..." text existed with no animated indicator or phase progression, giving no feedback during multi-second AI responses.
- Fix: Added `ChatPhase` state machine (`idle → thinking → searching → responding`) with timed transitions (1.5s → searching, 4s → responding). Replaced static text with animated CSS typing dots (`.chat-typing-dots` with `typingBounce` keyframe) and descriptive phase labels. All styling extracted to CSS classes (`.chat-status-indicator`, `.chat-status-content`, `.chat-status-label`).
- Files: `apps/web/app/tutor/page.tsx`, `apps/web/app/globals.css`

#### A3 — Graph 422 Highlight Fix (Completed)
- Root cause: Frontend dropdown options for Nodes (1000), Edges (2000), and Depth (4 hops) exceeded backend FastAPI `Query(le=...)` validation limits (`le=500`, `le=1000`, `le=3` respectively). FastAPI returned 422 Unprocessable Entity.
- Fix: Removed out-of-range dropdown options — Nodes max now 500, Edges max now 1000, Depth max now 3 hops. Added 4 regression tests to `TestGraphParamValidation` verifying 422 on out-of-range and acceptance of max valid values.
- Files: `apps/web/app/graph/page.tsx`, `tests/api/test_response_contracts.py`

#### A2 — Graph Re-mount on Click (Completed)
- Root cause: Inline `onSelect`/`onBackgroundClick` arrow functions recreated every render → `draw` useCallback dependency changed → full SVG teardown + rebuild on every click. Also `detail_start` reducer action nulled `subgraph`, causing ConceptGraph to unmount and remount.
- Fix: (1) Stored `onSelect`/`onBackgroundClick` in refs (`onSelectRef`, `onBackgroundClickRef`) so `draw` no longer depends on them. (2) Memoized handler callbacks in page.tsx with `useCallback`. (3) Changed `detail_start` reducer to preserve previous `subgraph` during loading. Updated graph-state test accordingly.
- Files: `apps/web/components/concept-graph.tsx`, `apps/web/app/graph/page.tsx`, `apps/web/lib/graph/graph-state.ts`, `apps/web/lib/graph/graph-state.test.ts`

#### A1/A5 — Graph Panel Layout (Completed)
- Root cause: Both panels used `margin: 0.5rem` + flex layout with `clamp(20rem, 30%, 28rem)` for detail panel width, causing uneven spacing and responsive width changes.
- Fix: Replaced flex layout with CSS grid (`.graph-panels`) using `grid-template-columns: minmax(0, 65fr) minmax(0, 35fr)` for stable 65/35 split. Removed margin from both panels, standardized padding to `1rem 1.25rem`, added `overflow-wrap: break-word` to panel headings. Added responsive stacking rule for small screens.
- Files: `apps/web/app/globals.css`, `apps/web/app/graph/page.tsx`

#### A4 — Reset View Button (Completed)
- Root cause: No "Reset view" button existed. Zoom/pan resets happened only during full graph rebuilds. `zoomRef` was stored but never exposed.
- Fix: Added `onResetViewReady` callback prop to `ConceptGraph` that passes a `resetView` function to the parent. The function calls `zoomRef.current.transform` with `zoomIdentity` via a 300ms transition. Added "Reset view" button to graph controls. "Clear focus" button now also resets zoom.
- Files: `apps/web/components/concept-graph.tsx`, `apps/web/app/graph/page.tsx`

#### D1 — Collapsed Sidebar Logo/Arrow Swap (Completed)
- Root cause: In collapsed mode, the logo and expand arrow were shown side-by-side, wasting limited sidebar width.
- Fix: Added CSS rules to hide `.sidebar-collapse-btn` in collapsed mode by default, then show it on `.global-sidebar.collapsed:hover` while hiding `.sidebar-logo`. This swaps logo → expand arrow on hover.
- Files: `apps/web/app/globals.css`

#### D2 — Collapsed Sidebar Footer Cleanup (Completed)
- Root cause: Collapsed sidebar workspace block still partially rendered (select and icon-btn hidden individually but the block itself visible). Profile block alignment was inconsistent.
- Fix: Hide the entire `.sidebar-workspace-block` when collapsed (single `display: none` rule, replacing the two individual child-hiding rules). Profile block now stacks theme toggle and logout vertically with centered alignment.
- Files: `apps/web/app/globals.css`

#### D3 — Sidebar Collapsed State Persistence (Completed)
- Root cause: `collapsed` state was initialized with `useState(false)` — not persisted across page navigations or page refresh.
- Fix: Initialize from `localStorage.getItem('sidebar-collapsed')` via lazy initializer. Added `useEffect` to persist changes to localStorage on every toggle.
- Files: `apps/web/components/global-sidebar.tsx`

#### F-note — Graph Panels Layout Direction Fix (Completed)
- Root cause: The `@media (min-width: 768px)` responsive rule incorrectly overrode `.graph-panels` to single column on ALL desktop screens, causing top/bottom stacking instead of the intended left/right layout.
- Fix: Removed `.graph-panels` and `.graph-explorer` overrides from the `min-width: 768px` block. Added a `@media (max-width: 767px)` block instead for mobile-only stacking.
- Files: `apps/web/app/globals.css`

#### B1 — Sources Row Alignment (Completed)
- Root cause: Table cells used `vertical-align: top`, causing misalignment when cells had different content heights (badges vs plain text). Column widths were slightly unbalanced with description at 22% and chunks at 7%.
- Fix: Changed `vertical-align: top` to `vertical-align: middle` for consistent row centering. Rebalanced columns (description 20%, chunks 8%, uploaded 12%). Added scoped `.kb-table .button-row` styles with consistent font size and padding for action buttons.
- Files: `apps/web/app/globals.css`

#### B3 — Empty Sources State (Completed)
- Root cause: Empty state was a plain `<p className="status empty">` with no visual hierarchy, no icon, and no CTA button.
- Fix: Replaced with a rich `.kb-empty-state` card featuring a dashed border, document-plus SVG icon, heading, descriptive paragraph, and a CTA button that directly opens the file picker. Added corresponding CSS classes.
- Files: `apps/web/app/kb/page.tsx`, `apps/web/app/globals.css`

#### E3 — Concept Switch Rejection Flow (Completed)
- Root cause: When reviewing the concept switch rejection, the "Keep current" button set `switchDecision = "reject"` and showed a dead-end system message: "Concept switch rejected. Send your next message and the tutor will ask a clarifying question." The user had to manually send another message to trigger the backend's `requires_clarification` path.
- Fix: Replaced the dead-end system message with an automatic follow-up API call. When the user clicks "Keep current", the handler sets `switchDecisionRef.current = "reject"` (via ref for synchronous availability) and immediately calls `onSubmitChat("Which concept should we focus on?")`. This triggers the backend's concept resolution with `switch_decision == "reject"`, which returns the clarification prompt directly. Added `switchDecisionRef` to avoid stale closure issues with React state batching.
- Files: `apps/web/app/tutor/page.tsx`

#### F1 — Chat History Observability (Completed)
- Root cause: The `chat.respond` CHAIN span only recorded the raw user query and final output text. Rich context (history, assessment, flashcards, evidence, concept resolution) assembled into the LLM prompt was invisible in traces and logs.
- Fix: Added span attributes for all chat context components: `chat.history_text_len`, `chat.assessment_context_len`, `chat.flashcard_progress_len`, `chat.retrieval_chunk_count`, `chat.evidence_count`, `chat.resolved_concept`, `chat.concept_confidence`, `chat.requires_clarification`, `chat.switch_suggestion`. Added `log.info` call with structured key=value format. Added `log.debug` in `_generate_tutor_text` with full prompt length breakdown.
- Files: `domain/chat/respond.py`

#### F2 — LangChain Evaluation (Completed)
- Assessment: After thorough investigation, **LangChain migration is NOT recommended** for this codebase. Reasons:
  1. Current approach works well: Custom `_call_with_observability()` in providers.py already records OpenInference spans with input messages, response, token usage, and model name. F1 closes the remaining gap.
  2. Minimal surface area: Only 3 LLM capabilities — LangChain's agent/chain abstractions add overhead without proportional benefit.
  3. Dependency weight: LangChain adds ~50+ transitive dependencies; current approach uses only `openai` + `litellm`.
  4. JSON schema mode: Native `response_format` support works cleanly; LangChain adds an indirection layer.
  5. Phoenix compatibility: OTel + OpenInference conventions already produce full traces in Phoenix.
- Recommendation: Continue with current approach. F1+F4 improvements close the observability gap.

#### F3 — Ingestion Pipeline Debug (Completed)
- Root cause: `run_post_ingest_tasks()` had minimal logging — only `log.exception` for failures. No visibility into which stage was running, how many chunks were processed, or whether summary/graph extraction succeeded.
- Fix: Added structured `log.info` calls at every stage boundary: START, chunk load count, embedding START/DONE, summary generated with length, graph START/DONE, overall DONE. Each log line includes workspace_id and document_id. Added upload logging in the KB route.
- Files: `core/ingestion.py`, `apps/api/routes/knowledge_base.py`

#### F4 — Backend Logging (Completed)
- Root cause: No request-level logging, no configurable log level, no structured log format, zero Python logging in chat pipeline.
- Fix: Added `APP_LOG_LEVEL` setting (default INFO). Configured `logging.basicConfig()` in `create_app()` with structured format. Added request/response logging in `CorrelationIdMiddleware` (method, path, status, elapsed ms, request ID). Added module-level loggers in respond.py and knowledge_base.py.
- Files: `core/settings.py`, `apps/api/main.py`, `apps/api/middleware.py`, `domain/chat/respond.py`, `apps/api/routes/knowledge_base.py`

