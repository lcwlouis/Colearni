# WOW Release Plan: Multi-Workspace Intelligent Tutor

## Summary
- Convert Colearni from manual-ID MVP flows into authenticated, private-by-default multi-workspace learning with UUID-based external IDs.
- Add stateful tutor intelligence across sessions/workspaces, including scheduled readiness analysis and quiz CTA recommendations.
- Make practice truly cumulative: flashcards and practice quizzes become non-repetitive, progress-aware, and “generate more” capable (`5/10/25`) with stop conditions.
- Improve UX quality: no refusal callouts for social turns (like “Hi”), friendlier tutor persona, and visible workspace knowledge base management.
- Keep rollout in small PR slices (<=400 LOC net each), with strict tests and observability gates.

## Product Decisions Locked
- Auth: email magic link.
- UUID strategy: big-bang API cutover, hard cutover allowed.
- Workspace model: private multi-workspace, no invites in this release.
- Shared state: global user tutor profile + workspace-local mastery.
- Background research: workspace-approved web sources, review queue first.
- KB viewer: documents + chunks + concepts, with view/delete/reprocess.
- Prompt quality: prompt kit + eval suite.
- Readiness behavior: advisory only, tutor prompts user with a quiz CTA/button.
- Flashcard pass signal: learner self-rating (`Again/Hard/Good/Easy`).
- Persona: ship OpenClaw-placeholder persona now, patch to exact style when snippet is provided.

## Public API / Interface Changes
- Add auth endpoints:
  - `POST /auth/magic-link/request`
  - `POST /auth/magic-link/verify`
  - `POST /auth/logout`
  - `GET /me`
- Add workspace endpoints:
  - `GET /workspaces`
  - `POST /workspaces`
  - `GET /workspaces/{workspace_id}`
  - `PATCH /workspaces/{workspace_id}/settings` (research toggle + half-life behavior)
- Namespace existing flows under workspace and remove client-supplied `user_id`:
  - `POST /workspaces/{workspace_id}/chat/sessions`
  - `GET /workspaces/{workspace_id}/chat/sessions`
  - `GET /workspaces/{workspace_id}/chat/sessions/{session_id}/messages`
  - `POST /workspaces/{workspace_id}/chat/respond`
  - `POST /workspaces/{workspace_id}/quizzes/level-up`
  - `POST /workspaces/{workspace_id}/quizzes/{quiz_id}/submit`
  - `POST /workspaces/{workspace_id}/practice/flashcards/generate`
  - `POST /workspaces/{workspace_id}/practice/flashcards/progress`
  - `POST /workspaces/{workspace_id}/practice/quizzes`
  - `POST /workspaces/{workspace_id}/practice/quizzes/{quiz_id}/submit`
- Add KB endpoints:
  - `POST /workspaces/{workspace_id}/documents`
  - `GET /workspaces/{workspace_id}/knowledge-base`
  - `DELETE /workspaces/{workspace_id}/documents/{document_id}`
  - `POST /workspaces/{workspace_id}/documents/{document_id}/reprocess`
- Add tutor/readiness endpoints:
  - `GET /workspaces/{workspace_id}/tutor/readiness`
  - `GET /me/tutor-profile`
- Response contract updates:
  - Add `response_mode: "grounded" | "social"` to chat envelope.
  - Add optional `actions[]` in chat envelope for CTA cards (for example, `start_quiz`).
  - Flashcard generate response includes `run_id`, `has_more`, `exhausted_reason`, and stable `flashcard_id`s.

## Data Model Changes
- Identity/session:
  - `auth_magic_links`, `auth_sessions`.
- UUID external IDs:
  - Add UUID public IDs for all API-facing entities; API uses UUIDs only.
- Tenancy enforcement:
  - Central membership guard dependency for all workspace-scoped routes.
- Tutor intelligence:
  - `user_tutor_profile` (cross-workspace user memory/readiness summary).
  - `user_topic_state` (workspace+concept readiness and recommendations).
  - `tutor_readiness_snapshots` (job outputs for traceability).
- Stateful practice:
  - `practice_generation_runs`.
  - `practice_flashcard_bank`.
  - `practice_flashcard_progress` (self-rating, pass status, due state).
  - `practice_item_history` (quiz/flashcard fingerprints to avoid repeats).
- Research automation:
  - `workspace_research_sources`.
  - `workspace_research_runs`.
  - `workspace_research_candidates` (pending/approved/rejected/ingested).

## Core Behavior Changes
- Tutor context quality:
  - On quiz/practice submit, persist graded summary into session timeline as structured card.
  - Include recent assessment summaries in tutor prompt context.
  - Tutor always sees prior answers/feedback and can comment-teach after completion.
- Readiness cron (half-life):
  - Active users: nightly run (24h cadence).
  - Idle 1-7 days: slow cadence (72h).
  - Idle >7 days: pause runs until next activity.
  - Output is advisory only; tutor emits quiz CTA, does not auto-switch topics.
- Practice novelty/statefulness:
  - Exclude passed flashcards and passed-equivalent quiz items by default.
  - Enforce non-repetition via normalized prompt fingerprint + similarity threshold.
  - If overlap is high, generation performs bounded retrieval expansion before regenerating.
  - “Generate more” supports exactly `5`, `10`, `25`, repeatable until `has_more=false`.
- Grounding UX:
  - Add lightweight turn-intent classifier for social/chitchat turns.
  - Social turns return `response_mode="social"` and never emit refusal callouts.
  - Strict grounded refusals remain for real knowledge claims with insufficient evidence.
- Persona/prompting:
  - Introduce versioned prompt kit for tutor, quiz generation, grading commentary, practice generation.
  - Ship friendly OpenClaw-placeholder voice profile now with eval checks.

