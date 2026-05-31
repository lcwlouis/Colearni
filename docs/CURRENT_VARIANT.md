# Current Implementation Variant

## Purpose

This file records the current local-ready tutor/quiz implementation details that have moved ahead of the original phase wording.

Read this after `docs/REBUILD_PLAN.md` before changing tutor, quiz, or adjacent planning docs.

If this file conflicts with an older phase description, follow this file and update the stale doc in the same change.

## Tutor Runtime

- **Unified structured-JSON turn classifier (Phase 13 hardening, current production path).** The first tutor call is a single enforced-JSON classifier (`tutor_turn_classifier.v1.md` → `LLMTutorAgent.classify_turn`) returning `{"mode": ..., "blocks_active_quiz_answer": bool}`. It replaces BOTH the old tagged mode classifier AND the separate `quiz_answer_guard` call, so an active-quiz turn costs one classifier call instead of two. Structured output (`response_format={"type":"json_object"}` + `thinking=False` on the OpenAI-compatible/OpenRouter path) plus a JSON-only prompt prevents the model from accidentally answering the learner in the classifier completion — the previous leak vector where conversation context tempted it to reply instead of emitting a tag. Reasoning is forced off so the confidential active quiz questions (passed only into this classifier) never appear in a trace. Parsing fails open: invalid JSON falls back to `_infer_mode_from_message` and does not block. `build_prep(mode, context)` then constructs the second-pass prompt (including tool-gated `direct`/`free_explore` resolution) without a tagged first pass.
- **Per-turn call budget.** A normal production turn is two calls: the unified classifier, then the answering call (the retrieval planner doubles as the answer when no tools are used, so primer-only concepts stay at one answering call). The conversation summary, when it runs, is a third call but is emitted AFTER the `done` event, so it never adds latency to the visible turn. A blocked active-quiz turn costs only the classifier call (or zero LLM calls on a verbatim exact-prompt match).
- **Back-compat tagged classifier.** The old `tutor_base.v1` tagged classifier and `_run_first_pass`/`prepare_mode` remain for `respond_stream` and any agent without `classify_turn`; such legacy agents still use the standalone semantic `quiz_answer_guard` (`quiz_guard.py`). The notes below describe that legacy path.
- Tutor answer budget is controlled by `LLM_TUTOR_MAX_TOKENS`, separate from provider reasoning budgets and headroom.
- The legacy first (mode-selection) LLM call is a **pure classifier**: `tutor_base.v1` instructs it to emit exactly one control line (`<mode .../>` or `<tool .../>`) and stop, writing no learner-facing reply. The learner-visible answer is always produced by the second call via the mode-specific final prompt. The first call uses a small dedicated token cap (`tutor_mode_selection_max_tokens`, default 48) instead of the full answer budget; the second call keeps `LLM_TUTOR_MAX_TOKENS`. The classifier prompt front-loads a no-prose contract, ends with the exact allowed control lines, and includes short few-shot examples so weak models emit a bare tag; the classifier call runs at temperature 0.
- **Robust mode resolution / prose fallback**: weak models sometimes ignore the classifier contract and write a learner-facing reply instead of a control line. The parser searches the buffered output for a valid `<mode>`/`<tool>` tag anywhere (honouring a leading blank line); if the model produced prose with no tag, the service does NOT blindly default to `socratic`. Instead it infers a mode from the learner's latest message via `_infer_mode_from_message` (the same keyword heuristic backing `FallbackTutorModeClassifier`). "I don't know" / "I'm stuck" / "no idea" route to `repair` (teach), "test me"/"quiz me" to `quiz_prompt`, explore/direct keywords to their modes, otherwise `socratic`. This prevents the tutor from getting stuck asking a question every turn when the classifier degrades.
- The tutor streams public SSE events for `status`, `thinking`, `tool_call`, `tool_result`, `mode`, `token`, `done`, and `error`.
- First-pass (mode-selection) reasoning streams live: `prepare_mode_stream` yields `status`/`thinking` events as the first LLM call produces them, instead of buffering them until the call completes. The resolved tool/mode events are then emitted, followed by the second-call response stream. (`prepare_mode` + buffered `_ModePreparation.buffered_events` remain for the non-streaming/back-compat path.)
- `mode` is guaranteed before visible `token` events, but gated-mode `status` and `tool_*` events may appear first.
- `tool_call` and `tool_result` describe the internal instruction-tool step; the later `mode` event is the final visible tutor mode.
- Public `tool_result` payloads are sanitized previews only. Raw internal tutor instructions must not be exposed.
- Hidden tool-call/tool-result turns are persisted for prompt replay, but the public conversation history still returns only visible user/assistant messages.
- Assistant turns persist both full `reasoning` text and ordered public `reasoning_parts`.
- `get_tutor_instructions` is wrapped by the normalized provider-tool schema internally, while the tutor still emits/persists the existing tagged compatibility representation for public SSE and replay stability.
- **Mastery-gated `direct` now teaches (guided) instead of refusing.** When the classifier picks `direct` but mastery is not `mastered`, the turn stays labelled `direct` and renders the `tutor_direct_locked` prompt: a brief, supportive explanation/walkthrough of the current concept (a few sentences, optionally one short worked example or a couple of steps) optionally ending with ONE gentle check question. The previous "buffer the reply and replace it with a single bare Socratic question" path (and its `_should_buffer_locked_socratic_fallback` / `_coerce_locked_socratic_reply` helpers and the `_ModePreparation.locked_socratic` flag) has been removed; gated `direct` streams normally. `mastered` learners still get the crisp `tutor_direct` answer. `free_explore` remains gated to `mastered` and still falls back to bounded `explore` via `tutor_locked_mode`.
- **Guided-teaching guardrail (no cheatsheets / answer dumps).** The `tutor_direct_locked` prompt and the shared final-response contract forbid producing an exhaustive answer key / cheatsheet / exam-cram summary, completing the learner's quiz/assessment questions, dumping "all the answers / everything to memorise", or covering many concepts to bypass the flow. When the learner is clearly extracting answers rather than learning, the tutor warmly redirects to teaching the concept instead. Teaching stays scoped to the single current concept and the Trail goal.
- If a reasoning-enabled call ends with no visible answer, the tutor retries once with `thinking=False` and emits `retrying_without_thinking` before failing.
- **Empty-completion guard:** if a turn ends with no visible tutor text, the service rolls back and emits an `empty_completion` `error` rather than persisting a blank assistant bubble. This now fires for ANY empty visible answer (`not full_text.strip()`), regardless of whether the model produced reasoning — previously a fully-empty completion (no text and no reasoning) slipped past the guard and persisted a blank assistant turn plus a `done` event.
- **Phase 13 LLM conversation summarization is active.** After successful tutor turns, `LLMConversationSummarizer` uses the versioned `conversation_summary.v1.md` prompt to summarize older visible user/assistant turns that have fallen outside the retained recent-turn window. Hidden tool calls/results and provider reasoning are excluded. Summary generation is bounded and idempotent by `turns_covered_to`; if the summary job fails, the successful tutor turn remains persisted.
- **Post-turn refinement is detached, not inline.** Both the conversation summary AND the tutor learner-state update run AFTER the `done` SSE event on a DETACHED background task (`TutorFollowupManager` / `run_tutor_followups`) that owns its OWN DB session built from the app sessionmaker. The request connection is released as soon as the stream finishes — the follow-up never pins a request DB connection while it makes its extra LLM call(s). This is safe because `persist_assistant_turn` commits every visible turn before `done`, so the background session reads fully-committed data. The route threads `session_factory` into `stream_chat_response`; when it is omitted (or the agent has no LLM client), the follow-up is skipped. `backend/app/main.py`'s lifespan owns clean shutdown via `tutor_followup_manager.shutdown()` (cancel + await) before `engine.dispose()`. Each step (summary, learner-state) is independently failure-isolated.
- **Tutor-driven learner-state updates are active (Phase 13.5d).** Learner state is mutated by TWO triggers: quiz grading (immutable-evidence trigger, `record_quiz_learning_evidence`) and the tutor conversation (conversational trigger, `maybe_update_learner_state_from_chat` + `LLMLearnerStateObserver` over `learner_state_update.v1.md`). The conversational pass runs in the same detached post-`done` follow-up task as the summary (no visible latency, no pinned request connection) and is failure-isolated. It is gated to run at most once every `LEARNER_STATE_UPDATE_INTERVAL` visible learner turns (default 4; `0` disables it) so it costs zero LLM calls on most turns; even when consulted, the observer returns `should_update=false` for ordinary turns and nothing is written. Forced JSON (`response_format=json_object` + `thinking=False`) and the observer fails CLOSED (no update) on parse/validation error. A positive observation merges demonstrated strengths, records revealed misconceptions as repair targets, drops `resolved` labels from misconceptions/repair targets, and updates `summary_text`/`updated_at`, while PRESERVING `last_quiz_attempt_id` (the tutor refines the mutable view but does not own the immutable quiz linkage). Tutor-sourced items are tagged `{"source": "tutor"}` and coexist with quiz-sourced items. The tutor reads `learner_state.summary_text` as `learner_state_summary` in its context.
- Regenerate reuses the latest visible user turn, deletes generated assistant/tool turns after it, and streams a replacement assistant turn. It does not append a duplicate user message or replay the replaced assistant answer.
- Editing a user message replaces the latest visible user turn in place (`replace_latest_user`): the backend updates that turn's content, deletes everything after it, and regenerates. The frontend drives this through the assistant-ui message edit composer (native branch + `runConfig.custom.replaceLatestUser`), so the edited turn replaces the original rather than appending a duplicate. The edit textarea matches the main composer's keys (Enter sends, Shift+Enter inserts a newline, Escape cancels).

