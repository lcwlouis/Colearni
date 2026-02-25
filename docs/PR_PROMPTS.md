# PR Prompt Library

Last updated: 2026-02-25

This file stores:
- `Used prompts` (PR1-PR15, retroactively standardized from the current repo state).
- `New prompts` (PR16+).

All prompts below are copy-paste ready for Codex.

## Shared Post-Implement Prompt

```text
PRX (Fix + Summary):
Run:
- ruff check .
- pytest -q
- alembic upgrade head (if migrations changed)

Fix failures, then provide:
- PR description
- key files changed
- migration/env changes
- how to run locally (3 commands)
- 2 API demo commands
- residual risks/follow-ups
Confirm routes are thin and PR <= 400 LOC net.
```

## Used Prompts (Archive)

### PR1 - Base Structure

Worktree: `codex/pr1-base-structure`

```text
PR1 (Design only, no code yet):
Read AGENTS.md plus:
- docs/CODEX.md
- docs/ARCHITECTURE.md
- docs/PRODUCT_SPEC.md
- docs/GRAPH.md

Goal: Create a clean Python backend scaffold.

Requirements:
- Create folder structure:
  apps/api, core, domain, adapters, tests, docs
- FastAPI app with GET /healthz returning 200 JSON.
- Keep routes thin (no business logic).
- Add ruff + pytest configuration.
- Add minimal config/settings module (pydantic-settings preferred).
- Add Makefile (or equivalent) with targets: lint, test, dev.
- Add a smoke test for /healthz.

Output: a short implementation plan listing files to add/modify and tests to add. Do NOT write code yet.```

```text
PR1 (Implement):
Implement the plan.

Acceptance criteria:
- App boots locally.
- GET /healthz returns 200 JSON.
- ruff passes and pytest passes.
- No DB/migrations in PR1.
- Routes contain no business logic.
```

```text
PR1 (Fix + Summary):
Use the integrated terminal to run lint/tests and fix failures.
Then write:
- PR description
- how to run locally (3 commands)
- 2 curl demos
```

### PR2 - DB Foundation + Initial Schema

Worktree: `codex/pr2-db-foundation`

```text
PR2 (Design only, no code yet):
Read AGENTS.md plus docs/GRAPH.md and docs/PRODUCT_SPEC.md. Postgres-only.

Goal: Add DB layer with SQLAlchemy 2.0 + Alembic migrations.

Requirements:
1) adapters/db:
   - engine + session
   - FastAPI dependency for session
2) Alembic initial migration creates:
   - users
   - workspaces
   - workspace_members
   - documents
   - chunks (text, tsvector column, embedding vector column)
   - concepts_raw, edges_raw
   - concepts_canon (canonical_name, description, aliases[], embedding optional, is_active, dirty)
   - edges_canon (src_id, tgt_id, relation_type, description, keywords[], weight)
   - provenance (target_type, target_id, chunk_id)
   - concept_merge_map (alias -> canon_concept_id, confidence, method)
   - concept_merge_log (from_id -> to_id, reason, method, confidence)
   - chat_sessions
   - chat_messages (type, payload JSONB)
   - quizzes, quiz_items, quiz_attempts
   - mastery (user_id, concept_id, score, status, updated_at)
3) Migration must enable extensions:
   - vector (pgvector)
   - pg_trgm
4) Indexes:
   - GIN on chunks.tsv
   - FK indexes
   - vector column present; vector index can be deferred

Output: list files to add/modify and schema outline (tables + key columns + constraints). No code yet.
```

```text
PR2 (Implement):
Implement PR2 per plan.

Acceptance criteria:
- docker compose up -d starts DB (pgvector image).
- alembic upgrade head works.
- app still boots.
- pytest passes (integration test can be skipped if DB missing, but should run when DB is up).
- Add a small integration test that checks extensions + a couple tables exist.
```

```text
PR2 (Fix + Summary):
Run lint/tests/migrations via the integrated terminal and fix issues.
Then write:
- PR description
- migration instructions
- how to run locally
- demo commands (including alembic upgrade)
```

### PR3 - Documents Ingestion API + Parsing

Worktree: `codex/pr3-documents-ingestion`