## Frontend Plan
- Replace manual workspace/user numeric inputs with authenticated user context.
- Add login flow and persistent workspace switcher with “Create workspace”.
- Add KB Explorer page showing documents/chunks/concepts + actions (delete/reprocess).
- Add readiness CTA cards in tutor timeline.
- Add flashcard self-rating controls and “Generate 5 / 10 / 25 more”.
- Remove red refusal UI for `response_mode="social"` responses.

## UX Follow-up Plan (Post Session 4)
- KB upload flow clarity:
  - Split file selection and upload into explicit separate actions (`Choose file` then `Upload Document`).
  - Surface immediate upload outcome with chunk count so ingestion success is visible.
- KB ingestion visibility:
  - Add per-document status indicator in KB list (`Ingested` when `chunk_count > 0`, otherwise `Pending`).
  - Keep a refresh action to re-fetch ingestion progress from backend.
- KB action safety (no browser popups):
  - Replace `window.confirm`/`window.alert` with inline confirmation and status banners for reprocess/delete.
- App shell layout stabilization:
  - Move workspace switcher, theme toggle, and logout out of top-right controls into the left sidebar bottom section.
  - Keep workspace selector outside the user profile block, but still anchored at the sidebar bottom.
- Backend visibility enhancement (next incremental slice):
  - Add explicit persisted ingestion lifecycle field (`queued`/`processing`/`ingested`/`failed`) for documents to replace chunk-count-only inference.

## Session 5 UX + Operability Plan (Current)
- Route rewrite script hygiene:
  - Confirm `tmp/rewrite_routes.py` is absent and not required after UUID+namespaced route cutover.
- KB upload operability:
  - Keep file selection and upload as two explicit actions (`Choose file` then `Upload document`).
  - Show upload outcome banner with ingested chunk count immediately after upload.
  - Keep manual refresh for status checks.
- KB ingestion + graph visibility:
  - Extend KB list payload with:
    - `ingestion_status` (`pending` | `ingested`)
    - `graph_status` (`disabled` | `pending` | `extracted`)
    - `graph_concept_count`
  - Reflect these fields in KB table badges so ingestion success is visible without logs.
- KB confirmation UX (no browser popups):
  - Replace browser dialogs (`confirm`/`alert`) with inline confirm UI and status banners for delete/reprocess.
- Layout stabilization:
  - Remove workspace/theme/logout controls from top-right header cluster.
  - Keep route navigation in topbar.
  - Move workspace selector + theme toggle + logout into tutor sidebar bottom profile/settings area.
- Model behavior configurability:
  - Add env-configurable graph LLM temperatures for different cases:
    - `APP_GRAPH_LLM_JSON_TEMPERATURE` (structured extraction/disambiguation)
    - `APP_GRAPH_LLM_TUTOR_TEMPERATURE` (tutor-style text generation)

## Session 6 Reliability + Upload UX Plan (Completed)
- Graph extraction reliability hotfix + SDK migration:
  - Reproduce the ingestion failure with `APP_INGEST_BUILD_GRAPH=true` using KB upload endpoint.
  - Fix JSON schema validation shapes to comply with strict-mode standards (`items` definitions, nullability, required arrays).
  - Migrate internal `urllib` HTTP requests inside `adapters/llm/providers.py` to official `openai`/`litellm` SDK packages.
  - Surface downstream provider errors securely as HTTP 502 with structured `IngestionGraphProviderError` exceptions instead of internal 500 stack traces.

## Session 9 Polish + Document Ingestion Upgrades (Completed)
- **Tutor Graph Context**:
  - Restrict the Tutor sidebar drawer so it does not carelessly render the full unlearned topology. It should only show the strictly mastered subgraph, or heavily limit the bounds (e.g., 2 hops max) when focusing on an actively learning concept.
- **Graph Layout Standardization**:
  - Uncouple the `Search concepts...` input from the concept graph visual card to make the panel native.
- **Document Summarization**:
  - Augment the KB ingestion pipeline (`build_graph_for_chunks`) to also derive and save a short 2-3 sentence overview (`summary` TEXT column).
  - Surface the generated summary in the UI (KB Table) to confirm file contents.
  - Pass the summary string natively into the Tutor context window as an active RAG signal.
- **Knowledge Base Table Fixing**:
  - Ensure `DELETE` endpoints accurately clear out the files and prevent stray orphaned database rows.
  - Resolve trailing whitespace and right-margin discrepancies on the table flex container layouts.
  - Add a regression test covering OpenAI structured output schema validation for graph extraction/disambiguation payloads.
  - Fix `_RAW_GRAPH_SCHEMA` and related schemas to be OpenAI-strict compliant (arrays require explicit `items` definitions).
  - Migrate graph LLM provider calls away from hand-rolled `urllib` HTTP toward SDK-backed clients:
    - OpenAI provider via official OpenAI Python SDK.
    - LiteLLM provider via LiteLLM SDK path (not manual OpenAI-compatible HTTP).
  - Preserve current `GraphLLMClient` interface so domain/core layers remain unchanged.
  - Normalize provider errors so ingestion routes return controlled API errors (no uncaught 500 traceback leaks).
  - Re-verify graph extraction path end-to-end by uploading `.md/.txt/.pdf` in KB UI with graph enabled.
- KB upload experience improvements:
  - Keep selected files visible with explicit in-page upload queue state (`queued`/`uploading`/`uploaded`/`failed`).
  - Support selecting and uploading multiple files in one action.
  - Keep document list refresh after batch upload completion so canonical table stays current.

## Session 10 UX Polish, Quiz Quality & Robustness (Completed)

### S28 Sidebar & Layout Polish (Completed)
- **Sidebar recent chats overflow**: The recent-chats list can expand unboundedly, pushing footer controls off-screen and clipping the context menu (rename/delete). Cap the chat list to a scrollable area with `overflow-y: auto` and ensure the context menu renders above the scroll boundary using fixed/portal positioning.
- **Chat horizontal scroll containment**: Long code blocks currently make the entire chat area scroll sideways. Constrain overflow to within the code block itself (`overflow-x: auto` on `pre`/`code` blocks) while keeping the chat thread at `max-width` without horizontal scroll.
- **Profile/logout layout**: The email, theme toggle, and logout button in the sidebar footer look unprofessional—the logout button stretches with email length. Redesign the profile block with a fixed-height, well-spaced row layout: email (truncated), then a row of icon actions (theme toggle, logout) evenly spaced.

