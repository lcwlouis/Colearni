# Drift Report

As of 2026-03-02.

This report compares three baselines against a full top-to-bottom audit of the codebase (60 domain files, 97 test files, 48+ API endpoints, 5 frontend pages, 9 migrations, 16 prompt assets, 124 env vars):

1. The original project description in the thread request.
2. The planning discussion in `tmp/pdfs/branch_colearni_discussion.txt`.
3. The current implementation in the repo.

Previous report: 2026-02-28.

---

## Executive Summary

Since the last report (2026-02-28), the project has made meaningful forward progress in several areas — research planning, learner profiles, concept tiers, document lifecycle tracking, and streaming — while the core tutor/graph/quiz product remains stable and well-built.

However, the overall strategic drift pattern has not changed:

- The pedagogy + graph + quiz core is **production-grade and architecturally sound**.
- The research/discovery layer has progressed from "mostly missing" to **early scaffolding** (topic planner, query planner, promotion logic, 38 tests) — but is still not user-facing or agentic.
- The learner profile has moved from "fragmented" to **partially assembled** (`domain/learner/` exists with profile assembly and activity state) — but is not yet a living, auto-updating model.
- The conductor/router has moved from "conceptual" to **in-progress** (typed `TurnPlan`, query analyzer) — but is not yet wired into the runtime.

The product today remains:

> "Graph-backed Socratic tutor with mastery-gated quizzes and practice over user-uploaded materials"

The original "agentic second brain" vision is still mostly unrealized, though the building blocks are now closer.

---

## Bottom-Line Assessment

| Baseline | Alignment (prev) | Alignment (now) | Change | Summary |
| --- | --- | --- | --- | --- |
| Original broad vision | 35–45% | 40–50% | ↑ ~5pp | Research planner, learner profile assembly, concept tiers landed. Still no user-facing discovery, no deep-search synthesis, no living user model. |
| Planning discussion | 70–80% | 75–85% | ↑ ~5pp | Research scaffolding, document lifecycle, streaming, learner digests added. Conductor still not wired. |
| Current docs (`ARCHITECTURE.md` + `PRODUCT_SPEC.md`) | 75–85% | 80–88% | ↑ ~3pp | ARCHITECTURE.md status note is now accurate. GRAPH.md has column-name errors. Streaming status UI still missing despite spec. |

These remain directional estimates.

---

## Current State Snapshot

The codebase is substantial: **60 domain files**, **48+ API endpoints**, **97 test files (~650 tests)**, **16 versioned prompt assets**, a **5-page Next.js app** with Sigma.js graph, and **9 Alembic migrations**.

### What exists and works

- Auth + multi-workspace support (magic links, workspace members).
- Knowledge-base upload, reprocessing, and per-document lifecycle tracking (`ingestion_status`, `graph_status`, `graph_concept_count`).
- Ingestion for `.txt`, `.md`, `.pdf` with word/char-based chunking and paragraph-aware splitting.
- Chunking, embeddings (OpenAI / LiteLLM / Mock), and hybrid retrieval (pgvector cosine + Postgres FTS).
- Raw + canonical concept graph with online resolver (budgeted), offline gardener (budgeted), and orphan pruning.
- Concept tier taxonomy (`umbrella | topic | subtopic | granular`) in schema and graph extraction.
- Chat tutor with evidence/citations, strict vs hybrid grounding, and streaming SSE.
- Mastery-gated Socratic/direct response style switching.
- Level-up quiz generation, mixed grading (MCQ deterministic + short-answer LLM rubric), mastery update.
- Practice quizzes and unified flashcard stacks with exhaustion tracking and quiz history with retry.
- Graph explorer with Sigma.js WebGL rendering, ForceAtlas2 layout, MiniSearch, expand/prune controls.
- "I'm feeling lucky" graph traversal (bounded topology-based selection).
- Readiness analyzer with half-life decay.
- Onboarding confirmation step.
- Dev stats toggle (localStorage, client-side).
- File-based prompt asset system (`core/prompting/`) with 16 versioned assets across 7 task families.
- Comprehensive observability (OpenTelemetry + optional Phoenix, 400+ lines in `core/observability.py`).
- Learner profile assembly (`domain/learner/`) — activity state and profile data gathered but not yet a living model.
- Query analyzer and typed turn plan (`domain/chat/query_analyzer.py`, `domain/chat/turn_plan.py`) — implemented and tested (22 + 14 tests) but not yet wired into the runtime conductor.
- Research subsystem with topic planner, query planner, source management, candidate promotion, and background runner — tested (38 tests) but not user-facing.
- Learner digest background job.
- Spaced repetition scaffold (`domain/learning/spaced_repetition.py`) — minimal, appears incomplete.