```text
PR3 (Design only, no code yet):
Read AGENTS.md plus:
- docs/CODEX.md
- docs/ARCHITECTURE.md
- docs/PRODUCT_SPEC.md
- docs/GRAPH.md

Goal: Implement ingestion for .md/.txt.

Requirements:
- POST /documents/upload (workspace-scoped) that accepts md/txt (multipart or raw text).
- Parser + normalizer in adapters/parsers (no PDFs yet).
- Deterministic chunker with tests (stable chunk IDs or stable ordering).
- Store:
  - documents row
  - chunks rows (text)
  - chunks.tsv (Postgres tsvector for full-text search)
- No embeddings in PR3.
- Add minimal CRUD query helpers in adapters/db for documents/chunks (no business logic in routes).

Output:
- Implementation plan (files + functions)
- DB write paths used
- Test plan (unit + optional integration)
Do NOT write code yet.
```

```text
PR3 (Implement):
Implement PR3 per plan.
Acceptance criteria:
- Upload creates a document and chunks in DB.
- chunks.tsv populated and searchable (simple test query).
- ruff + pytest pass.
- Routes remain thin.
- Add at least: unit tests for chunker + normalizer, and one DB integration test if DB is up.
```

### PR4 - Embeddings Pipeline

Worktree: `codex/pr4-embeddings-pipeline`

```text
PR4 (Design only, no code yet):
Read /Users/louisliu/Projects/Personal/ColearniCodex/AGENTS.md plus:
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/CODEX.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/ARCHITECTURE.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/PRODUCT_SPEC.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/GRAPH.md

Goal: Add embeddings pipeline + pgvector top-k retrieval.

Requirements:
- Keep FastAPI routes thin; put logic in domain/adapters.
- Add embedding provider interface + adapter (mockable in tests).
- Add write path to populate chunks.embedding for newly ingested chunks and a bounded backfill utility for missing embeddings.
- Add vector retriever: retrieve(query, workspace_id, top_k) -> ranked chunks.
- Keep budgets bounded (no unbounded loops/calls).
- Add unit tests for embedding batching + ranking behavior.
- Add DB integration test for vector similarity retrieval if DB is up.

Output:
- Implementation plan (files/functions/tests).
- Any new env vars/config.
Do NOT write code yet.
```

```text
PR4 (Implement):
Implement PR4 per the approved design.

Acceptance criteria:
- Embeddings can be generated for chunks and stored in DB.
- Vector retrieval returns top-k relevant chunks for a workspace.
- ruff check . passes.
- pytest -q passes.
- PR size stays small (<= 400 LOC net); if larger, split into PR4a/PR4b.
```

### PR5 - Hybrid Retrieval (Vector + FTS)

Worktree: `codex/pr5-hybrid-fulltext-retrieval`

```text
PR5 (Design only, no code yet):
Read /Users/louisliu/Projects/Personal/ColearniCodex/AGENTS.md plus:
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/CODEX.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/ARCHITECTURE.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/PRODUCT_SPEC.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/GRAPH.md

Goal: Add full-text retrieval + hybrid merge (vector + tsvector).

Requirements:
- Implement FTS retriever on chunks.tsv.
- Implement hybrid retriever that merges vector + FTS candidates and reranks deterministically.
- Return retrieval payload with provenance-ready fields (workspace_id, document_id, chunk_id, snippet, score, retrieval method).
- No business logic in routes.
- Add unit tests for hybrid merge/rerank.
- Add DB integration test proving FTS + vector both contribute.

Output:
- Plan with file list + scoring/rerank formula.
- Test plan.
Do NOT write code yet.
```

```text
PR5 (Implement):
Implement PR5 per the approved plan.

Acceptance criteria:
- Hybrid retrieval works and returns merged ranked results.
- Workspace scoping is enforced.
- ruff check . passes.
- pytest -q passes.
- Keep PR <= 400 LOC net; split if needed.
```

### PR6 - Citation Verifier for User-Facing Responses

Worktree: `codex/pr6-citation-verifier`

```text
PR6 (Design only, no code yet):
Read /Users/louisliu/Projects/Personal/ColearniCodex/AGENTS.md plus:
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/CODEX.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/ARCHITECTURE.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/PRODUCT_SPEC.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/GRAPH.md

Goal: Evidence model + citations enforcement for user-visible responses.

Requirements:
- Add/confirm core Pydantic schemas: EvidenceItem, Citation, assistant response envelope.
- Add verifier logic:
  - Hybrid mode: allow general context but label it.
  - Strict mode: refuse/ask for sources when evidence is insufficient.
- Add minimal integration point in chat response path so all assistant outputs pass verifier.
- Add unit tests for strict/hybrid behavior and citation validation.
- Keep routes thin.

Output:
- Plan + schema definitions + enforcement points.
Do NOT write code yet.
```