### S29 Graph & Knowledge Explorer Polish (Completed)
- **Graph page box padding**: Add more spacing between the graph visualization panel and the concept detail panel. Make both panels dynamic/responsive (cards with proper margin, border-radius, shadow). Ensure the graph page doesn't look flat or left-crammed.
- **Tutor sidebar graph detail**: Show the concept description (not just mastery label) in the graph drawer on the tutor page. Restrict how far the user can hop from the node they started learning from (enforce `max_hops` parameter).
- **Graph suggestion strategy**: Adjacent and wildcard suggestions (`pick_lucky`) always deterministically return the same 2 items. Add randomization by sampling from the top-N candidates with weighted random selection instead of always taking `LIMIT 1`.
- **Graph edge weight normalization**: Change graph extraction weight to be integer 1–99 (round down all LLM responses to max 99). The LLM can produce samples between 1–20 but post-processing clamps to 1–99 range. No need to tell the LLM about the cap.

### S30 Quiz Generation Quality & Statefulness (Completed)
- **Fix quiz generation falling back to templates**: The `_auto_items` fallback produces identical template-based questions for every concept. The LLM-based generation path (`_generate_level_up_items_with_retries`) is failing silently. Fix `_supports_quiz_generation` to check for the correct method (`generate_tutor_text`), improve the generation prompt with richer context (concept description, neighboring concepts, document chunks), and make MCQ choices concept-specific rather than generic templates.
- **Level-up quiz tied to chat session**: Level-up quizzes should be tagged to each chat session ID and be stateful. The quiz drawer should persist across navigation and show status (building/ready/submitted) per chat.
- **New quiz button broken**: The "Start new quiz" button resets state but doesn't indicate generation is in progress, then gets stuck on internal server error. Add loading state, proper error display, and auto-retry logic.

### S31 Onboarding Flow (Future)
- When a user has no topics chosen as a starting point but has uploaded documents, the tutor/onboarding agent should list potential topics the user can start learning from.
- The onboarding process should ask the user what they want to learn, search for that knowledge, then lock the graph and navigate from there within the tutoring area.
- This should happen both for fresh workspaces and when documents are uploaded without prior topic selection.

### S32 Robustness & Testing
- ✅ Handle the `summary` column missing error (migration `20260227_0005` applied).
- ✅ Add robust integration tests for quiz generation + graph suggestion randomization paths.
- ⏳ Remaining: add/finish coverage for chat respond with document lookups, sidebar session CRUD, KB delete cascade.
- ⏳ Remaining: resolve legacy contract/doc sync + ingestion test debt (`test_api_docs_sync`, `test_response_contracts`, `test_ingestion_embeddings`, `test_document_ingestion_integration`).

## Session 11 UI Resilience + Quiz Lifecycle + Scalable Graph UX (Current Plan)

### Session 11 Implementation Map (Do-Not-Rediscover Notes)
- **Tutor shell/layout baseline (already implemented in Session 10)**:
  - Main shell and sidebar composition live in `apps/web/app/layout.tsx` + `apps/web/components/global-sidebar.tsx`.
  - Tutor page orchestration (timeline, drawers, quiz wiring, graph drawer) is in `apps/web/app/tutor/page.tsx`.
  - Global tutor/chat styling and sidebar overflow behavior are in `apps/web/app/globals.css`.
- **Current right-drawer architecture**:
  - Graph and quiz drawers are stateful toggles in `apps/web/app/tutor/page.tsx`.
  - Existing open animation is present; close transitions are still abrupt and need explicit exit-state handling.
  - Width behavior is currently constrained and should be upgraded to responsive clamp/minmax values.
- **Current code/markdown rendering path**:
  - Assistant message rendering and markdown style hooks are in tutor message rendering code and `.markdown-content` CSS rules (`apps/web/app/tutor/page.tsx`, `apps/web/app/globals.css`).
  - Session 10 fixed broad chat horizontal overflow; Session 11 still needs code-frame-specific clipping/scroll polish.
- **Quiz data path (already live, missing automation)**:
  - API routes: `apps/api/routes/quizzes.py`.
  - Domain generation/grading and persistence: `domain/learning/level_up.py`.
  - DB contract includes concept + optional session linkage (see `quizzes` table and repository usage).
  - Tutor response path currently does not actively query concept-scoped latest quiz status as first-class context.
- **Background job baseline**:
  - Existing scheduler-like recurring logic is readiness-only (`apps/jobs/readiness_analyzer.py`).
  - No current job auto-creates level-up quizzes when a concept becomes active.
- **Graph scalability baseline in Colearni**:
  - Graph UI: `apps/web/app/graph/page.tsx`, `apps/web/components/concept-graph.tsx`.
  - Tutor graph drawer reuse: `apps/web/app/tutor/page.tsx`.
  - Graph exploration backend: `apps/api/routes/graph.py`, `domain/graph/explore.py`, `adapters/db/graph_repository.py`.
  - Session 10 already added weighted randomization + normalized weights; Session 11 should focus on large-graph rendering strategy and controls.