### What does not exist

- No user-facing research discovery UI or agentic search loop.
- No periodic synthesis ("everything I've learned") surface.
- No living user model that auto-consolidates preferences, goals, interests.
- No deep-search agent.
- No conductor/router wired at runtime (still functional if/else orchestration in `respond.py`).
- No SuggestionAgent (deferred; prompt asset `suggestion_hook_v1` exists but no agent).
- No streaming status ticker visible in the chat UI (types exist, display missing).
- No grounding-mode toggle in the frontend UI.
- No E2E pipeline tests.

---

## Where The App Matches The Plan Well

### 1. Learning-first, anti-brainrot tutor

**Status: Strong. Production-grade.**

The tutor pipeline (`domain/chat/respond.py` → `tutor_agent.py` → `verifier.py`) implements the full Socratic/direct gating loop with evidence/citation verification. The prompt asset system (`core/prompting/assets/tutor/`) provides versioned Socratic and direct-mode templates. Social-intent fast-path (`domain/chat/social_turns.py`) handles greetings without wasting retrieval budget.

The streaming path (`POST /chat/respond/stream`) uses proper SSE with feature-flag gating and event counting.

Grounding policy enforcement is strict: `verify_assistant_draft()` validates citation labels against evidence source types, refuses on insufficient evidence in strict mode, and returns structured refusal reasons.

**Concern:** The verifier validates citation *structure* (labels, IDs, source types) but does not check citation *semantic overlap* with the response text. LLM hallucinations that correctly format citations but don't actually ground in the cited evidence would pass verification. This is a real product risk at scale.

### 2. Graph-backed learning model

**Status: Strong. Well-budgeted. Improved since last report.**

The two-layer graph (raw → canonical) with online resolver and offline gardener is mature. Budget enforcement is present throughout: `ResolverBudgets` (lexical, vector, LLM calls per chunk/doc), `GardenerConfig` (max LLM calls, clusters, dirty nodes per run). No unbounded loops detected anywhere in `domain/graph/`.

New since last report: concept tier taxonomy (`umbrella | topic | subtopic | granular`) landed in migration 0009 with a workspace+tier index. Orphan pruning (`domain/graph/orphan_pruner.py`) cleans up disconnected nodes after document deletion.

The resolver pipeline is well-decomposed: `resolver.py` → `resolver_candidates.py` → `resolver_decision.py` → `resolver_apply.py`.

**Concern:** `docs/GRAPH.md` has incorrect column names. It says `src_concept_id`/`tgt_concept_id` (edges) and `from_concept_id`/`to_concept_id` (merge log), but the actual schema uses `src_id`/`tgt_id` and `from_id`/`to_id`. Any developer reading the docs will write code against nonexistent columns.

**Concern:** `GRAPH.md` recommends `pg_trgm` similarity indexes on `canonical_name` and aliases for lexical blocking (candidate generation), but no migration creates these indexes. This means lexical blocking may degrade as graph size grows.

### 3. Quiz, mastery, and practice loops

**Status: Strong. Materially complete. Well-tested.**

Quiz logic is well-decomposed: `quiz_flow.py` (shared orchestration), `quiz_generation.py` (item diversity, validation, 16 defs), `quiz_grading.py` (MCQ deterministic + SA rubric, 11 defs), `quiz_persistence.py` (DB ops, 17 defs). Practice has novelty deduplication via `practice_novelty.py` fingerprinting. Unified flashcard stacks with exhaustion tracking implemented in both backend and frontend.

Practice submissions are idempotent on replay. Generation retries capped at 3 attempts. Practice never mutates mastery state (product spec compliance).

**17 backend tests + 5 DB integration tests** covering flows.

