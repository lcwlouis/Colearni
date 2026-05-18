# AGENTS.md

## Current State

CoLearni was reset to start fresh for the actual MVP. Treat the docs in `docs/` as the current source of truth. Historical README/architecture assumptions should not be carried forward unless they match the rebuild docs.

## Read These First

- `docs/CODEX.md`
- `docs/REBUILD_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/PROMPTS.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/MASTERY_MODEL.md`
- `docs/TUTOR_BEHAVIOUR.md`
- `docs/SOURCE_PROVENANCE.md`
- `docs/TEST_PLAN.md`
- `docs/FRONTEND.md` when touching `apps/web/`

## Repo Expectations

- Small PR-sized changes, target 400 net LOC or less. Split larger work into phases.
- FastAPI routes must stay thin; no business logic in routes.
- Tests are required for new core behavior.
- Evidence-first: user-visible sourced answers must include citations or refuse in strict mode.
- Source provenance is mandatory for import/export and retrieval behavior.
- Public Trail Packs must never include private workspace content.
- No unbounded loops; obey graph resolver and gardener budgets in `docs/GRAPH.md`.

## Startup and Shutdown (lifespan)

`backend/app/main.py` contains the `lifespan` async context manager. Startup logic goes **before** the `yield`; shutdown/teardown logic goes **after** it.

**Current responsibilities:**
- Startup: `ensure_default_workspace()` — creates the default local workspace if none exists. Remove or replace when auth + multi-user support is added.
- Shutdown: `engine.dispose()` — closes the SQLAlchemy async connection pool cleanly.

**Update the lifespan when you add any of the following:**
- A new DB engine or secondary connection pool.
- An external HTTP client (e.g. `httpx.AsyncClient`) that should be shared across requests.
- A cache client (Redis, in-memory, etc.).
- A background task scheduler or worker.
- Any object that must be initialised once at startup or closed cleanly at shutdown.

Always add a short inline comment above each startup/shutdown line explaining what it owns and when it should be changed (e.g. `# Replace with user-scoped provisioning when auth is added`).

## MVP Direction

Build local-ready first, with SaaS as a thin layer later.

Do not start with:

- PDF ingestion.
- SaaS auth/billing.
- Public marketplace.
- Complex multi-agent frameworks.

The first demo should prove that a learner can create a Trail, learn one concept Socratically, pass a level-up quiz, see graph progress update, and export/import a safe Trail Pack.