### S33 Tutor UI Layout & Drawer Polish
- **Code block frame clipping**: normalize assistant markdown code blocks to use the app panel tokenized frame (`border`, `radius`, `surface`) and ensure full visible bounds with no clipping.
- **Code block horizontal overflow**: keep chat column width fixed while enabling in-frame horizontal scrolling for long lines (`overflow-x: auto` on code frame only).
- **Composer bottom anchoring**: ensure message composer is always pinned to bottom of tutor viewport while timeline independently scrolls.
- **Right drawer adaptive width**: allow quiz/graph drawer to expand on wider screens (responsive clamp/minmax), instead of fixed narrow width.
- **Closing animations**: implement exit animation for graph/quiz drawers to match existing entry animation (no abrupt disappear).
- **Left sidebar collapse**: add a first-class collapse/expand control for global sidebar mirroring the graph/quiz toggle pattern.
- **Sidebar footer clipping**: make workspace selector/profile/footer dynamically size to viewport height and avoid bottom cutoff across resolutions.
- **Implementation notes (next session)**:
  - Primary files: `apps/web/app/tutor/page.tsx`, `apps/web/app/globals.css`, `apps/web/components/global-sidebar.tsx`.
  - Keep changes CSS-first where possible; only introduce JS state for drawer close animation and sidebar collapse state persistence.
  - Validate against current behavior that already fixed session-list overflow and context-menu z-index (avoid regressing Session 10 fixes).

### S34 Quiz Lifecycle Automation & Concept Grounding
- **Scheduler verification + implementation**: there is currently no in-app cron/scheduler that auto-creates level-up quizzes on topic introduction. Add explicit job orchestration policy (internal scheduler or external cron contract) and implementation.
- **Auto quiz trigger**: when a concept transitions into active learning scope, enqueue/generate a level-up quiz asynchronously.
- **Mastered-neighbor context**: augment quiz generation context to include surrounding mastered nodes (bounded top-K by edge weight) and use that context in generation prompt payload.
- **Concept-attached canonical quiz access**: keep quiz attachment at `concept_id` as primary key for learning state, with optional `session_id` linkage for chat continuity.
- **Tutor queryability**: add retrieval/query helpers so tutor can fetch latest quiz status/results by concept and reference them during response generation.
- **Implementation notes (next session)**:
  - Generation logic extension point: `domain/learning/level_up.py`.
  - Trigger surfaces to evaluate: concept activation path in tutor/graph progression (`domain/chat/respond.py` and graph-learning transitions).
  - Add read helper(s) in adapters/domain for “latest quiz by concept/workspace” and inject into tutor prompt composition path (`domain/chat/prompt_kit.py` / `domain/chat/respond.py`).
  - Keep API routes thin (`apps/api/routes/quizzes.py`), business logic in domain/adapters only.

### S35 Scalable Graph Experience (External LightRAG Comparative)
- **External reference boundary (explicit)**: HKUDS/LightRAG is a separate repository and stack. We only adapt proven interaction/scaling patterns, not copy architecture or couple our APIs/models to LightRAG internals.
- **Verified comparative inputs**:
  - LightRAG `/graphs` endpoint exposes `label + max_depth + max_nodes` and returns truncation signals (`is_truncated`).
  - LightRAG WebUI combines Sigma.js + Graphology with runtime controls (depth/nodes/layout iterations), graph search indexing, and multiple layout engines/workers.
- **Adoptable patterns for Colearni (native implementation only)**:
  - Introduce progressive graph loading strategy (seed/subgraph first, incremental expand) within existing Colearni graph endpoints.
  - Add user controls for max nodes/depth/layout iterations and explicit truncation messaging in Graph/Tutor graph surfaces.
  - Add client-side graph indexing/search and selective rendering/hide-unselected-edge behavior for dense graphs.
  - Add background/worker layout iterations to keep interaction smooth under high node counts.
- **Non-goals / do-not-port**:
  - No direct dependency on LightRAG packages, stores, route layout, or frontend component structure.
  - No wholesale swap of Colearni graph APIs, tenancy rules, or data model to mirror LightRAG.
- **Performance target slice**: define and validate baseline target for >=1k nodes interactive rendering in Colearni Graph page without UI lockups.
- **Implementation notes (next session)**:
  - Keep Colearni graph endpoints and tenancy contracts unchanged; layer in pagination/progressive-expansion semantics if needed, but without introducing LightRAG-specific route contracts.
  - Start by instrumenting current render bottlenecks in `apps/web/components/concept-graph.tsx` before adding worker/layout complexity.
  - If adding node/depth controls, wire through existing graph query state and route params rather than introducing parallel API surfaces.

### S36 Documentation Integrity
- Create and maintain `docs/PROMPTS.md` as source-of-truth inventory of prompts by agent/domain with direct code paths.
- Before closing any future PLAN slice, ensure implementation details are reflected in `docs/PROGRESS.md` (and API/architecture docs when contract/design changes).

---

## Session 12: Reasoning/Context Integrity + Test Debt + Onboarding + Spaced Repetition

### S45 (Urgent) Reasoning Controls + Full Context Envelope Integrity
- **Problem statement (observed in Phoenix)**:
  - LLM API calls are effectively showing only system + latest message, with missing explicit chat-history sections and missing topic-linked assessment/flashcard context in outbound prompts.
- **Reasoning policy by task (toggleable)**:
  - Default `reasoning=off` for high-volume structured generation paths:
    - graph extraction/disambiguation (`extract_raw_graph`, `disambiguate`)
    - quiz generation (`level_up` + practice generation)
  - Default `reasoning=on` for deliberative text tasks:
    - tutor chat response generation
    - quiz grading/feedback synthesis
    - agents requiring deeper planning/synthesis
  - Add per-surface overrides via settings/env + request-level override for controlled experimentation.
- **Configuration surface**:
  - Add explicit settings keys (example naming):
    - `APP_LLM_REASONING_CHAT`
    - `APP_LLM_REASONING_QUIZ_GRADING`
    - `APP_LLM_REASONING_GRAPH_GENERATION`
    - `APP_LLM_REASONING_QUIZ_GENERATION`
  - Implement normalized reasoning config object in provider adapters so OpenAI/LiteLLM/no-reasoning models degrade gracefully.