### 4. Thin-route, Postgres-first implementation style

**Status: Mostly strong. Two violations found.**

48+ API endpoints across 13 route files. The vast majority (85%) follow the thin-route pattern: validate Pydantic input → call domain function → return response.

**Violation 1:** `apps/api/routes/readiness.py` executes raw SQL directly in the route handler, including joins and column transformations. This is business logic that belongs in `domain/readiness/`.

**Violation 2:** `apps/api/routes/documents.py` contains multipart payload parsing logic (`_read_upload_payload()`) that belongs in `adapters/parsers/`.

These are not showstoppers but they violate the CODEX.md golden rules and should be refactored.

---

## Where The Project Has Drifted Most From The Original Vision

### 1. Search-first topic discovery: scaffolded, not delivered

**Previous assessment: "mostly missing". Updated: early scaffolding exists.**

The research subsystem has progressed since the last report:

- Topic planner (`domain/research/topic_planner.py`) — generates subtopic proposals from a goal. 16 tests.
- Query planner — generates search queries. Tested.
- Source management — CRUD for research sources. 11 API routes.
- Candidate promotion — decides which candidates to ingest. 12 tests.
- Research runner — background job for execution. Exists.

However, this is still **internal plumbing, not a user-facing product loop**:

- No UI for research discovery or topic exploration.
- No human-in-the-loop approval flow visible in the frontend.
- No periodic/automatic topic expansion.
- No web-scale search orchestration.
- The research runner lacks explicit budget enforcement (unlike the graph gardener).
- 11 API routes exist but no frontend consumes them.

**Drift from original:** Still high, but the gap is narrowing. The building blocks are testable; the product surface is not.

### 2. The learner model: partially assembled, not living

**Previous assessment: "fragmented". Updated: assembly started.**

New since last report:

- `domain/learner/` exists with 2 files: profile assembly and activity state.
- Learner profile assembler has **17 tests** — it gathers mastery, readiness, activity data.
- Learner digests (migration 0008) provide background-job-generated summaries.
- `user_tutor_profile` in the auth system provides `readiness_summary`, `learning_style_notes`, `last_activity_at`.

What is still missing:

- No single canonical learner profile object that consolidates everything.
- No automatic updater that evolves the profile based on user behavior.
- No preference/interest/goal tracking.
- The assembled data is used for context injection but not surfaced as a user-visible model.

**Drift from original:** Still high, but the data plumbing is closer. The *product behavior* (a living, evolving learner model that users can see and the system uses to personalize proactively) does not exist.

### 3. Deep-search / second-brain synthesis: still absent

No progress here since the last report. No deep-search agent, no "everything I've learned" synthesis, no periodic external update pipeline.

The learner digest job is the closest thing, but it's a background job output stored in a table — not a user-facing synthesis surface.

**Drift from original:** High. Unchanged.

---

## Where The Docs And The App Have Drifted From Each Other

### 1. ARCHITECTURE.md: moderately accurate, one stale claim fixed

The status note added at the top of ARCHITECTURE.md (lines 26–32) now correctly describes the current state: "functional orchestration modules rather than hard agent boundaries" with typed turn planning as the next target.

However:

- The Mermaid diagram still shows `SuggestionAgent` as a first-class component. No SuggestionAgent exists in code (only a prompt asset `suggestion_hook_v1`).
- The ingestion pipeline diagram shows `.md/.txt` only. PDF is supported and has been for weeks.
- The repo structure section lists `adapters/retrieval/` but retrieval lives in `domain/retrieval/` — an architectural divergence that is neither documented nor justified.

### 2. GRAPH.md: column-name errors

`docs/GRAPH.md` uses `src_concept_id`/`tgt_concept_id` (line 69) and `from_concept_id`/`to_concept_id` (line 100). The actual schema (migration 0001) uses `src_id`/`tgt_id` and `from_id`/`to_id`. This is a documentation bug that will trip up any developer or AI agent writing graph queries.

### 3. PRODUCT_SPEC.md vs frontend: streaming status gap

PRODUCT_SPEC.md §8 specifies streaming status as a "replace-mode" indicator showing steps like "Retrieving evidence…", "Composing response…". The backend emits `ChatPhase` and `ActivityStep` types. The frontend defines `ACTIVITY_LABELS` and has `stream-messages.ts` for delta appending.