## Tutor UI

- The tutor remains concept-scoped inside the concept side panel. Do not treat `AssistantModal` as the current tutor surface.
- The frontend uses `@assistant-ui/react` with a custom `LocalRuntime` adapter.
- Reopened chats rehydrate from `reasoning_parts` first and only fall back to flattened `reasoning` when structured parts are absent.
- The learner-facing reasoning UI defaults to a compact summary. Full trace is opt-in via the `Reasoning` toggle.
- The reasoning view preference is stored in `localStorage` as `colearni.reasoningView`.
- Current public reasoning part kinds are `status`, `thinking`, `tool_call`, and `tool_result`.
- True per-message source/citation parts and quote rendering are still deferred. The current tutor header only shows concept-level source chips.

## App Shell + Navigation (Phase 13.7)

Status: **wired and shipped**. The persistent app shell lives under the `apps/web/app/(app)` route group: `(app)/layout.tsx` renders `components/layout/Sidebar.tsx` (desktop) + `MobileNav.tsx` + `UserProfileChip.tsx`, and the routed destinations now resolve to real pages/data.

- Dashboard, Trails, Explore, Quizzes, Progress, Sources, Bookmarks, and Settings are wired.
- Explore is the cross-Trail discovery hub today: Trail Pack import CTA + cross-Trail concept search list. The workspace-level graph remains deferred to Phase 16.
- The old shared "coming soon" stub / scaffolding-typo placeholder pages have been replaced.
- Trails/Graph overlap RESOLUTION (locked): the per-Trail graph is a VIEW of a Trail at `/trails/[id]`, not a standalone destination. The duplicate "Graph" sidebar item and its `__never__` match-prefix hack are already gone; any future cross-Trail/workspace graph belongs under Explore (the Sigma.js-class surface), not a revived top-level "Graph". See `docs/REBUILD_PLAN.md` Phase 13.7 for the full surface wiring map.

