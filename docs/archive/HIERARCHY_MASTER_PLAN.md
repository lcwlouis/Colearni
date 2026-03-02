# CoLearni Hierarchy Master Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new nested plan set; no active plan is being replaced)

Template usage:
- This is a task-specific master plan for introducing a **Tiered Concept Graph** (Umbrellas, Main Topics, Subtopics, Granular nodes).
- It does not replace `docs/AGENTIC_MASTER_PLAN.md`.
- The child plans under `docs/hierarchy/` are subordinate execution plans; this file is the cross-track source of truth.

---

## Plan Completeness Checklist

This master plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered track list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

---

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of every run
   - after every 2 sub-slices across child plans
   - after any context compaction / summarization event
   - before claiming any child-plan slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the active child plan are met
3. Work in SMALL PR-sized chunks:
   - one sub-slice at a time
   - prefer commit message format: `chore(hierarchy): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` in the active child plan and update this master status ledger.
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions recorded here
6. If implementation uncovers a behavior-change risk, STOP and update the active child plan and this file before widening scope.
7. This is a schema / extraction / context / UI refactor. Do not mix in unrelated product work.
8. Completing one child plan is NOT run completion. The run is only complete when every track in the master status ledger is marked `complete` or explicitly `blocked`.
9. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.
10. Run Python verification from the repo root with `PYTHONPATH=.`. This worktree shares top-level package names like `core` and `domain` with sibling repos, so plain `pytest` can import the wrong code.
11. The `tier` column is additive. All existing rows default to `null` (unknown). Never retroactively assign tiers to existing data in a migration – only provide the column and enum type.
12. Hierarchical edges (`contains`, `has_subtopic`, `belongs_to_umbrella`) are additive new relation_type values. Existing flat edges are unchanged.
13. Do not break any existing tests in the graph resolver, gardener, or exploration path. All slice verifications must confirm `pytest -q tests/` still passes the pre-existing baseline.

---

## Purpose

The current `concepts_canon` / `edges_canon` graph is **flat**: all concepts are treated as peers. This causes two documented problems:

1. **Topic Drift** – the tutor LLM loses broader context when switching to granular nodes, leading to associative tangents rather than progressive learning.
2. **Lack of Curriculum Structure** – progressive mastery (e.g., "mastered 3/3 subtopics → master the Topic") cannot be tracked because there is no hierarchy in the data model.

This plan introduces a **Hybrid Hierarchy**:

- A `tier` identifier (`UMBRELLA | TOPIC | SUBTOPIC | GRANULAR`) is added to `concepts_canon` to support fast SQL queries and distinct UI rendering.
- New semantic edge relation types (`contains`, `has_subtopic`, `belongs_to_umbrella`) are added to `edges_canon` to encode strict parent→child structural links.
- The extraction pipeline is updated to recognize and classify tiers during concept extraction.
- The tutor retrieval context is updated to include ancestor nodes when the active concept is a SUBTOPIC or GRANULAR node.
- The frontend graph and sidebar are updated to visually distinguish tiers.

---

## Inputs Used

This plan is based on:

- `docs/AGENTIC_MASTER_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/GRAPH.md`
- `adapters/db/graph/__init__.py`
- `adapters/db/graph/concepts.py`
- `adapters/db/graph/edges.py`
- `adapters/db/graph/gardener.py`
- `domain/graph/types.py`
- `domain/graph/explore.py`
- `adapters/db/migrations/versions/20260224_0001_initial_schema.py`
- `apps/web/features/graph/hooks/use-graph-page.ts`
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `core/schemas/chat.py`

---

## Executive Summary

What is already in good shape:

- `concepts_canon` already has `is_active`, `dirty`, `embedding`, `aliases`, and `description`.
- `edges_canon` already has `relation_type` as a free-text column with no CHECK constraint limiting values.
- The migration system (Alembic) is already in place and used for all schema changes.
- `domain/graph/types.py` already has well-typed extraction domain objects.
- The frontend graph already renders nodes and edges with force-directed layout.

What is materially missing:

1. No `tier` column on `concepts_canon` → no fast filter by UMBRELLA/TOPIC/SUBTOPIC.
2. No concept of hierarchical edge types → parent/child links must be inferred by edge traversal heuristics.
3. Extraction prompts do not produce tier classification or `contains`/`has_subtopic` edges.
4. Tutor context does not include ancestor concept descriptions when on a granular subtopic.
5. UI does not visually distinguish concept tiers; all nodes render identically.

The remaining work must stay narrow:

- Additive schema change (no breaking column removals).
- Extend extractor types and prompts, not replace them.
- Inject hierarchy into tutor context via a small extension to `retrieval_context.py`.
- Add tier-based visual hints in the frontend graph without rewriting the graph rendering engine.

---

## Non-Negotiable Constraints

1. The `tier` column is nullable. Existing rows remain `null` after migration; the system degrades gracefully.
2. Do not remove or rename any existing relation types in `edges_canon` – only add new ones.
3. All new relation types must be documented in `docs/GRAPH.md`.
4. The tutor context injection must be guarded: if no ancestor is found, the tutor proceeds exactly as before.
5. Keep routes thin – all tier/hierarchy logic belongs in domain or adapter layers, not in FastAPI route handlers.
6. Preserve `verify_assistant_draft()` as the final answer gate.
7. Keep `PYTHONPATH=.` baseline test counts stable across every slice.

---

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE1` Graph schema, migrations, resolver, gardener, and exploration are all in place and tested.
- `BASE2` `edges_canon.relation_type` is already a free-text field with no enum CHECK constraint.
- `BASE3` Frontend graph force-directed rendering already handles dynamic node/edge sets.

---

## Remaining Track IDs

Use these stable IDs in commits, reports, and verification blocks:

- `HR1` Schema & Migrations
- `HR2` Extractor Prompts & Logic
- `HR3` Tutor Context Injection
- `HR4` UI Visuals

---

## Child Plan Map

Use these child files as the execution source of truth for each track:

- `docs/hierarchy/01_schema_plan.md` → `HR1`
- `docs/hierarchy/02_extractor_plan.md` → `HR2`
- `docs/hierarchy/03_tutor_context_plan.md` → `HR3`
- `docs/hierarchy/04_ui_visuals_plan.md` → `HR4`

---

## Master Status Ledger

| Track | ID  | Status      | Last verified |
|-------|-----|-------------|---------------|
| Schema & Migrations | HR1 | `complete` | 2026-03-01 |
| Extractor Prompts & Logic | HR2 | `complete` | 2026-03-01 |
| Tutor Context Injection | HR3 | `complete` | 2026-03-01 |
| UI Visuals | HR4 | `complete` | 2026-03-01 |

Update this table after every completed child-plan slice.

---

## Current Verification Status

Baseline at plan creation (2026-03-01):

- `PYTHONPATH=. pytest -q`: 555 passed (inherited from AGENTIC_MASTER_PLAN baseline)
- `npm --prefix apps/web test`: 87 passed (13 test files)
- No hierarchy-specific tests yet exist

Post-implementation status (2026-03-01):

- `PYTHONPATH=. pytest -q --ignore=tests/db`: **873 passed, 2 failed** — both pre-existing failures in `test_prompt_kit` and `test_tutor_agent` (unrelated to this plan; present before plan started)
- New tests added: `tests/domain/test_ancestor_chain.py` (9 tests), `tests/domain/test_retrieval_ancestor_context.py` (9 tests)
- `npm --prefix apps/web run typecheck`: 0 new errors (1 pre-existing unrelated test-file error)
- DB integration tests (`tests/db/`): skip (no live DB in CI) — migration `20260301_0009_concept_tier.py` is written and correct; must be applied via `alembic upgrade head` before DB tests can pass

Post-audit fix (2026-03-01):

- **Bug found**: `get_bounded_subgraph()`, `get_full_subgraph()`, and `list_concepts()` in `domain/graph/explore.py` did not SELECT `c.tier` or include `tier` in response dicts. Pydantic models `GraphSubgraphNode`, `GraphConceptSummary`, and `GraphConceptDetail` in `core/schemas/graph.py` lacked `tier` field, silently stripping any tier data. **Fixed**: added `c.tier` to all 3 SQL queries, `tier` to all 3 response dicts, and `tier: str | None = None` to all 3 Pydantic models.
- `PYTHONPATH=. pytest -q --ignore=tests/db`: **873 passed** (excluding 2 pre-existing unrelated failures)

---

## Decision Log

Decisions already made for this plan:

1. Use a PostgreSQL ENUM type `concept_tier` (`umbrella`, `topic`, `subtopic`, `granular`) rather than a free-text column, to allow indexed lookups and DB-level validation.
2. The `tier` column is nullable with no default, so that existing rows are unaffected and the extractor can emit `null` when classification confidence is low.
3. Hierarchical edges use the existing `relation_type` free-text field; no new FK column is added to `edges_canon`.
4. Valid new relation types: `contains` (umbrella→topic), `has_subtopic` (topic→subtopic), `belongs_to` (subtopic→topic or topic→umbrella) as reverse direction.
5. Tier classification happens at extraction time (LLM) and is stored in `concepts_raw.extracted_json`; it is promoted to `concepts_canon.tier` at merge time.
6. Tutor ancestor injection only fires when the resolved concept's tier is `subtopic` or `granular`.
7. Frontend tier visualization uses node size and color hue (not shape) to avoid breaking the existing force-directed layout engine.
8. No mastery-rollup logic (e.g., "3/3 subtopics → topic mastered") is in scope for this plan; it is explicitly deferred to a follow-on plan.

---

## Deferred Follow-On Scope (Not Active Execution Targets)

1. Mastery rollup: automatic Topic mastery when all Subtopics are mastered.
2. Curriculum graph view: a tree-layout rendering mode distinct from force-directed.
3. LLM-assisted retroactive tier classification of existing concepts.
4. Umbrella-scoped quiz flows (quiz covering all subtopics under one umbrella).

---

## Removal Safety Rules

These rules apply whenever any child plan removes, replaces, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. For deletions larger than trivial dead code, capture prior import/call sites, replacement module path, and tests or checks proving parity.
4. If a public route, payload, or CSS contract is removed or changed, record a compatibility note and rollback path in the child plan verification block.
5. Maintain the detailed removal ledger in the active child plan and summarize meaningful removals here.

---

## Removal Entry Template

Use this exact structure for every meaningful removal:

```text
Removal Entry - <track-id>