```text
PR6 (Implement):
Implement PR6 per plan.

Acceptance criteria:
- User-visible assistant outputs include citations or refusal in strict mode.
- Strict/hybrid toggle is test-covered.
- ruff check . passes.
- pytest -q passes.
```

### PR7 - Graph Extraction + Online Resolver

Worktree: `codex/pr7-graph-extraction-resolver`

```text
PR7 (Design only, no code yet):
Read /Users/louisliu/Projects/Personal/ColearniCodex/AGENTS.md plus:
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/CODEX.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/ARCHITECTURE.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/PRODUCT_SPEC.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/GRAPH.md

Goal: Raw extraction + Online Resolver + canonical upserts.

Requirements:
- Extract concepts_raw + edges_raw from chunks via schema-first LLM output.
- Implement online resolver with bounded candidate generation:
  - exact alias map
  - lexical top-k
  - vector top-k
  - optional single LLM disambiguation
- Respect GRAPH budgets (candidate caps + LLM caps).
- Canonical merge/create rules:
  - alias map updates
  - provenance links
  - dirty flag updates
  - edge upsert dedupe by unique key
- Add unit tests with mocked LLM.
- Add DB integration test for merge/create + provenance behavior.

Output:
- Plan with resolver decision thresholds and fallback rules.
Do NOT write code yet.
```

```text
PR7 (Implement):
Implement PR7 per plan.

Acceptance criteria:
- Raw extraction persists concepts_raw/edges_raw.
- Online resolver upserts canonical nodes/edges with provenance.
- Budget guards hard-stop when caps are reached.
- ruff check . passes.
- pytest -q passes.
- Keep PR <= 400 LOC net; split into PR7a/PR7b if needed.
```

```text
PR7-HF1 (Design only, no code yet):
Read AGENTS.md plus:
- docs/CODEX.md
- docs/ARCHITECTURE.md
- docs/PRODUCT_SPEC.md
- docs/GRAPH.md

Goal: Fix retrieval contract drift and wire hybrid retrieval into chat.

Requirements:
- Define one canonical RankedChunk contract used consistently by retrievers + chat response builder.
- Update vector/FTS/hybrid retrievers and related tests to that contract.
- Update chat response assembly to use the same contract fields (no adapter mismatch).
- Replace vector-only retrieval in chat with HybridRetriever (vector + FTS), preserving workspace scoping and top_k bounds.
- Keep routes thin.
- Add regression tests covering the failing chat path and hybrid usage path.

Acceptance criteria:
- pytest -q passes, including tests/api/test_chat_respond.py.
- ruff check . passes.
- /chat/respond still returns AssistantResponseEnvelope with valid citations/evidence metadata.
- PR <= 400 LOC net (split if needed).

Output:
- Implementation plan with files/functions/tests.
Do NOT write code yet.
```

```text
PR7-HF2 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md and docs/ARCHITECTURE.md.

Goal: Populate chunk embeddings during ingestion (bounded, testable).

Requirements:
- Wire embedding population into document ingestion write path for new chunks.
- Respect batch size and bounded behavior from settings.
- Keep fallback behavior explicit if provider is unavailable (clear error or controlled skip by design; choose one and test it).
- Preserve existing ingest behavior (documents/chunks/tsv).
- Add unit/integration tests for ingestion with embeddings.

Acceptance criteria:
- New ingested chunks have non-null embeddings when embedding path is enabled.
- Existing ingestion tests remain green.
- ruff check . and pytest -q pass.
- PR <= 400 LOC net.

Output:
- Implementation plan with any new config flags/env vars and test plan.
Do NOT write code yet.
```