## Quiz Variant

- Quiz cards are backend-owned and persisted in `quiz_drafts`, keyed by `(concept_id, quiz_type)`.
- Reopening an ungraded level-up or practice quiz returns the existing draft across devices/sessions.
- Clients can request a fresh card with `force_new: true`. The current UI uses this for explicit level-up retry.
- Quiz questions are mixed-format: `multiple_choice`, `multi_select`, `ordering`, `cloze`, `short_answer`, `long_answer`, and `code`. The submitted answer is always a single string: `multi_select`/`ordering` use newline-separated option/item lists, `cloze` uses newline-separated fill-ins (prompt blanks are `____`), `code` is monospace/multiline with Tab-indent. Grading is LLM-based for every type.
- Quiz prompts and grader feedback render Markdown + KaTeX (inline/fenced code and `$...$`/`$$...$$` math) via the shared `QuizMarkdown` renderer, so code and math questions display correctly.
- Questions also carry `difficulty`: `light`, `standard`, or `challenge`.
- `multiple_choice` questions include 3-4 options. `short_answer` and `long_answer` omit `options`.
- Older persisted `explain` / `apply` / `compare` question snapshots are normalized to `long_answer` on read.
- Grading stores the immutable quiz attempt, creates a `quiz_attempt_summaries` row, updates mutable `learner_states`, then clears the matching backend draft.
- Quiz generation receives bounded prior quiz context from attempt summaries so fresh cards avoid repeating exact prompts, especially prompts already answered correctly. The context includes labels, score bands, and prompt excerpts only — no learner answers or answer keys.
- Prior attempts can be revisited through `GET .../concepts/{concept_id}/quiz-attempts`; attempts are read-only immutable snapshots.
- When an ungraded quiz draft is active, the backend guards against learners extracting quiz answers in chat. Production turns fold this into the unified `classify_turn` decision (`blocks_active_quiz_answer`), which catches verbatim, paraphrased, AND follow-up extraction attempts using the conversation history. Verbatim copies are also short-circuited deterministically (exact-prompt match, no LLM call). Legacy agents without `classify_turn` fall back to the standalone semantic `quiz_answer_guard` (`quiz_guard.py`). All paths run backend-only and return a boolean; matched messages get a deterministic safe redirect before any answering LLM call (covering mastered concepts where `direct` would otherwise answer fully). Raw quiz prompts are only ever sent to the classifier/guard, never to the answering prompt, and never streamed; the guard fails open on parse/model errors.
- The frontend quiz panel shows a professional result report with Markdown/math-rendered prompts and feedback and explicit generation/grading progress copy. Past attempts now live in a dedicated **history tab** (`QuizHistoryPanel`, opened via "View past attempts") that only calls `GET .../quiz-attempts` and never triggers quiz generation; it supports All/Level-up/Practice filtering and per-attempt review. Shared attempt/feedback rendering lives in `quizShared.tsx`. The concept-panel action toolbar keeps Tutor/Practice/Level Up in stable positions across mastery states and adds a "View past attempts" entry. It does not stream raw quiz context to the learner.