- **Provider/model compatibility contract**:
  - Reasoning toggles must be capability-aware per provider/model:
    - If a model/provider supports reasoning controls, apply requested mode.
    - If unsupported, silently fallback to standard generation while emitting an observability event (`reasoning_mode_unsupported_fallback`).
  - Keep behavior stable when switching providers/models; no hard failures from unsupported reasoning knobs.
- **Full context envelope integrity (chat + assessments + flashcards)**:
  - Update `domain/chat/respond.py` + `domain/chat/session_memory.py` to construct explicit prompt sections:
    - `RECENT CHAT HISTORY`
    - `COMPACTED PRIOR CONTEXT`
    - `TOPIC ASSESSMENT HISTORY` (quiz/practice outcomes)
    - `FLASHCARD PROGRESS SNAPSHOT`
  - Ensure these sections are always included when data exists, concept-scoped where applicable, and budgeted by token policy.
  - Extend quiz generation context (`domain/learning/level_up.py`) with chat-history-derived misconceptions and relevant assessment traces.
- **Observability + Phoenix verification**:
  - Add structured span attributes/events for outbound prompt sections present/missing and token-budget allocation.
  - Add regression tests asserting that outbound prompt text includes history + assessment + flashcard sections for seeded sessions.
  - Add explicit acceptance check in Phoenix traces: outbound user payload must include more than latest-turn text for non-empty sessions.
- **Model/provider switching impact (explicit)**:
  - Yes, this affects switching behavior only insofar as capability differences are normalized by adapter fallback.
  - With the capability-aware contract above, changing providers/models should not break flows; only effective reasoning mode may differ and will be observable.
- **Execution order**:
  - Run S45 before S37–S40 so Session 12 is built on correct prompt-context + reasoning semantics.

### S37 Test Debt & Mock Infrastructure Cleanup
- **Fix `_FakeSession`**: Add `.execute()`, `.get_bind()` stubs to the unit-test `_FakeSession` in `tests/core/test_ingestion_embeddings.py`, or replace with `MagicMock(spec=Session)`.
- **Explicit settings in unit tests**: Every `test_ingest_*` test must pin `ingest_build_graph=False` (or `True` with a matching stub client) via `settings.model_copy(update={...})` so tests don't depend on env file state.
- **Fix `IntegrationGraphLLM`**: Add `generate_tutor_text(self, *, prompt: str) -> str` returning a deterministic stub summary so the document summary path doesn't NPE.
- **Fix integration ingestion tests**: In `tests/db/test_document_ingestion_integration.py`, pass `graph_llm_client=IntegrationGraphLLM()` and appropriate settings for non-graph tests.
- **Sync API docs + contracts**: Update `docs/API.md` headings for route additions since Session 9. Update `REQUIRED_FIELDS` in `tests/api/test_response_contracts.py` for new schema fields (`is_truncated`, `total_concept_count`).
- **Fix settings test**: Update `tests/core/test_settings.py` observability alias expectation or pin via monkeypatch.
- **Exit criteria**: 0 failing tests in full `pytest tests/` run.
- **Implementation notes**:
  - Primary files: `tests/core/test_ingestion_embeddings.py`, `tests/db/test_document_ingestion_integration.py`, `tests/api/test_api_docs_sync.py`, `tests/api/test_response_contracts.py`, `tests/core/test_settings.py`.
  - Keep < 200 LOC net.

### S38 Onboarding Flow
- **Backend: onboarding status endpoint**: Add `GET /workspaces/{ws_id}/onboarding/status` returning `{ has_documents, has_active_concepts, suggested_topics }`.
- **Domain: topic suggestion logic**: Add `suggest_starting_topics(db, workspace_id, limit=5)` returning top-N concepts by degree (most connected = most central).
- **Tutor onboarding prompt path**: In `domain/chat/respond.py`, detect when workspace has documents but user has no mastery records. Inject onboarding system prompt listing suggested topics.
- **Frontend: onboarding card**: In tutor page, when user has documents but no active concepts, render an onboarding card with clickable topic chips.
- **Tests**: Unit test for `suggest_starting_topics`. API test for onboarding endpoint. Integration test for onboarding prompt injection.
- **Implementation notes**:
  - New files: `domain/onboarding/` or extend `domain/graph/explore.py`.
  - Route: `apps/api/routes/onboarding.py` or extend graph routes.
  - Frontend: `apps/web/app/tutor/page.tsx` (onboarding state check + card).
  - Keep < 300 LOC net.

### S39 Spaced Repetition Foundation
- **Schema + migration**: Add `next_review_at TIMESTAMPTZ` and `interval_days FLOAT DEFAULT 1.0` to `practice_flashcard_progress`.
- **Domain: SR scheduler**: New `domain/learning/spaced_repetition.py` implementing SM-2 variant. Map `Again/Hard/Good/Easy` → interval multipliers (0.5×/1.0×/2.5×/4.0×). Compute `next_review_at = now + interval_days`.
- **Wire into flashcard progress**: After recording flashcard rating, call `compute_next_review()` and persist `interval_days` + `next_review_at`.
- **Due flashcards query**: Add `get_due_flashcards(db, workspace_id, user_id, limit)` selecting cards where `next_review_at <= now()` ordered by most overdue.
- **API endpoint**: `GET /workspaces/{ws_id}/practice/flashcards/due?limit=10` returning due flashcards.
- **Tests**: Unit tests for `compute_next_review` with all 4 ratings. Unit test for due-cards query ordering. API test for `/due` endpoint.
- **Implementation notes**:
  - New file: `domain/learning/spaced_repetition.py`.
  - Migration: `adapters/db/migrations/versions/`.
  - Wire: `domain/learning/practice.py` (rating handler), `apps/api/routes/practice.py` (due endpoint).
  - Keep < 300 LOC net.

