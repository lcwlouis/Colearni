# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Key docs to read first

Before making changes, read the relevant doc:
- `docs/CODEX.md` — contributor rules (PR size, layer constraints, DoD checklist)
- `docs/ARCHITECTURE.md` — system design and data flows
- `docs/GRAPH.md` — knowledge graph budgets and resolver/gardener rules
- `docs/FRONTEND.md` — required when touching `apps/web/`

## Commands

**Backend:**
```bash
make dev          # uvicorn --reload on :8000
make lint         # ruff check .
make test         # pytest -q (all tests)
pytest tests/domain/chat/ -v   # run a specific test directory
pytest tests/api/test_chat.py::test_foo -v  # run a single test
make db-upgrade   # alembic upgrade head
make db-revision m="add new table"  # create migration
make db-reset     # drop and recreate (dev only)
make graph-gardener   # offline graph consolidation job
make quiz-gardener    # offline quiz generation job
```

**Frontend (`apps/web/`):**
```bash
npm run dev       # next dev on :3000
npm run lint      # eslint
npm run typecheck # tsc --noEmit
npm run test      # vitest run
```

**Infrastructure:**
```bash
./scripts/start-infra.sh   # start PostgreSQL (Docker)
make phoenix               # start Arize Phoenix trace UI on :6006
```

## Architecture

Colearni is a Socratic AI tutor that grounds all responses in user-uploaded documents. Users upload files → a knowledge graph is built → a tutor answers questions using retrieved evidence, gated by mastery.

### Layer boundaries (strictly enforced)

```
apps/api/     ← thin HTTP routes only; may import core/, domain/, adapters/
core/         ← schemas, contracts, prompting, verifier; NO imports from apps/ or domain/
domain/       ← business logic; may import core/ and adapters/; NO imports from apps/
adapters/     ← DB, LLM, embeddings, parsers
apps/web/     ← Next.js frontend (no server business logic)
```

Routes must only: validate input → call domain/core → return output. No business logic in routes.

### Core data flow

**Ingestion:** Upload → parse/chunk → embed + store tsvector → extract raw concepts/edges (LLM) → online resolver → upsert canonical graph → mark dirty nodes for gardener.

**Chat query:** User message → hybrid retrieval (pgvector + FTS, RRF fusion) → `EvidenceItem[]` with provenance → TutorAgent (Socratic vs Direct based on mastery) → verifier (citations check) → streamed response or card payload.

**Level-up quiz:** Mastery check → generate quiz card → submit answers → grade (MCQ deterministic, short-answer via LLM rubric) → update mastery. Strict grounded mode: refuse if evidence is insufficient.

**Practice (non-leveling):** Same flow as level-up quiz but submissions never update mastery to `learned`.

### Key domain modules

| Module | Purpose |
|---|---|
| `domain/chat/respond.py` | Main chat orchestration entry point |
| `domain/chat/tutor_agent.py` | Socratic vs direct answer decision |
| `domain/graph/resolver.py` | Online graph resolution (budgeted) |
| `domain/graph/gardener.py` | Offline consolidation job (budgeted) |
| `domain/retrieval/` (in `adapters/`) | Hybrid vector + FTS retrieval |
| `core/contracts.py` | Protocol interfaces (EmbeddingProvider, ChunkRetriever, etc.) |
| `core/verifier.py` | Grounded answer verification |
| `core/prompting/` | File-based prompt registry (`assets/` = versioned Markdown files) |

### Budgets (hard stops — never remove)

- Resolver: max 3 LLM calls/chunk, 50/document
- Gardener: max 30 LLM calls/run, 50 clusters/run
- Chat: max tool calls per turn

Always emit explicit stop reasons when budgets are hit.

### Frontend graph rendering

`/graph/explore` API → `apps/web/lib/graph/transform.ts` → `apps/web/components/sigma-graph/` (Sigma.js WebGL + graphology + force-atlas layout + MiniSearch overlay).

### Database

PostgreSQL 16 + pgvector. Alembic manages migrations. Key table groups: auth sessions, workspaces, documents/chunks/embeddings, concepts/edges (raw + canonical), mastery, quiz attempts, flashcard progress, research sources.

## Patterns

- **All inputs/outputs use Pydantic models** — including tool schemas and API payloads.
- **Evidence-first:** every user-visible tutor answer is built from `EvidenceItem[]` + `Citation[]`.
- **Prompt versioning:** prompts live in `core/prompting/assets/` as Markdown files with front-matter (TaskType, Version). Use `PromptRegistry` to load/render them — never inline prompt strings.
- **Observability is opt-in:** set `APP_OBSERVABILITY_ENABLED=true` + `APP_OBSERVABILITY_OTLP_ENDPOINT` to enable OpenTelemetry traces (Phoenix on `:6006`). Always instrument new agent/grading paths.
- **PR size:** target ≤ 400 LOC net. Split if larger.