```text
PR7-HF3 (Design only, no code yet):
Read AGENTS.md plus docs/GRAPH.md and docs/ARCHITECTURE.md.

Goal: Wire PR7 graph extraction/resolver into ingestion path safely.

Requirements:
- Connect upload->ingestion path to graph build pipeline with explicit configuration gates.
- Keep resolver budgets enforced as in docs/GRAPH.md.
- Ensure raw rows, canonical upserts, alias map, and provenance are written when enabled.
- Keep routes thin; orchestration in core/domain.
- Add tests for enabled/disabled wiring behavior.

Acceptance criteria:
- In enabled mode, upload ingestion writes raw + canonical graph artifacts.
- In disabled mode, upload behavior remains unchanged.
- ruff check . and pytest -q pass.
- PR <= 400 LOC net.

Output:
- Implementation plan and test plan.
Do NOT write code yet.
```

```
PRX (Fix + Summary):
Run:
- ruff check .
- pytest -q
- alembic upgrade head (if migrations changed)

Fix failures, then write:
- PR description
- key files changed
- migration/env changes
- how to run locally (3 commands)
- 2 demo API commands
- residual risks/follow-ups
Also confirm routes are thin and PR size <= 400 LOC net.
```

```text
PR7-Reconcile (Design only, no code yet):
Read /Users/louisliu/Projects/Personal/ColearniCodex/AGENTS.md plus:
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/CODEX.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/ARCHITECTURE.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/PRODUCT_SPEC.md
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/GRAPH.md

Goal: reconcile PR7 hotfixes on main.

Requirements:
- Unify RankedChunk contract across retrievers, chat orchestration, and tests.
- Wire chat retrieval to hybrid (vector + FTS) with bounded top_k and workspace scoping.
- Ensure ingestion path behavior for embeddings and graph wiring matches approved hotfix decisions.
- Keep routes thin.
- Update/add tests for regression coverage.

Acceptance criteria:
- pytest -q passes.
- ruff check . passes.
- /chat/respond tests are green.
- No business logic moved into FastAPI routes.
- PR <= 400 LOC net (split if needed).

Output:
- Implementation plan with exact files/functions/tests.
Do NOT write code yet.
```

```text
PR7-HF4 (Design only, no code yet):
Read /Users/louisliu/Projects/Personal/ColearniCodex/AGENTS.md plus:
- /Users/louisliu/Projects/Personal/ColearniCodex/docs/CODEX.md

Goal: fix grounding env var naming consistency.

Requirements:
- Update /Users/louisliu/Projects/Personal/ColearniCodex/.env and /Users/louisliu/Projects/Personal/ColearniCodex/.env.example:
  - replace DEFAULT_GROUNDED_MODE with APP_DEFAULT_GROUNDING_MODE
- Ensure comments reflect valid values: hybrid | strict.
- Add/adjust a small settings test if needed to prevent regression.

Acceptance criteria:
- ruff check . passes
- pytest -q passes
- env examples match Settings aliases

Output:
- file-level implementation plan only. Do NOT write code yet.
```

### PR8 - Provider Foundations

Worktree: `codex/pr8-provider-foundation`

```text
PR8 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Add provider-agnostic embedding support with OpenAI + LiteLLM (keep mock for tests).

Requirements:
- Extend embedding provider config to support: mock, openai, litellm.
- Add LiteLLM embedding adapter implementing EmbeddingProvider.
- Keep current OpenAI adapter working.
- Add settings/envs for LiteLLM model + optional base URL/api key pass-through.
- Preserve current DB schema (embedding dim still enforced; no migration in this PR).
- Add unit tests for factory selection, error handling, and response cardinality.
- No network calls in tests; use monkeypatch/fakes.

Acceptance criteria:
- Existing embedding/retrieval tests pass unchanged.
- New tests cover litellm path and config validation.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net (split if needed).

Output:
Implementation plan (files + tests). Do NOT write code yet.

```

### PR9 - GraphLLM Client Abstraction + Wiring

Worktree: `codex/pr9-graph-llm-provider`

```text
PR9 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Wire GraphLLM client implementations through provider abstraction (OpenAI + LiteLLM).

Requirements:
- Implement concrete GraphLLMClient adapters for OpenAI and LiteLLM.
- Add factory/build function for graph LLM client selection from settings.
- Wire app startup state so graph client can be injected when APP_INGEST_BUILD_GRAPH=true.
- Keep ingestion route thin; no graph business logic in route.
- Ensure schema-first extraction/disambiguation format remains enforced.
- Add tests for factory wiring and ingestion graph-enabled/disabled behavior.

Acceptance criteria:
- Graph-enabled ingestion path can resolve graph client from settings.
- Graph-disabled behavior remains unchanged.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

### PR10 - Tutor Agent Mastery Gating

Worktree: `codex/pr10-tutor-mastery-gating`

```text
PR10 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md.