## Concept Primer Variant (Phase 13.5a)

- Each concept can carry a short orientation **primer**: a one-paragraph `overview`, 3-6 `key_terms` (`term` + one-line `definition`), and 3-4 short `sample_questions` (<=90 chars) that power the chat welcome-screen suggestion chips.
- Primers are generated in a SEPARATE LLM pass (`concept_primer.v2.md`), never inlined into trail generation, to keep graph JSON lean on smaller models.
- **Single repair attempt.** Because primers explicitly target small/local models (which routinely emit the wrong count of key terms/sample questions or an over-long prompt), `LLMPrimerGenerator` mirrors the quiz generator: on a parse/validation failure it asks the model once for corrected JSON (`generator.repair(...)`) before giving up with `PrimerGenerationError`. Both the non-stream `generate` and the streamed generation route the parse through `_parse_or_repair_primer`; generators without a `repair` method surface the original error unchanged.
- The primer is cached on the concept inside `ConceptNode.metadata_json["primer"] = {"overview", "key_terms", "sample_questions", "version"}` (no migration; current cache `version` is `2`). Primers cached before `sample_questions` existed (version 1) still validate, defaulting `sample_questions` to `[]`.
- Generation is idempotent: `generate_concept_primer(..., force_new=False)` returns the cached primer WITHOUT calling the model; `force_new=True` regenerates and overwrites the cache.
- Endpoints:
  - `POST .../concepts/{concept_id}/primer` (optional body `{"force_new": true}`) returns the cached/generated primer.
  - `POST .../concepts/{concept_id}/primer/stream` streams generation over SSE for a live preview: a cache hit yields a single `done` event; a miss yields `status` (preparing) then cosmetic `thinking`/`token` preview events and a final authoritative `done` (or `error`). Only `token` chunks are parsed into the primer JSON; `thinking` is preview-only and never parsed.
- **Resilient, backend-driven generation (stream endpoint).** On a cache miss the stream endpoint detaches the actual generation from the request: it spawns a background task (`PrimerGenerationManager`) that owns its OWN DB session built from the app sessionmaker and commits the cached primer independently. The SSE response only *subscribes* to that background job for the live preview. If the learner navigates away, refreshes, or the connection drops mid-generation, only that subscription is cancelled — the background task runs to completion and persists the primer, so nothing is wasted and the next open is a cache hit. The request connection is released (`session.rollback()`) before subscribing, so streaming never pins a request DB connection.
  - The background task is created with `asyncio.create_task` and is NOT tied to the request. `backend/app/main.py`'s lifespan owns clean shutdown: it calls `primer_generation_manager.shutdown()` (cancel + await outstanding tasks) before `engine.dispose()` so no task or session leaks.
- **Single-flight dedup.** At most one in-flight detached generation per `concept_id`. Two near-simultaneous `primer/stream` opens share the same background task and therefore the SAME single model call: the manager keys an in-process registry by `concept_id` (in-process guard), and `_produce_primer_events` additionally takes a PostgreSQL `pg_advisory_xact_lock` (mirroring quiz drafts) as the cross-process boundary and re-checks the cache after acquiring it, so a primer produced by another worker is returned without a model call. The advisory lock is skipped on non-PostgreSQL (e.g. SQLite tests).
- The concept detail response (`GET .../concepts/{concept_id}`) returns `primer` when cached and `null` when absent. Generation is a calling-side decision (lazy on first open or a future bounded pre-generation loop); the detail GET never auto-generates.
- Primer content is abstract concept-level orientation, NOT source-derived, so it is export-eligible and needs no sanitizer changes.
- **Anti-hallucination grounding (prompt-level).** Because the primer pass receives NO source-existence signal (`_render_prompt` passes only topic/goal/concept fields, mastery labels, and neighbour titles — there is no `has_sources` variable), `concept_primer.v2.md` carries an *unconditionally safe* grounding rule: prefer conceptual framing over specific facts, and never state specific dates, counts, quantities, statistics, or proper-noun lists (e.g. exact track titles, release years) as fact unless supported by provided source material — hedge generally or omit instead of fabricating precise figures to sound authoritative. `concept_primer.v1.md` (retained per the versioning policy but not the rendered version — `PRIMER_VERSION = 2`) carries the same rule for consistency. If a source-context variable is ever threaded into `_render_prompt`, the rule can be made conditional-aware.

## Tutor-Suggested Quiz Cards (Phase 14)

Status: **shipped** (decisions LOCKED; backend + frontend implemented and tested). The contract below is authoritative.

