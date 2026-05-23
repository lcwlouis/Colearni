# CLAUDE.md

This file gives Claude Code guidance for working in this repository.

## Current State

CoLearni was reset to start fresh for the actual MVP. Some historical files may still exist in git history, but the current rebuild should follow the docs in `docs/`.

Do not assume the old ingestion-first app still exists. The new MVP is local-ready, graph-first, and Trail-centered.

## Read These First

Before making changes, read the relevant docs:

- `docs/CODEX.md` - contributor rules, safety rules, verification format.
- `docs/REBUILD_PLAN.md` - phased MVP execution plan.
- `docs/ARCHITECTURE.md` - system architecture, data model, and layer structure.
- `docs/API.md` - full API contract (endpoints, schemas, streaming spec).
- `docs/PROMPTS.md` - prompt registry format and skeletons for all LLM tasks.
- `docs/PRODUCT_SPEC.md` - MVP product behavior and non-goals.
- `docs/GRAPH.md` - graph validation and budget rules.
- `docs/MASTERY_MODEL.md` - mastery statuses, state transitions, scoring, practice mode.
- `docs/TUTOR_BEHAVIOUR.md` - tutor modes, context management, streaming.
- `docs/SOURCE_PROVENANCE.md` - source safety and export rules.
- `docs/TEST_PLAN.md` - required test coverage by phase.
- `docs/FRONTEND.md` - required when touching `apps/web/`.

## Product Direction

CoLearni is:

```text
personal learning workspace
+ concept graph / Trail
+ Socratic tutor
+ mastery state
+ source-aware retrieval
+ safe community Trail sharing
```

The product should feel like a mentor or coach, not a search engine.

Build local-ready first. Keep SaaS compatibility in the architecture, but do not start with auth, billing, moderation, or a public marketplace.

## MVP Build Order

1. Foundation cleanup.
2. Workspace + Trail database models.
3. Trail generation endpoint.
4. Graph viewer.
5. Tutor chat for one concept.
6. Mastery + level-up quiz.
7. Source provenance + export sanitizer.
8. Trail Pack export.
9. Research trace.
10. Hydration.
11. Trail Pack import.
12. Demo polish.
13. SaaS prep.

Do not start with PDF ingestion.

## Architecture Rules

- Keep FastAPI routes thin: validate input, call services, return output.
- Put business logic in services. If domain modules are later introduced, keep them separate from HTTP routes.
- Keep LLM prompts isolated, versioned, and testable.
- Keep source provenance explicit.
- Never mix public Trail Pack content with private workspace content.
- Preserve evidence-first behavior: user-visible sourced answers cite allowed evidence or refuse in strict grounded mode.
- Obey graph resolver and gardener budgets in `docs/GRAPH.md`.
- Avoid unbounded loops and whole-workspace retrieval by default.

## Layer Structure

The canonical layout for this rebuild:

```text
backend/
  app/
    api/        # FastAPI routes only — validate input, call service, return output
    services/   # Business logic: Trail, tutor, mastery, source, research, export/import
    agents/     # LLM orchestration and prompt rendering
      prompts/  # Versioned Markdown prompt files (see docs/PROMPTS.md)
    models/     # SQLAlchemy ORM models
    schemas/    # Pydantic request/response models
  alembic/      # Alembic migrations
  tests/        # pytest

apps/
  web/          # Next.js frontend

docs/
```

Do not use `apps/api/`, `domain/`, `core/`, or `adapters/` — those belonged to the old structure. Follow the layout above.

Do not inline LLM prompt strings in Python code. Use the prompt registry in `agents/prompts/`.

## Environment Variables

Required variables for the backend (document in `.env.example`):

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgresql+asyncpg://...`) |
| `LLM_PROVIDER` | Provider: `openai` \| `openrouter` \| `anthropic` \| `gemini` \| `deepseek` (default: `openai`) |
| `LLM_MODEL` | Model name for the chosen provider (e.g. `gpt-4o-mini`, `claude-3-5-haiku-20241022`) |
| `LLM_API_KEY` | API key for the provider |
| `LLM_API_BASE` | Optional: override base URL for custom/local endpoints (e.g. Ollama: `http://localhost:11434/v1`) |
| `LLM_THINKING_ENABLED` | Enable extended thinking/reasoning (default: `false`). Gracefully skipped if model doesn't support it. |
| `LLM_THINKING_BUDGET` | Anthropic: `budget_tokens` for extended thinking, min 1024 (default: `8000`) |
| `LLM_THINKING_LEVEL` | OpenAI o-series: `reasoning_effort` — `low` \| `medium` \| `high` (default: `medium`) |
| `LLM_TUTOR_MAX_TOKENS` | Requested tutor answer budget per call (default: `4096`) |
| `APP_ENV` | `development` or `production` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` (default: `INFO`) |
| `OBSERVABILITY_ENABLED` | `true` to enable OpenTelemetry traces (optional) |
| `OTLP_ENDPOINT` | OTLP endpoint for Phoenix (optional) |

Variables for the frontend:

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL (e.g. `http://localhost:8000`) |

## Planned Commands

These commands are targets for the scaffold. If implementation chooses different commands, update this file and `README.md`.

Backend:

```bash
pytest
alembic upgrade head
uvicorn backend.app.main:app --reload
```

Frontend:

```bash
cd apps/web
npm run dev
npm run typecheck
npm run test
```

Infrastructure:

```bash
docker compose up -d
```

## Safety Rules

- Never include user-uploaded content in public exports.
- Never include chunks or embeddings in public exports.
- Never include private notes or chat history in public exports.
- Never include mastery records in public exports by default.
- Public research-agent sources may export links and metadata only by default.
- Unknown license means no redistribution of content.
- Public access is not the same as redistribution rights.

## Verification

Do not claim completion without fresh verification.

Every implementation closeout should include:

```md
## Verification

Root cause / task:
Files changed:
Tests added:
Commands run:
Manual checks:
Known limitations:
```