### S40 Quiz Gardener Operability & Testing
- **Unit tests for quiz_gardener**: Add tests with mocked DB verifying candidate query logic and `create_level_up_quiz` delegation.
- **Makefile target**: Add `make quiz-gardener` entry to run the job (same pattern as `readiness_analyzer`).
- **Docs**: Document quiz_gardener invocation in `docs/ARCHITECTURE.md` alongside existing job documentation.
- **Implementation notes**:
  - Test file: `tests/domain/test_quiz_gardener.py` (or `tests/jobs/`).
  - Keep < 100 LOC net.

---

## Session 13: Session-11 Misses Remediation + UX Parity

### S41 Tutor Continuity, Context Memory, and Naming Reliability
- **Composer bottom anchoring (hard fix)**:
  - Replace ad-hoc inline style composition in `apps/web/app/tutor/page.tsx` with a stable shell contract: header fixed-height row, timeline scroll container (`flex: 1; min-height: 0; overflow-y: auto`), composer dock row (`flex-shrink: 0`) that is always at viewport bottom.
  - Remove competing layout definitions (`.chat-main` grid in CSS vs inline `display:flex` in JSX) and keep a single source-of-truth style in `apps/web/app/globals.css`.
  - Add a viewport-height assertion for the tutor shell to avoid composer drifting to “bottom of last message”.
- **Conversation memory (full-history aware, bounded)**:
  - Current system exists but is shallow: `domain/chat/session_memory.py` only includes latest system summary + recent 10 messages and uses lexical truncation.
  - Upgrade to tiered memory: `recent_window` + `rolling_structured_summary` + `assessment_cards` + `topic_trace`.
  - Introduce token budgeting + deterministic compaction policy (budget by section, then summarize oldest unsummarized range) instead of char-based slicing.
  - Add compaction metadata (`source_start_id`, `source_end_id`, `token_estimate`, `version`) to system-summary payload for auditability.
  - Include explicit retrieval tests proving older turns survive via summary, not only recent-window replay.
- **Chat-history-informed quiz generation**:
  - Extend level-up generation context in `domain/learning/level_up.py` to include compacted session slices (user misconceptions, unresolved asks, repeated corrections) from `session_memory`.
  - Pass this as a dedicated `CHAT_HISTORY_CONTEXT` block in the quiz prompt and guard against leakage of irrelevant chat by concept-scoping and recency weighting.
  - Add tests asserting quiz items react to known conversation misunderstandings.
- **Auto session title generation (<=5 words)**:
  - Current behavior is first-user-message fallback (`set_chat_session_title_if_missing(...)`); replace with topic-aware summarization title generator.
  - New title policy: 2–5 words, title-case, no punctuation suffix noise, include dominant concept/topic if available.
  - Trigger naming after first assistant response (when concept inference + context are available), with idempotent update and manual rename override preservation.
- **Sidebar delete confirmation regression**:
  - Reintroduce explicit in-app confirmation step in sidebar context menu delete path (`apps/web/components/global-sidebar.tsx` + `apps/web/lib/tutor/chat-session-context.tsx`).
  - Use inline confirmation popover/modal (not `window.confirm`) consistent with prior UX direction.
- **Session handoff automation point (requested)**:
  - Add a completion hook for S41: once all accepted S11/S12 fixes are marked done and validated, trigger an LLM-driven maintenance task to update `docs/PLAN.md` and `docs/PROGRESS.md`, then automatically draft and start the next session checklist.

### S42 Markdown Rendering, Sidebar Footer Fit, and Collapsed Sidebar Quality
- **Code block rendering hardening**:
  - Investigate clipping path across `.chat-content { overflow: hidden; }`, markdown wrappers, and nested `pre/code` styles.
  - Ensure block code uses frame tokens without clipping while preserving in-block horizontal scroll only.
  - Verify KaTeX + fenced code coexistence and no double-background artifacts in assistant responses.
- **Sidebar footer should fit (no internal scroll for workspace/profile cards)**:
  - Remove forced footer scroll (`.sidebar-footer max-height: 40vh; overflow-y: auto`) and rebalance layout with session list as sole scrolling region.
  - Keep workspace selector + profile/logout visible without nested scroller in normal viewport sizes.
- **Collapsed sidebar UX rework (image-3 remediation track)**:
  - Add explicit collapsed rail design (icon-only nav with centered hit targets, tooltips, active indicator, clear expand affordance).
  - Preserve quick access actions (new chat, workspace switch entry point) in collapsed mode rather than hiding all controls.
  - Improve visual rhythm: spacing, icon alignment, and state transitions.
- **Acceptance criteria**:
  - No footer scrollbar at common desktop heights.
  - Collapsed sidebar remains fully usable and discoverable.
  - Code blocks render with full frame and no clipping in long-line and multiline cases.

### S43 Graph UX Density + LightRAG-Informed Adaptation (Native)
- **Wasted-space reduction on Graph page (image-1)**:
  - Remove fixed SVG dimensions in `apps/web/app/graph/page.tsx` (`width={700}`, `height={500}`) and adopt responsive fill with available panel height.
  - Convert panel split to ratio-driven layout with resizable or adaptive columns so graph canvas claims primary space.
  - Tighten outer padding/margins and reduce dead zones in right panel empty state.
- **LightRAG adaptation plan (without coupling)**:
  - Research HKUDS/LightRAG runtime patterns (graph search index, focus/neighbor expansion, hide-unselected edges, multi-layout iterations).
  - Implement Colearni-native equivalents in `apps/web/components/concept-graph.tsx` and graph page controls:
    - search-and-focus on graph nodes,
    - focus mode (selected node + N-hop neighborhood),
    - progressive expansion,
    - optional worker-driven layout iterations for large graphs.
  - Keep existing Colearni API contracts/tenancy unchanged.
- **Performance target**:
  - Maintain interactive graph operations at >=1k nodes with no visible UI lockups (selection, pan/zoom, focus filter, search highlight).