- `suggest_quiz` is a REAL normalized provider tool registered through `backend/app/agents/provider_tools.py` (the same registration path as the retrieval tools), surfaced to the client as a new `suggest_quiz` SSE event. It is NOT an ad-hoc event bolted onto the stream.
- The tool is offered on EVERY tutor turn. Unlike the retrieval tools (gated on the concept having sources / a primer), `suggest_quiz` is never gated on sources.
- Tool args are exactly `quiz_type` (enum `level_up` | `practice`) and `reason` (short, learner-visible string). `concept_id` is NOT a model argument; the backend always scopes to the trusted current concept — the same pattern as `search_sources`, whose schema deliberately omits `concept_id`.
- Trigger is model-decided but mastery-aware via PROMPT guidance only (suggest `practice` anytime; suggest `level_up` only when mastery looks near-ready). There is NO hard backend mastery gate in v1.
- The CTA is opt-in: clicking it (never auto-open) reuses the existing backend-owned `quiz_drafts` generate/reuse path keyed by `(concept_id, quiz_type)`. No new quiz endpoint is added.
- The `reason` is persisted on the assistant turn's `reasoning_parts` under a NEW part kind `suggest_quiz` (joining the existing `status`, `thinking`, `tool_call`, `tool_result` kinds), so the CTA rehydrates on reload like the rest of the turn trace.
- Dedupe is layered: the backend `(concept_id, quiz_type)` uniqueness already guarantees a single draft, and the frontend collapses to a single active CTA per `quiz_type`.
- The tutor cannot grade or update mastery through this path — structurally enforced. `suggest_quiz` only emits an intent; grading and mastery updates stay in the quiz service.
- Two sibling suggestion tools follow the SAME opt-in, never-auto-act, every-turn pattern and persist their own `reasoning_parts` kind + SSE event: `suggest_flashcards` (kind `suggest_flashcards`, args `reason`) nudges the recall-first flashcards deck, and `suggest_artifact` (kind `suggest_artifact`, args `kind` + `reason`; Phase 15f) nudges an artifact build. Like `suggest_quiz`, neither generates, opens, nor persists anything — the learner clicks the CTA to act, and the backend stays the owner of generation/persistence/mastery. This is CTA-first today; a richer direct in-chat trigger flow is still WIP.

## Artifact Templates + Builder Sub-Agent (Phase 15)

Status: **15a–15f implemented + tested** (decisions LOCKED; Phase 15 is under active review/polish at time of writing). What is shipped in code:

- **15a** — artifacts table + migration `0014_artifacts` (+ `0015_artifact_kinds`), strict/lenient envelope schemas, workspace/trail-scoped list/retrieval endpoints, validated create-service, fail-closed export-gating helper, and a frontend `kind -> component` registry that degrades to `text_fallback` on any unknown kind / invalid data / render error. The artifact-builder SUB-AGENT (`backend/app/services/artifact_builder.py`), its bounded retrieval loop (`_run_builder_retrieval_loop`), one-repair-then-fail behaviour, `POST .../artifacts/build` + `POST .../artifacts/build/stream` (SSE), advisory-lock dedupe, and the detached `ArtifactGenerationManager` (own DB session, cancel-safe, lifespan teardown) are ALL implemented. Frontend `ArtifactsPanel` lists + generates via the SSE path.
- **15b** — pin system shipped (see below).
- **15c** — flashcards subsystem shipped, BACKEND + FRONTEND (see below).
- **15d** — `timeline` + `mini_graph` read-only templates implemented (schemas, registry renderers, fallback).
- **15e** — `simulation_slider` implemented as a CLOSED `sim_kind` enum with backend-owned `precomputed` oracle (`backend/app/services/simulations.py`) and trusted hardcoded client compute (`apps/web/lib/simulations.ts`).
- **15f** — tutor `suggest_artifact` tool wired (every turn, opt-in CTA, `reasoning_parts` kind `suggest_artifact`); see the Tutor-Suggested Quiz Cards section above for the shared suggestion-tool contract.

The original 15a-only status note has been superseded by this update. The old pinned-flashcard follow-up is closed; the remaining UX follow-up is the richer inline-in-chat trigger experience for `suggest_flashcards` / `suggest_artifact`, because the current implementation still lands as opt-in CTA actions that open the relevant panel/build flow.

Artifact foundation (15a):

- A new `artifacts` table: workspace-scoped, `concept_id` nullable, `trail_id` (artifacts are BOTH concept-attached AND trail-attached), discriminated `artifact_type`, a validated typed payload, `source_refs[]`, and advisory-lock dedupe mirroring `quiz_drafts`. List/retrieval endpoints + history UI — persisted and retrievable like past quizzes.
- Shared artifact ENVELOPE: `{ artifact_version, kind, title, caption?, text_fallback (REQUIRED), provenance{source_ids, visibility, citations[]}, data{kind-specific} }`. Strict Pydantic output schema (`extra="forbid"`) + a versioned lenient read schema, mirroring `ConceptPrimerOutput`/`ConceptPrimerRead`. Every payload carries a mandatory `text_fallback`.
- Frontend component REGISTRY (`kind -> component`) generalizing the existing `{type:"data", name}` dispatch, wrapped in an error boundary that degrades to `text_fallback` (like the existing Mermaid `catch -> textContent`). Unknown/invalid `kind` renders `text_fallback`.
- Export/provenance: concept-level (non-source-derived) artifacts stay LOCAL-ONLY like the primer (excluded from public Trail Pack export). Source-derived artifacts are public-export-eligible only if EVERY contributing source passes `_can_include_source_in_public_export` AND none is `user_upload` (all-or-nothing).
- First two read-only templates: `worked_example`, `comparison_card`.

