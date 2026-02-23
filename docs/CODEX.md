# docs/CODEX.md

## Purpose
These rules exist so Codex can contribute code safely without turning the repo into spaghetti.

Codex must follow this doc in every PR.

---

## Golden rules (non-negotiable)

### 1) Small PRs
- Target: **<= 400 LOC net** per PR.
- If bigger, split into multiple PRs.

### 2) Routes are thin
FastAPI routes must:
- validate input (Pydantic)
- call domain/core functions
- return output
No business logic in routes.

### 3) Tests required
- Every behavior change requires tests.
- Prefer unit tests for pure logic.
- Add integration tests only when needed (DB retrieval, migrations).

### 4) Evidence-first output
All tutor responses must be built from:
- `EvidenceItem[]` + `Citation[]`

If the user enables **strict grounded mode**, the system must refuse or ask for more sources when evidence is insufficient.

### 5) Budgets prevent runaway costs
Agent loops and the Graph Gardener must obey explicit budgets:
- max tool calls per chat turn
- max LLM calls per chunk/doc
- max clusters per gardener run
Hard-stop when budgets are hit.

### 6) No cross-import violations
- `core/` and `domain/` must not import from `apps/`.
- Keep clear boundaries between layers.

---

## Style & tooling
- Python: ruff + pytest (and type checks if configured)
- Use clear typing and docstrings for public functions
- Pydantic models for all inputs/outputs (tools, cards, API payloads)
- Prefer pure functions and small modules

---

## PR workflow (Codex should follow this)
For every PR:

1) **Design-only proposal (no code)**
   - Outline approach, new files, modified files
   - Define schemas and endpoints
   - Define tests to add

2) **Implementation**
   - Implement per plan
   - Keep routes thin
   - Add tests

3) **Fix pass**
   - Ensure `ruff` and `pytest` pass
   - Fix typing/import issues

4) **PR summary**
   - Provide short description + demo commands (curl)
   - Mention any migrations and how to apply

---

## Command expectations (typical)
Codex should assume these exist or create them if missing:
- `ruff check .`
- `pytest -q`
- Optional (if configured): `ruff format .`, `mypy .`

---

## What Codex must NOT do
- Don’t add large new dependencies without explanation in PR summary.
- Don’t redesign architecture without updating docs and clearly stating why.
- Don’t implement a frontend unless the task explicitly asks for it.
- Don’t remove logs/provenance fields that enable explainability.
- Don’t create unbounded loops (chat agents, gardener, retrieval retries).

---

## Definition of Done (DoD) checklist
A PR is done only if:
- tests added/updated and passing
- migrations included if schema changed
- endpoints documented (briefly)
- no business logic in routes
- Evidence/citations preserved for user-visible answers
- budgets are respected and enforced in code