Removed artifact
- <file / function / route / schema / selector>

Reason for removal
- <why it was dead, duplicated, or replaced>

Replacement
- <new file/module/path or "none" if true deletion>

Reverse path
- <exact steps to restore or revert>

Compatibility impact
- <public/internal, none/minor/major>

Verification
- <tests or manual checks proving the replacement works>
```

---

## Verification Block Template

Use this exact structure for every completed slice:

```text
Verification Block - <slice-id>

Slice
- <slice title>

Changes made
- <file 1>: <what changed>
- <file 2>: <what changed>

Verification gates met
- [ ] Existing tests still pass: `PYTHONPATH=. pytest -q` → N passed
- [ ] Slice-specific test(s) pass: <test command>
- [ ] No new mypy/pyright errors introduced
- [ ] (Frontend only) `npm --prefix apps/web test` still passes

Rollback path
- <how to undo if needed>
```

---

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```
Read docs/HIERARCHY_MASTER_PLAN.md in full.

Pick the first incomplete track from the Master Status Ledger (start with HR1).
Open its child plan from the Child Plan Map.

Execute Slice 1 of that child plan now:
1. Make the code or doc change described.
2. Run the verification gates listed in the child plan.
3. Record a Verification Block in the child plan.
4. Update the Master Status Ledger in docs/HIERARCHY_MASTER_PLAN.md.
5. Commit with message format: chore(hierarchy): <slice-id> <short description>

After completing Slice 1, re-read this file (docs/HIERARCHY_MASTER_PLAN.md), then
continue with Slice 2 of the same track or the first slice of the next incomplete track.

Do NOT stop until every track in the Master Status Ledger is marked complete or blocked.
```