Artifact-builder SUB-AGENT (15a):

- Exposed as a tool with its own specialised prompt + its own BOUNDED retrieval loop reusing the existing retrieval tools (`search_sources`, `read_document_section`, `get_graph_neighbourhood`, `get_concept_primer`) under the existing `tutor_tool_call_budget` (3). Structured JSON output + exactly ONE repair attempt, then fail.
- The BACKEND owns generation, IDs, citations, persistence, and provenance/export gating; the model returns a validated payload only. Every citation must map to a real retrieved `source_revision_id` or be dropped. On-demand only; returns a reference, not a blob through chat.
- Rationale: small/local LLMs cannot juggle tutoring + retrieval + per-template JSON in one context. This is the orchestrator-worker pattern kept as a small direct-provider adapter, NOT an agent framework.

Background/detached generation (15a):

- Generation runs detached with LIVE status in chat (shimmer / SSE status events) and CONTINUES if the learner leaves/refreshes — mirroring the existing `PrimerGenerationManager` pattern: own DB session from the app sessionmaker, cancel-safe, single-flight per target, lifespan shutdown owns clean teardown. The SSE response only subscribes; the background task persists independently.

Pin system (15b):

- SHIPPED: polymorphic `pins` table `(id, workspace_id, trail_id, item_type, item_id, pinned_at)` + migration `0016_pins`, `item_type in {artifact, quiz_attempt}`, with a CHECK on `item_type` and a UNIQUE constraint on `(workspace_id, trail_id, item_type, item_id)` enforcing IDEMPOTENT pinning (one row per item). Thin pin/unpin/list routes (`backend/app/api/pins.py`) over a service (`backend/app/services/pins.py`); pin/unpin are idempotent and validate the referenced item belongs to the same workspace+trail (no cross-trail/cross-workspace pins). `GET .../pins` aggregates `{artifacts: [ArtifactRead], quiz_attempts: [QuizAttemptRead]}` scoped to the trail.
- Frontend: a reusable `PinToggle` Save/Saved control on each artifact (`ArtifactsPanel`) and each quiz attempt (`quizShared`/`QuizHistoryPanel`); the workspace-level Bookmarks page (`/bookmarks`) is a per-Trail-grouped "Saved" surface that iterates the workspace's own Trails (bounded: one `listPins` per Trail, no recursion) and renders pinned artifacts via `ArtifactRenderer` and pinned attempts via the shared quiz-attempt list. Per-USER == per-workspace for now (becomes user-scoped when auth lands).
- NOTE: concept/source "pinning" as a retrieval/recommendation PRIORITISATION weight is a DIFFERENT, deferred mechanism (see `docs/REBUILD_PLAN.md` → Future Exploration / Backlog).

Flashcards subsystem (15c, DEDICATED — not a generic artifact):

