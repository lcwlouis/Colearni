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

## Assumptions and Defaults
- OpenClaw exact style snippet is not yet available; placeholder persona ships first.
- Concept IDs may remain internal while all API-facing IDs move to UUID.
- Research ingestion is approval-gated (no auto-ingest in first WOW release).
- Collaboration/invites are out of scope for this release.