### S44 Document Deletion vs Graph Retention Policy + Implementation
- **Current behavior audit**:
  - Deleting a document removes `chunks`, `provenance`, `concepts_raw`, `edges_raw` for those chunks, but canonical graph entities may persist.
- **Policy decision slice (explicit user-facing choice)**:
  - Add workspace setting or per-delete option:
    - `retain_learned_graph=true` (keep canonical concepts/edges not currently backed by docs), or
    - `prune_orphan_graph=true` (remove canonical nodes/edges with no remaining provenance/chunk support).
- **Implementation plan**:
  - Add orphan-pruning service in domain layer, run synchronously (small docs) or enqueue background prune job (large workspaces).
  - Add KB delete UI affordance clarifying graph impact before confirmation.
  - Add regression tests for both policies.
- **Default recommendation**:
  - Default to retain graph for continuity; provide explicit “prune orphaned graph nodes from this document” advanced option to prevent clutter when desired.
---

## Session 14: Learning Intelligence & Graph Curation

### S46 Learning Path Generator (S4 foundation)
- **Domain logic**: `domain/learning/learning_path.py` — `generate_learning_path(session, workspace_id, user_id, limit=10)` ordering next concepts by topological dependency (edges from already-mastered nodes), readiness decay, and degree centrality tiebreaker.
- **Prerequisites**: `get_prerequisites(session, workspace_id, concept_id)` returning incoming edge source concepts with their mastery status — enables "learn X before Y" signals.
- **API endpoint**: `GET /workspaces/{ws_id}/learning/path?limit=10` returning ordered path with concept name, description, readiness score, prerequisite status.
- **Route file**: New `apps/api/routes/learning.py`; register in `main.py`.
- **Schemas**: `LearningPathResponse`, `LearningPathEntry` in `core/schemas.py`.
- **Tests**: Unit tests for path ordering with various mastery/edge configurations.
- **Est. ~300 LOC net.**

### S47 Concept Strength Analytics & Weakness Detection (S2 foundation)
- **Domain logic**: `domain/learning/strength.py` — `compute_concept_strengths(session, workspace_id, user_id)` aggregating quiz pass rate, flashcard average interval + fail rate, readiness score, and time since last engagement into a normalized 0–1 `strength_score` per concept.
- **Weakness ranking**: `get_weakest_concepts(session, workspace_id, user_id, limit=5)` for targeted review recommendations.
- **API endpoint**: `GET /workspaces/{ws_id}/learning/strengths` returning per-concept strength breakdown.
- **Tutor context**: Inject weakest-concept signals into `respond.py` prompt context so the tutor can proactively mention areas for review.
- **Tests**: Unit tests for strength aggregation, weakness ranking, and tutor context injection.
- **Est. ~280 LOC net.**

### S48 Graph Curation: Duplicate Detection & Merge (S1 foundation)
- **Duplicate detection**: `domain/graph/curation.py` — `find_probable_duplicates(session, workspace_id, limit=20)` using alias overlap, normalized name similarity, and shared neighbor ratio to score candidate merge pairs.
- **Merge operation**: `merge_concepts(session, workspace_id, keep_id, merge_id)` retargets edges, transfers aliases, merges provenance, deactivates merged node — reusing gardener patterns.
- **API endpoints**: `GET /workspaces/{ws_id}/graph/curation/duplicates` and `POST /workspaces/{ws_id}/graph/curation/merge`.
- **Schemas**: `DuplicateCandidateResponse` in `core/schemas.py`.
- **Tests**: Unit tests for duplicate scoring and merge correctness.
- **Est. ~350 LOC net.**

### S49 Spaced Repetition Review Session Orchestrator
- **Review session lifecycle**: `domain/learning/review_session.py` — `start_review_session(session, workspace_id, user_id, limit=20)` batches due flashcards into a tracked session, `complete_review_session(session, review_id)` computes stats (cards reviewed, avg rating, retention rate, concepts covered).
- **Migration**: New `review_sessions` table (id, workspace_id, user_id, started_at, completed_at, card_count, cards_reviewed, avg_rating, retention_rate).
- **API endpoints**: `GET /workspaces/{ws_id}/practice/review/start?limit=20` and `POST /workspaces/{ws_id}/practice/review/{review_id}/complete`.
- **Tests**: Unit tests for session lifecycle and stats computation.
- **Est. ~350 LOC net.**

### S50 Mastery Decay Alerts & Tutor Proactive Nudges
- **Nudge generation**: `domain/readiness/nudge.py` — `generate_decay_nudges(session, workspace_id, user_id, threshold=0.3, limit=3)` finds concepts below readiness threshold, ranked by decay velocity.
- **Tutor integration**: `format_nudge_for_tutor(nudges)` produces a `PROACTIVE REVIEW NUDGES` prompt section. On first message of a session, inject decay nudges so the tutor weaves in "Your understanding of X might be getting rusty" naturally.
- **Wire into**: `respond.py` (first-message detection), `prompt_kit.py` (nudge section template).
- **API endpoint**: `GET /workspaces/{ws_id}/readiness/nudges` for frontend nudge banner.
- **Tests**: Unit tests for nudge selection, threshold filtering, and prompt formatting.
- **Est. ~250 LOC net.**
### Incorporated from SUGGESTIONS.md
- **Spaced Repetition Optimization Engine** (S2): ML-driven spaced repetition to dynamically identify weakest graph links and push micro-assessments. (Future)
- **Markdown-Based Skills Architecture** (S9): Migrate away from hardcoded prompts toward file-system-based "skills" directory with discoverable Markdown prompt files. (Future — aligns with S25 Agentic RAG)
- **Autonomous Learning Path Generation** (S4): Tutor proactively generates personalized daily/weekly syllabus based on KB and readiness scores. (Future — aligns with S31 Onboarding)
- **Proactive Knowledge Graph Curation** (S1): Background agents continuously refine the graph—merge duplicates, highlight contradictions, suggest new relationships. (Future)