- BACKEND SHIPPED: tables `flashcard_decks` + `flashcards` (one deck per concept; UNIQUE `(workspace_id, concept_id)`) + migration `0017_flashcards`. 4 thin routes (`backend/app/api/flashcards.py`, registered in `backend/app/main.py`): `POST .../concepts/{concept_id}/flashcards/generate` (extend/force flags, idempotent default), `GET .../flashcards`, `POST .../flashcards/{card_id}/review` (`{recalled}`), `GET .../flashcards/export?format=csv|json`. Logic lives in services (`flashcards.py` generation + review, `flashcard_scheduler.py` Leitner, `flashcard_export.py`). Pin integration via the `flashcard` `item_type` (deck id is the pinnable unit; aggregated under `flashcards` in `GET .../pins`).
- FRONTEND SHIPPED: typed API helpers (`getFlashcards`, `generateFlashcards`, `reviewFlashcard`, `flashcardsExportUrl` in `lib/api.ts`; `Flashcard`/`FlashcardDeck`/`FlashcardGenerateResponse` in `lib/types.ts`). `FlashcardsPanel.tsx` opens from the concept action row ("Flashcards" button, mirroring "Artifacts"; footer hidden while open like `artifactsOpen`/`quizMode`). Empty state shows a "Generate flashcards" CTA; on `exhausted` with no new cards it shows the returned `reason` as a friendly decline. RECALL-FIRST review: one card FRONT at a time, answer hidden until "Show answer", then binary "Got it" (recalled=true) / "Missed it" (recalled=false) calls `reviewFlashcard` and advances the due-first session queue (progress `n / total`, box/reps shown subtly; keyboard space=reveal, y/n=grade). "Generate more" extends the deck, an Export CSV/JSON menu uses the export URL, and a `PinToggle` (`item_type: flashcard`) pins the deck. Errors degrade with a message + Retry. Tested in `__tests__/FlashcardsPanel.test.tsx` + a ConceptPanel open/back test.
- Canonical relational/JSON store (`flashcard_decks` + `flashcards`); CSV is Anki-compatible export only, plus JSON export. CSV is NOT the source of truth.
- Card schema: `front`, `back`, `hint`, `source_ref`, `card_type (basic|cloze|reverse)` + scheduling state `{box, interval_days, last_reviewed, due, reps, lapses}`.
- Scheduling v1 = LEITNER (5–6 boxes, geometric intervals e.g. 1/3/7/16/35 days), recall-first swipe yes/no: yes => box+1 (capped), no => box 1 (`lapses++`). Schema is FSRS-ready; v1 logic is Leitner.
- Generation is source-grounded, atomic, dedup-aware and RETURNS `{cards, exhausted: bool, reason}` so it can decline instead of padding garbage. Every card's `source_ref` must map to a real retrieved `source_revision_id` or the card is dropped (the model can never invent a citation); a deterministic embedding-similarity gate drops paraphrase-duplicates. Cap ~3–8 cards/concept; deck soft-cap. Card-writing rules baked into the prompt (`flashcard_generation.v1.md`): one fact/card, specific & unambiguous, no yes/no fronts, answer not inferable, cloze-one-blank for lists, add why/how cards, self-contained, source-grounded only, no duplicates, STOP when exhausted.
- Incremental extension feeds existing card FRONTS back as exclusion context + a deterministic embedding-similarity gate to drop paraphrase-duplicates. Optional: bias new cards toward weak sub-areas using the learner's repeated-"no" struggle signal (distinct from dedup).
- Pinnable + retrievable like quizzes. Pedagogy basis: Wozniak "Twenty rules", Matuschak "How to write good prompts", Leitner/SM-2/FSRS, Bjork.

Interactive simulation slider (15e, `sim_kind`-enum approach):

- A CLOSED ENUM of trusted `sim_kind`s (e.g. `linear`, `quadratic`, `exponential`, `supply_demand`), each backed by a HARDCODED, vetted, unit-tested compute+render function in the frontend registry. The LLM emits a validated data payload only — chosen `sim_kind` + named coefficients within validated finite ranges + axis labels + <=3 parameters + a predict-then-check `prompt` — NEVER code or a formula string.
- The BACKEND pre-computes baseline sample points and validates ranges (finite, no NaN, bounded `y`), shipping `precomputed.{at_defaults, y_bounds}` as render hint + validation oracle. Client live-eval on slider drag uses the trusted hardcoded function clamped to `y_bounds`, else degrades to the static plot / `text_fallback`. NO arbitrary JS, NO browser-side mathjs. Arbitrary-formula sims are a future backend jsep-whitelist path only.
- Remaining read-only templates (15d): `timeline`, `mini_graph` (reuses Mermaid strict-mode / `@xyflow`).

Tutor integration (15f):

- SHIPPED: the tutor emits a `suggest_artifact` opt-in suggestion (every turn, not gated on sources), surfaced as a `suggest_artifact` SSE event + `reasoning_parts` kind and rendered as an opt-in CTA. Args are `kind` (the artifact `ArtifactKind` enum) + a learner-visible `reason`; the build only runs on CTA click through the backend-owned `/artifacts/build(/stream)` path. Sequenced after Phase 14 as planned so the two suggestion mechanisms were not stood up at once.

## Graph Generation Variant

- Trail/graph generation currently uses a single structured **JSON** completion (`trail_generation.v1.md`), parsed and validated with one repair attempt. This is the default path.
- Decision (from local-model testing): JSON output is the default and the only supported path for smaller/older and locally-hosted models. In testing, such models reliably produce one JSON object but struggle with multi/parallel tool calls (e.g. emitting `add_node` calls across turns, or stopping after reasoning), which produces malformed or incomplete graphs.
- Planned (not yet implemented): an optional **tool-call generation mode** behind a capability toggle, used only for large hosted models that reliably emit parallel tool calls. The toggle must default to JSON; tool-call mode is opt-in per provider/model. This is recorded here so the future toggle is a calling-side switch, not a rewrite of the JSON path.

## Graph Recommendations

- The frontend consumes `GET /api/workspaces/{workspace_id}/trails/{trail_id}/next` for dashboard and Trail-detail recommended-next UI.
- The client-side duplicate recommendation heuristic has been removed; `summarizeTrail` only computes progress, mastery counts, and last activity.

## Duplicate-Request Protection

- The frontend `QuizPanel` dedupes in-flight generation requests so StrictMode/dev effect replay does not create duplicate generation calls.
- The backend is the real safety boundary: PostgreSQL `pg_advisory_xact_lock` serializes draft creation per `(concept_id, quiz_type)`.
- If duplicate inserts still race, the service rolls back, reloads the existing draft, and returns it.

## Migration Rule

