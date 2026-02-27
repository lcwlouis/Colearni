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

## Session 6 Reliability + Upload UX Plan (Current)
- Graph extraction reliability hotfix + SDK migration:
  - Reproduce the ingestion failure with `APP_INGEST_BUILD_GRAPH=true` using KB upload endpoint.
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

## Assumptions and Defaults
- OpenClaw exact style snippet is not yet available; placeholder persona ships first.
- Concept IDs may remain internal while all API-facing IDs move to UUID.
- Research ingestion is approval-gated (no auto-ingest in first WOW release).
- Collaboration/invites are out of scope for this release.