But the **visible streaming status ticker does not exist in the UI**. The types are defined; the display is not wired. This is a spec feature that appears implemented to anyone reading the code, but is invisible to users.

### 4. PRODUCT_SPEC.md vs frontend: grounding-mode toggle

The spec describes a strict/hybrid grounding toggle. The backend supports it (`default_grounding_mode` setting, `verify_assistant_draft()` policy). The frontend displays the grounding mode label in `chat-response.tsx` — but there is **no user-facing toggle** to switch modes. It's config-only.

### 5. Retrieval layer location mismatch

ARCHITECTURE.md shows `adapters/retrieval/` in the repo structure. The actual implementation lives in `domain/retrieval/` (`hybrid_retriever.py`, `vector_retriever.py`, `fts_retriever.py`, `evidence_planner.py`). The low-level DB queries (`vector_top_k()`, `full_text_top_k()`) are correctly in `adapters/db/chunks_repository.py`, but the retrieval orchestration logic sits in `domain/` rather than `adapters/`.

This is arguably fine (retrieval orchestration is domain logic), but the docs should reflect reality.

### 6. FRONTEND.md: mostly accurate, underdocuments feature components

The shared component inventory in FRONTEND.md is accurate. However, the `features/` directory has grown significantly (graph detail panel, flashcard stack, quiz history/viewer, tutor timeline, concept-chat links, KB upload queue, sidebar) and these are not cataloged in FRONTEND.md.

---

## Code Quality & Hygiene Assessment

This section is new. The previous report focused on product drift. A constructive drift report should also audit engineering quality.

### Strengths

1. **Zero TODO/FIXME/HACK comments** across 60+ domain files and all route handlers. The codebase is either genuinely clean or someone is rigorous about not leaving breadcrumbs.

2. **Budget enforcement is real, not aspirational.** The resolver, gardener, practice generation, and research candidate limits all have explicit caps with hard stops. No unbounded loops found anywhere in `domain/`.

3. **No cross-layer import violations.** `core/` and `domain/` never import from `apps/`. Verified across entire codebase.

4. **Type safety is strong.** Pydantic models for all API payloads, Protocol-based contracts in `core/contracts.py`, custom exception hierarchies (`QuizValidationError`, `QuizGradingError`, `ChatNotFoundError`), and consistent use of dataclasses for configuration objects.

5. **Prompt system is well-designed.** File-based assets with YAML front-matter, strict placeholder validation (no silent failures), caching, and metadata export for observability. 16 assets across 7 task families.

6. **Test suite is substantial.** 97 files, ~650 tests, covering all major domain areas. Evidence planner alone has 57 tests. Research planner has 38. Chat/tutor commands have 44.

7. **Observability is comprehensive.** 400+ lines in `core/observability.py` with OpenTelemetry semantic conventions, Phoenix integration, token/cost tracking, content recording toggle, and span sanitization.

### Weaknesses

1. **Test coverage is uneven.** Graph resolver: 7 tests. Graph gardener: 7 tests (+ 1 integration). Verifier: 6 tests. These are critical-path components that deserve 3–5x more coverage, especially for edge cases (disambiguation conflicts, budget exhaustion mid-merge, concurrent gardener runs).

2. **No E2E pipeline tests exist.** There is no test that exercises the full `upload → chunk → embed → store → ask question → retrieve → tutor response → verify citations` loop. Unit tests are strong; the integration seams between layers are undertested.

3. **Settings bloat.** `core/settings.py` has 60+ configuration fields in a single flat `Settings` class. This works but makes it hard to understand which settings belong to which subsystem. Logical grouping (e.g., nested Pydantic models for `GraphSettings`, `RetrievalSettings`, `ReasoningSettings`) would improve maintainability.

4. **Verifier scope is narrow.** `verify_assistant_draft()` validates citation *structure* but not *semantic correctness*. It cannot detect a response that formats citations correctly but hallucinates content not present in the cited evidence. For a product that emphasizes "evidence-first" and "grounded answers", this is a meaningful gap.

