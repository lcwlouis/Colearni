# WOW Release - Implementation Progress

> Last updated: Session 6

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
| S20 Graph ingestion SDK migration + schema hardening | Not Started | Graph extraction currently uses hand-rolled HTTP adapter; OpenAI strict schema failure reproducible in ingestion path |
| S21 KB live upload queue + multi-file uploads | Done | KB now keeps in-page queue (`queued/uploading/uploaded/failed`) and supports uploading multiple files in one batch |

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