Goal:
Implement TutorAgent behavior with mastery gating on top of verified chat response flow.

Requirements:
- Add mastery lookup and gating policy:
  - not learned -> Socratic style (questions/hints/step prompts)
  - learned -> direct summary/explanation allowed
- Use provider abstraction from PR8/PR9 for generated tutor text.
- Keep verifier/citation envelope constraints intact.
- Keep routes thin.
- Add tests for gating matrix (learned/not learned x strict/hybrid).

Acceptance criteria:
- Behavior changes correctly by mastery state.
- Evidence/citations policy still enforced.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

### PR11 - Level-Up Quiz Flow + Mastery Transition

Worktree: `codex/pr11-levelup-quiz`

```text
PR11 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md.

Goal:
Level-up quiz card flow with grading and mastery transition.

Requirements:
- Add create quiz, submit answers, grade attempt, persist results.
- Use existing quizzes/quiz_items/quiz_attempts/mastery tables.
- Enforce pass criteria from PRODUCT_SPEC.
- Keep routes thin.
- Add tests for pass/fail transitions and idempotent submission behavior.

Acceptance criteria:
- End-to-end level-up flow works.
- Mastery updates correctly and is test-covered.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

```text
PR11-HF5 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md and docs/ARCHITECTURE.md.

Goal:
Finish runtime LiteLLM support for embeddings so APP_EMBEDDING_PROVIDER can be openai|litellm|mock.

Requirements:
- Add missing settings field(s) for LiteLLM embedding model config (e.g. APP_LITELLM_MODEL).
- Update embedding provider validator to allow litellm.
- Keep OpenAI and mock behavior unchanged.
- Update .env.example with LiteLLM embedding config examples.
- Add tests proving env-driven settings + factory behavior for openai/litellm/mock.
- Keep PR small and focused.

Acceptance criteria:
- Setting APP_EMBEDDING_PROVIDER=litellm can successfully build provider.
- Existing embedding tests still pass.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

### PR12 - Practice mode

Worktree: `codex/pr12-practice-mode`

```text
PR12 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Implement practice mode (flashcards + mini quizzes) from a graph concept node, non-leveling.

Requirements:
- Add domain module + API route(s) for:
  - flashcard generation from concept context
  - practice quiz generation/submission
- Practice quizzes may use existing quizzes/quiz_items/quiz_attempts with quiz_type='practice'.
- Explicitly DO NOT update mastery to learned in any practice flow.
- Reuse provider abstraction (openai/litellm) for generated content.
- Keep FastAPI routes thin.
- Add tests for:
  - generation success
  - grading/feedback shape (if applicable)
  - mastery unchanged
  - workspace scoping

Acceptance criteria:
- Practice flow works from concept_id in workspace.
- No practice flow mutates mastery to learned.
- Existing PR11 level-up behavior (mixed grading + generation-context-based grading) is not regressed.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net (split if needed).

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

### PR13 - Graph Explorer API + Lucky

Worktree: `codex/pr13-graph-explorer`

```text
PR13 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Add graph exploration endpoints and “I’m feeling lucky”.

Requirements:
- Add read-only graph endpoints:
  - concept detail
  - bounded neighbors/subgraph
- Add lucky endpoint:
  - adjacent mode (k-hop neighborhood)
  - wildcard mode (new but workspace-relevant)
- Enforce strict workspace isolation.
- Enforce bounded response sizes and deterministic ordering.
- Keep routes thin.
- Add tests for scope/bounds/ranking behavior.

Acceptance criteria:
- Graph endpoints are workspace-scoped and bounded.
- Lucky suggestions return valid adjacent/wildcard picks.
- Existing retrieval/chat/quiz flows remain green.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

### PR14 - Graph Gardener (Offline Consolidation)

Worktree: `codex/pr14-graph-gardener`