- Alembic revision ids must fit `alembic_version.version_num` (`VARCHAR(32)`).
- Current example:
  - file: `backend/alembic/versions/0012_trail_prior_knowledge.py`
  - revision: `0012_trail_prior_knowledge` (down_revision `0011_source_chunks`)

## Retrieval Tool Calling Loop

The LLM multi-turn retrieval tool calling loop is **implemented**. The loop functions
(`_run_retrieval_loop`, `execute_retrieval_tool`) live in `backend/app/services/conversations.py`,
but the orchestration that invokes them (`stream_chat_response`, `prepare_mode`/`stream_text`) lives
in `backend/app/services/tutor.py`.

Key design decisions:

- **Two-phase tutor turn**: `prepare_mode()` runs the first LLM call (mode selection only) and returns a `_ModePreparation` bundle. `stream_chat_response` then runs the retrieval loop (between the two LLM calls). If the retrieval planner emits no tool calls but does emit text, that text is reused as the final answer to avoid a duplicate no-tool final call. If retrieval tools are used, `stream_text()` runs the second LLM call with enriched context so the LLM sees retrieved content in its final response.
- **Budget**: the per-turn tool-call budget (`settings.tutor_tool_call_budget`, default 3) counts individual tool calls per turn. A single LLM response returning 2 calls costs 2 against the budget, including duplicate calls served from the per-turn cache.
- **Sequential execution (shared session)**: the tool calls from one LLM response are dispatched SEQUENTIALLY against the request's single `AsyncSession`. A single asyncpg connection cannot run concurrent operations, so dispatching them with `asyncio.gather` corrupted the in-flight transaction (`InFailedSQLTransactionError`) whenever the model emitted >1 tool call — which then aborted the subsequent commit (e.g. `create_artifact`). Retrieval is read-only and the budget is tiny, so the latency cost of sequential dispatch is negligible. The same fix applies to the artifact-builder retrieval loop (`_run_builder_retrieval_loop`).
- **Text-emitted tool-call recovery**: small/local models (e.g. `deepseek-v4-flash`) sometimes ignore the native tool-call channel and print a `<functioncall>{...}</functioncall>` block (or a bare `{"name": ..., "arguments": {...}}` object) directly in the text. `parse_text_tool_calls`/`strip_text_tool_calls` (in `provider_tools.py`) recover any VALID calls whose name matches an offered tool (so retrieval and the `suggest_quiz`/`suggest_artifact` CTAs still fire) and strip the raw block so it never leaks to the learner as the visible answer. Applied in both the tutor loop and the artifact-builder loop.
- **Deduplication**: duplicate calls (same name + args) within a turn return the cached result without re-executing, but are still appended back to the tool-round transcript with their original call IDs.
- **Per-result cap**: `settings.tutor_max_tool_result_chars` (default 2000). Truncated results include a count suffix.
- **Mode-selection (first pass)**: the classifier call uses a small dedicated token cap (`settings.tutor_mode_selection_max_tokens`, default 48) and requests provider reasoning only when `settings.tutor_mode_selection_thinking` is true (default false). Prompt context retains the latest `settings.tutor_recent_visible_turns_limit` visible turns (default 10) plus tool turns in that window.
- **Tool offer condition**: the retrieval loop runs when there is a usable LLM client AND the concept has at least one linked source OR a cached primer. The offered tool list is scoped via `select_retrieval_tools(has_sources, has_primer)`: source tools (`search_sources`, `read_document_section`, `get_concept_sources`) only when sources exist, `get_concept_primer` only when a primer is cached, and `get_graph_neighbourhood` whenever the loop runs. The opening-turn primer auto-injection is unchanged; on later turns the primer reaches the model only through `get_concept_primer`.
- **Concept scoping**: retrieval is scoped to the concept being tutored. `search_sources_by_text` accepts `concept_id` and JOINs `ConceptSourceLink` when provided; the `search_sources` dispatcher always passes the trusted current concept (the tool schema deliberately does not expose a `concept_id` argument).
- **Two retrieval tools**:
  - `search_sources` → dispatches to `search_sources_by_text` returning `ChunkSearchResult` objects with `line_start`/`line_end` navigation metadata.
  - `read_document_section` → reads lines from `SourceRevision.raw_text` (markdown), scoped to workspace.
  - `get_concept_sources` and `get_graph_neighbourhood` are also registered and dispatched in `execute_retrieval_tool`, defaulting to the current concept when `concept_id` is omitted.
  - `get_concept_primer` returns the cached concept primer (overview + key terms + sample questions) via a read-only `read_cached_primer` lookup, defaulting to the current concept. It never triggers generation; when no primer is cached it returns a short "no primer available yet" result.

## Deferred Work

- `open_source_chunk`: superseded by `read_document_section` (intentionally not implemented).
- True per-message citation/source parts and quotes.
- Global cross-Trail assistant surfaces.
- Guided graph focus controls.

## Update Rule

When implementation changes any item above, update this file and the affected contract docs in the same change.