5. **Dead code risk.** Several small modules may be unused: `domain/chat/social_turns.py` (1 function), `domain/chat/answer_parts.py` (1 function), `domain/chat/title_gen.py` (2 functions), `domain/learning/spaced_repetition.py` (3 functions, appears incomplete). These should be audited for actual call paths.

6. **Readiness route violates thin-route rule.** `apps/api/routes/readiness.py` executes raw SQL with joins and column transformations directly in the route handler. This is the most visible CODEX.md violation in the codebase.

7. **Job budget inconsistency.** The graph gardener job has explicit CLI budget args. The readiness analyzer iterates all (workspace, user) pairs without a cap. The research runner has no documented budget constraints. Per CODEX.md rule 5, all agent/job loops must obey explicit budgets.

8. **Missing pg_trgm index.** GRAPH.md recommends trigram similarity indexes for lexical blocking in the resolver. No migration creates them. As graph size grows, candidate generation will slow down.

---

## Drift Matrix By Feature Area (Updated)

| Area | Original vision | Planning discussion | Current app | Drift vs original | Change since 2026-02-28 |
| --- | --- | --- | --- | --- | --- |
| Grounded tutor | Important | Core MVP | Implemented + streaming | Low | Stable |
| Socratic gating | Important | Core MVP | Implemented | Low | Stable |
| Level-up quiz progression | Important | Core MVP | Implemented + quiz flow decomposition | Low | Stable |
| Practice from graph nodes | Mentioned later | Core MVP | Implemented + novelty dedup + exhaustion | Low | Improved |
| Unified flashcard stack | Not mentioned | Specified later | Implemented (frontend + backend) | Low | Improved |
| Quiz history with retry | Not mentioned | Specified later | Implemented | Low | New |
| Raw + canonical graph | Not explicit | Core MVP | Implemented + concept tiers + orphan pruning | Low | Improved |
| Concept tier taxonomy | Not mentioned | Emerged later | Schema landed, extraction partial | Low–Moderate | New |
| Multi-workspace Postgres app | Not central | Strongly emphasized | Implemented | Low | Stable |
| Document lifecycle tracking | Not mentioned | Implied | Implemented (ingestion_status, graph_status, summaries) | Low | New |
| File-based prompt assets | Not mentioned | Emerged later | 16 assets, 7 task families, versioned | Low | Stable |
| Observability | Not mentioned | Desired | Comprehensive (OTel + Phoenix + tracing) | Low | Stable |
| Topic finder agent | Core idea | Deprioritized | Topic planner exists (16 tests), not user-facing | High | Improved (was missing) |
| Knowledge finder / search agent | Core idea | Deprioritized | Query planner + source CRUD exists, not user-facing | High | Improved (was missing) |
| User config / learner model | Core idea | Partial | Profile assembler + learner digests, not living model | High | Improved (was fragmented) |
| Periodic deep-search synthesis | Core idea | Desired | Missing | High | Unchanged |
| External source discovery | Core idea | Deprioritized | Research scaffolding (11 routes, 38 tests), no UI | High | Improved |
| Conductor / router | Implied | Emphasized | TurnPlan + QueryAnalyzer exist, not wired | Moderate | Improved (was conceptual) |
| SuggestionAgent | Implied | In architecture diagram | Prompt asset exists, no agent | Moderate | Unchanged |
| Streaming status UI | Not mentioned | Specified in PRODUCT_SPEC | Types exist, visible display missing | Moderate | Gap identified |
| Grounding mode toggle UI | Not mentioned | Specified in PRODUCT_SPEC | Backend supports it, no frontend toggle | Moderate | Gap identified |
| Spaced repetition | Mentioned (phase 2) | Non-goal for MVP | Minimal scaffold, appears incomplete | Low (expected) | New scaffold |
| PDF support | Desired | Deferred | Implemented | Positive drift | Stable |
| Web UI | Optional | Optional/later | 5 pages, Sigma.js graph, rich feature components | Positive drift | Stable |

---

## Most Important Product Reframe

The same reframe from the previous report still applies:

- **Original:** "agentic learning copilot and second brain that actively finds and curates new knowledge"
- **Current:** "grounded learning workspace over user-uploaded material, with graph-backed tutoring and mastery workflows"