```text
PR14 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Implement offline Graph Gardener consolidation job with hard budgets.

Requirements:
- Process only bounded dirty/recent canonical nodes.
- Candidate generation via lexical + vector top-k blocking.
- Cluster and run budgeted LLM merge decisions.
- Execute idempotent merges:
  - mark merged-away concepts inactive
  - repoint/dedupe edges
  - update alias map
  - write merge log
- Enforce hard stops for all gardener budgets.
- Add tests for:
  - budget stopping
  - idempotency
  - merge bookkeeping correctness

Acceptance criteria:
- Gardener never scans entire graph in one run.
- Budget caps are enforced in code.
- Merge log + alias updates are correct and reversible.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net (split if needed).

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

### PR15 - PDF Text-Layer Ingestion

Worktree: `codex/pr15-pdf-text-ingestion`

```text
PR15 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md and docs/ARCHITECTURE.md.

Goal:
Add basic PDF text-layer ingestion (no image crop/zoom mode).

Requirements:
- Support text-extractable PDFs only.
- Reuse normalize/chunk/store pipeline.
- Clear failure for non-extractable PDFs.
- Keep routes thin.
- Add tests for extractable and non-extractable PDFs.

Acceptance criteria:
- Text PDFs ingest successfully into existing document/chunk flow.
- Non-extractable PDFs fail with clear error message.
- Existing md/txt ingestion remains unchanged.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.

Output:
Implementation plan (files + tests). Do NOT write code yet.
```

## New Prompts (Next)

Use `Shared Post-Implement Prompt` after each `PR16+ (Implement)` run.

### PR16 - Level-Up Submit API Contract Parity

Worktree: `codex/pr16-levelup-feedback-contract`

```text
PR16 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Align level-up submit API response with product spec by returning per-item feedback plus overall feedback.

Requirements:
- Update submit response schema for level-up quiz to include:
  - item identifier
  - item type
  - correctness/result
  - per-item explanation/feedback
  - item score where applicable
- Preserve mixed grading behavior:
  - MCQ deterministic grading
  - short-answer rubric grading using persisted generation-time context
- Preserve mastery transition logic and pass criteria behavior.
- Keep routes thin; domain owns grading/feedback composition.
- Add tests for schema shape and grading output coverage (unit + API/integration as appropriate).
- Keep PR <= 400 LOC net (split if needed).

Output:
Implementation plan (files + tests + schema changes). Do NOT write code yet.
```

```text
PR16 (Implement):
Implement PR16 per approved plan.

Acceptance criteria:
- `/quizzes/level-up/submit` returns per-item feedback and overall feedback in one response.
- Existing grading correctness for MCQ + short-answer is preserved.
- Mastery update behavior is unchanged and test-covered.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.
```

### PR17 - Typed Response Schemas for API Outputs

Worktree: `codex/pr17-typed-response-schemas`

```text
PR17 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Replace ad-hoc API payload dictionaries with typed Pydantic response models across chat/quizzes/practice/graph routes.

Requirements:
- Define/expand response models in core schemas for all target endpoints using loose dict payloads.
- Update route response models and serialization to typed outputs.
- Preserve backward compatibility of field names unless explicitly called out.
- Keep FastAPI routes thin (validation + delegation + return only).
- Add route tests for response contracts and required fields.
- Add/adjust domain tests if typing changes surface behavior edges.
- Keep PR <= 400 LOC net (split if needed).

Output:
Implementation plan (files + endpoint contract map + tests). Do NOT write code yet.
```

```text
PR17 (Implement):
Implement PR17 per approved plan.

Acceptance criteria:
- Target endpoints return typed response models (no loose dict contracts).
- OpenAPI response definitions match runtime payloads.
- Existing behavior is preserved (typing-only refactor unless explicitly planned).
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.
```

### PR18 - Observability for Grading + Budgets

Worktree: `codex/pr18-observability-budgets`

```text
PR18 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Add observability for grading flows and graph/gardener budgets without changing business behavior.

Requirements:
- Add structured events/logs for:
  - level-up grading start/result/failure
  - practice grading start/result/failure
  - resolver and gardener budget usage + hard-stop reasons
- Include correlation IDs (workspace_id, quiz_id/attempt_id, run_id where relevant).
- Keep instrumentation provider-agnostic (works with OpenAI/LiteLLM paths).
- Ensure logs do not expose secrets or full sensitive payloads.
- Add tests validating instrumentation is emitted on key success/failure branches.
- Keep PR <= 400 LOC net (split if needed).

Output:
Implementation plan (events schema + file list + tests). Do NOT write code yet.
```

```text
PR18 (Implement):
Implement PR18 per approved plan.