- S22 App Shell & Sidebar Redesign:
  - Move page navigation buttons from the top bar into the left sidebar (similar to ChatGPT/Gemini).
  - Standardize the layout of KB and Graph pages to match the Tutor chat page style.
  - Implement workspace management UI (rename existing workspaces, add new workspaces).
- S23 Unified Graph & Practice UX:
  - Collapse the Practice page into the Graph page.
  - Always display the full knowledge graph by default on the Graph page (similar to LightRAG WebUI).
  - Add visual indicators for edge directions (arrows) and improve edge weight rendering, as the backend already stores `src_id`, `tgt_id`, and `weight`.
  - Ensure all flashcards are stateful, eliminating non-stateful flashcards. Flashcards are stored per concept per workspace.
- S24 Tutor Context Expansion & Quiz Grading UI:
  - Add chat state URL persistence so refreshing the Tutor chat page restores the active chat session ID instead of jumping to the latest or losing state. Evaluate if chat session IDs should be migrated to UUID `public_id` paths.
  - Store practice quizzes persistently so they are referenceable by the tutor and the user can revisit old quizzes.
  - Revise the practice quiz workflow so clicking "Start new quiz" automatically generates the next one without needing to manually click generate again.
  - Adjust practice quiz frontend grading: scores >= 0.7 for non-MCQ questions display as green (correct/pass).
- S25 Agentic RAG Tutor:
  - Upgrade the Tutor from a static KB query pipeline into an Agentic RAG system based on the prompt.
  - Implement a "skills folder" architecture (inspired by nanobot/openclaw) using Markdown files to guide the agent in dynamic discovery of prompts and capabilities.
  - Dynamically build the tutor prompt to include summarized flashcards, practice quizzes, and level-up quizzes.
  - Provide tools to the agent so it can access granular details of the user's history and knowledge base when needed.
- S26 Agent Thoughts Chat UI:
  - Introduce an interactive "thoughts" UI in the chat (like ChatGPT/Copilot).
  - Display the agent's current step: thinking, searching history, navigating graph, etc.
- S27 Architecture Documentation:
  - Document the current prompting system, agent architecture, and how agents are looping.

## Test Cases and Scenarios
- Auth:
  - Magic-link request/verify success, expiry, replay prevention.
- Tenancy:
  - Cross-user workspace access returns `403` everywhere.
- UUID cutover:
  - All API endpoints reject numeric IDs and accept UUIDs.
- Tutor context:
  - Quiz submit creates structured timeline card.
  - Next tutor response references latest graded result context.
- Readiness jobs:
  - Cadence transitions at inactivity boundaries.
  - Advisory CTA emitted, no auto topic mutation.
- Practice statefulness:
  - Passed flashcards excluded on next generate.
  - `5/10/25` generation respected.
  - Overlap retry path triggers retrieval expansion.
  - Exhaustion sets `has_more=false` with reason.
- Grounding UX:
  - “Hi” returns social answer, no refusal.
  - Strict factual request without evidence still refuses correctly.
- Frontend:
  - Workspace creation/switching, KB view/actions, flashcard rating flow, CTA rendering.

## Rollout Sequence (Small PR Slices)
1. Auth + session primitives and `/me`.
2. Workspace APIs + membership guard dependency.
3. UUID API contract cutover.
4. Chat/practice/quizzes route contract migration (remove client `user_id`).
5. Login + workspace switcher UI.
6. KB Explorer APIs + UI.
7. Persist quiz/practice feedback cards into chat memory.
8. Tutor prompt context upgrade for assessment history.
9. Readiness schema + cron job + advisory CTA plumbing.
10. Stateful flashcards schema + APIs + UI ratings.
11. Practice quiz novelty engine + overlap-aware generation.
12. Research agent schema + cron + review queue.
13. Prompt kit + persona profile + social intent mode.
14. Eval suite + observability expansion + hardening.
15. S22 App Shell & Sidebar Redesign
16. S23 Unified Graph & Practice UX
17. S24 Tutor Context Expansion & Quiz Grading UI
18. S25 Layout & Tutor Graph Context (was Agentic RAG — deferred)
19. S26 Document Summaries & Deletion Fixes (was Agent Thoughts — deferred)
20. S27 UUID Navigation & Dashboard Widgets (was Architecture Docs — deferred)
21. S28 Sidebar & Layout Polish
22. S29 Graph & Knowledge Explorer Polish
23. S30 Quiz Generation Quality & Statefulness
24. S31 Onboarding Flow
25. S32 Robustness & Testing
26. S33 Tutor UI Layout & Drawer Polish
27. S34 Quiz Lifecycle Automation & Concept Grounding
28. S35 Scalable Graph Experience (LightRAG-Informed)
29. S36 Documentation Integrity
30. S45 (Urgent) Reasoning Controls + Full Context Envelope Integrity
31. S37 Test Debt & Mock Infrastructure Cleanup
32. S38 Onboarding Flow
33. S39 Spaced Repetition Foundation
34. S40 Quiz Gardener Operability & Testing
35. S41 Tutor Continuity, Context Memory, and Naming Reliability
36. S42 Markdown Rendering, Sidebar Footer Fit, and Collapsed Sidebar Quality
37. S43 Graph UX Density + LightRAG-Informed Adaptation (Native)
38. S44 Document Deletion vs Graph Retention Policy + Implementation
39. S46 Learning Path Generator
40. S47 Concept Strength Analytics & Weakness Detection
41. S48 Graph Curation: Duplicate Detection & Merge
42. S49 Spaced Repetition Review Session Orchestrator
43. S50 Mastery Decay Alerts & Tutor Proactive Nudges

## Assumptions and Defaults
- OpenClaw exact style snippet is not yet available; placeholder persona ships first.
- Concept IDs may remain internal while all API-facing IDs move to UUID.
- Research ingestion is approval-gated (no auto-ingest in first WOW release).
- Collaboration/invites are out of scope for this release.