What has changed since the last report is that **the bridge between these two visions is now partially built**. The research planner, query planner, candidate promotion logic, and learner profile assembler are real code with real tests. They are just not connected to users yet.

The strategic question remains the same but is now more urgent, because the scaffolding exists:

- **Commit to Phase 1:** Polish the learning workspace (fix streaming UI, grounding toggle, conductor wiring, test coverage) and ship it as a standalone product.
- **Open Phase 2:** Wire the research planner into a user-facing discovery loop, build the learner profile surface, and add synthesis — using the scaffolding that already exists.

Doing both simultaneously risks both. The codebase is clean enough to support either path, but not both paths at once without more test coverage and a real conductor.

---

## Specific Findings Requiring Action

### Documentation bugs (fix immediately)

1. **GRAPH.md column names** — Lines 69 and 100 use `src_concept_id`/`tgt_concept_id` and `from_concept_id`/`to_concept_id`. Actual schema: `src_id`/`tgt_id`, `from_id`/`to_id`.
2. **ARCHITECTURE.md ingestion diagram** — Shows `.md/.txt` only; PDF is supported.
3. **ARCHITECTURE.md repo structure** — Lists `adapters/retrieval/`; retrieval is in `domain/retrieval/`.
4. **ARCHITECTURE.md Mermaid diagram** — Shows `SuggestionAgent`; no agent exists.

### CODEX.md violations (fix soon)

5. **readiness.py route** — Raw SQL in route handler. Move to `domain/readiness/snapshot.py`.
6. **documents.py route** — Multipart parsing in route. Move to `adapters/parsers/`.
7. **Job budgets** — Readiness analyzer and research runner lack budget enforcement per CODEX.md rule 5.

### Schema / performance (fix before scale)

8. **Missing pg_trgm index** — Add migration for trigram similarity index on `concepts_canon.canonical_name`. Required for resolver lexical blocking at scale.
9. **Concept tier extraction** — Migration 0009 adds the `tier` column. Verify that `domain/graph/extraction.py` actually populates it during raw→canonical resolution.

### Test gaps (fix for confidence)

10. **Graph resolver** — 7 unit tests is insufficient for a component that makes merge-vs-create decisions affecting the entire knowledge graph. Add disambiguation conflict, budget exhaustion, and concurrent resolution scenarios.
11. **Graph gardener** — 7 unit tests + 1 integration. Add cluster conflict, partial merge, budget exhaustion mid-run scenarios.
12. **Verifier** — 6 tests for the component that enforces the "evidence-first" product promise. Add strict-mode edge cases, malformed citation payloads, and boundary conditions.
13. **E2E pipeline** — No test exercises the full upload→chunk→embed→retrieve→respond→verify loop. This is the most important integration seam in the product.

### Frontend gaps (fix for product spec compliance)

14. **Streaming status ticker** — PRODUCT_SPEC.md §8 specifies it. Types exist. Display is not wired. Users see no streaming status.
15. **Grounding mode toggle** — PRODUCT_SPEC.md describes a strict/hybrid toggle. Backend supports it. No UI control exists.

---

## Recommendation

The codebase is in better shape than the last report. The engineering quality is high — clean layers, strong typing, real budget enforcement, good test coverage in most areas. The main risk is not code quality; it is **product ambiguity**.

Three things would most improve the project's position:

1. **Fix the docs to match reality.** The GRAPH.md column-name errors, the ARCHITECTURE.md stale diagram, and the retrieval location mismatch are all trivially fixable and create unnecessary confusion. Do this first.

2. **Wire what is already built.** The conductor (TurnPlan + QueryAnalyzer), the streaming status UI, and the grounding toggle are all partially or fully implemented in the backend. Finishing the last mile of integration would close the gap between docs and product with relatively low effort.

3. **Decide on Phase 2 scope before building more scaffolding.** The research planner, learner assembler, and learner digest job are real code — but they are not connected to users, and they are not being tested end-to-end. Adding more scaffolding without a clear product decision about when and how these features ship will create maintenance burden without user value.

The worst outcome would be continuing to build internal plumbing for Phase 2 features while Phase 1 has spec-vs-implementation gaps (streaming status, grounding toggle, conductor wiring) that are visible to users. Ship the current product cleanly first.