Acceptance criteria:
- Grading paths emit structured observability events.
- Resolver/gardener budget consumption and stop reasons are logged.
- Instrumentation does not alter existing grading or graph behavior.
- ruff check . passes.
- pytest -q passes.
- PR <= 400 LOC net.
```

### PR19 - Frontend Scaffold + API Client

Worktree: `codex/pr19-frontend-scaffold`

```text
PR19 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md.

Goal:
Create a minimal frontend scaffold and typed API client that preserves the app's learning-first intent.

Requirements:
- Create `apps/web` (Next.js) with minimal page shell and navigation.
- Add typed API client aligned to backend response contracts from PR17.
- Add environment-configurable backend base URL.
- Add initial views/placeholders for:
  - tutor chat
  - graph exploration
  - quizzes/practice entry points
- Do not encode tutor policy in frontend; backend remains source of truth for mastery gating and evidence mode.
- Include basic UX states: loading, empty, API error.
- Document frontend run/build commands.
- Keep PR <= 400 LOC net (split if needed).

Output:
Implementation plan (files + client strategy + tests/lint plan). Do NOT write code yet.
```

```text
PR19 (Implement):
Implement PR19 per approved plan.

Acceptance criteria:
- Frontend app boots and can call backend health endpoint.
- Typed API client works against current backend contracts.
- Desktop and mobile layout render without breakage.
- Backend test suite remains green.
- Frontend commands are documented.
- PR <= 400 LOC net.
```

### PR20 - Chat + Level-Up Card UI

Worktree: `codex/pr20-chat-levelup-ui`

```text
PR20 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md.

Goal:
Implement chat UI and level-up card UX that reflects Socratic-by-default learning and mastery progression.

Requirements:
- Chat UI:
  - send message / receive assistant response
  - render citations/evidence labels
  - render strict-grounding refusals clearly when returned
- Level-up UI:
  - start quiz
  - render mixed item types
  - submit once
  - render per-item feedback + overall summary + next steps
- Respect backend mastery gating; UI must not bypass or simulate direct-answer unlocks.
- Add client-side state tests (or component tests) for critical flows and error paths.
- Keep PR <= 400 LOC net (split if needed).

Output:
Implementation plan (routes/components/state + tests). Do NOT write code yet.
```

```text
PR20 (Implement):
Implement PR20 per approved plan.

Acceptance criteria:
- Chat UI works end-to-end with citations/grounding states shown.
- Level-up card flow works end-to-end with per-item + overall feedback rendering.
- Error/retry states are handled clearly.
- Frontend behavior does not violate backend tutoring/mastery policies.
- PR <= 400 LOC net.
```

### PR21 - Graph Explorer + Practice UI + Lucky

Worktree: `codex/pr21-graph-practice-ui`

```text
PR21 (Design only, no code yet):
Read AGENTS.md plus docs/CODEX.md, docs/ARCHITECTURE.md, docs/PRODUCT_SPEC.md, docs/GRAPH.md.

Goal:
Implement graph explorer and practice UI to support breadth learning without mutating mastery through practice.

Requirements:
- Graph explorer UI:
  - list/select canonical concepts
  - show concept detail and bounded adjacency
- Lucky flow:
  - adjacent suggestions
  - wildcard suggestions
- Practice UI:
  - generate flashcards
  - generate/submit practice quiz
  - render feedback
- Clearly separate practice outcomes from level-up/mastery progression in UI.
- Keep API usage bounded (no unbounded polling/fetch loops).
- Add tests for core UI flows and workspace-scoped API calls.
- Keep PR <= 400 LOC net (split if needed).

Output:
Implementation plan (components/data flows/tests). Do NOT write code yet.
```

```text
PR21 (Implement):
Implement PR21 per approved plan.

Acceptance criteria:
- Graph UI loads canonical node data and bounded adjacency.
- Lucky action returns and displays adjacent/wildcard suggestions.
- Practice flows run end-to-end and do not indicate mastery mutation.
- Mobile and desktop layouts are usable.
- PR <= 400 LOC net.
```

## Parallel Work Guidance (for New PRs)

Safe to run concurrently after PR17 is merged:
- `PR18` and `PR19` can run in parallel.

Must be sequential:
- `PR16 -> PR17 -> PR19`.
- `PR20` depends on `PR19` and `PR16/PR17` contracts.
- `PR21` depends on `PR19` and graph/practice contract stability.
