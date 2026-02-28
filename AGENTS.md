# AGENTS.md

## Read these first
- docs/CODEX.md
- docs/ARCHITECTURE.md
- docs/PRODUCT_SPEC.md
- docs/GRAPH.md
- docs/FRONTEND.md (required when touching `apps/web/`)

## Repo expectations (summary)
- Small PRs (<= 400 LOC net). Split if larger.
- FastAPI routes must stay thin (no business logic).
- Tests required for all new behavior (pytest).
- Evidence-first: user-visible answers must include citations or refuse in strict mode.
- Budgets: no unbounded loops; obey resolver + gardener budgets in docs/GRAPH.md.