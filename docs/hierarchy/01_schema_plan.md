# HR1 Schema Plan (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for Track HR1: Schema & Migrations.
- It does not replace `docs/HIERARCHY_MASTER_PLAN.md`.
- `docs/HIERARCHY_MASTER_PLAN.md` remains the parent source of truth for cross-track constraints and status.

## Plan Completeness Checklist

This child plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 HR1 sub-slices
   - after any context compaction / summarization event
   - before claiming any HR1 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one HR1 sub-slice at a time
   - prefer commit message format: `chore(hierarchy): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` here and update the master status ledger.
5. Do not widen this plan into extractor logic, tutor context injection, or UI work except where this plan explicitly calls for an interface seam.
6. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.
7. Always run Python with `PYTHONPATH=.` from the repo root. This worktree shares top-level package names with sibling repos; plain `pytest` can import the wrong code.

## Purpose

This plan introduces the foundational schema changes required by all other HR tracks.

Earlier work already landed:

- `concepts_canon` with `is_active`, `dirty`, `embedding`, `aliases`, and `description`
- `edges_canon` with a free-text `relation_type` column (no CHECK constraint)
- Alembic migration infrastructure in `adapters/db/migrations/`
- `domain/graph/types.py` with well-typed extraction domain objects

This plan exists because the data model is currently flat: `concepts_canon` has no `tier` column, and there is no way to perform fast SQL queries by concept tier or to distinguish umbrella concepts from granular leaves.

## Inputs Used

- `docs/HIERARCHY_MASTER_PLAN.md`
- `docs/GRAPH.md`
- `adapters/db/graph/__init__.py`
- `adapters/db/graph/concepts.py`
- `domain/graph/explore.py`
- `domain/graph/types.py`
- `adapters/db/migrations/versions/20260224_0001_initial_schema.py`

## Executive Summary

What is already in good shape:

- Alembic migrations are used for all schema changes and run cleanly.
- `CanonicalConceptRow` in `adapters/db/graph/__init__.py` is the single projection point for all DB rows.
- All existing concept SELECT paths go through `_to_canonical_concept()`.
- `domain/graph/types.py` `ExtractedConcept` is the typed extraction domain object.

What is materially missing:

1. No PostgreSQL ENUM type `concept_tier` → DB cannot enforce or index tier values.
2. No `tier` column on `concepts_canon` → all tier classification is lost after extraction.
3. `CanonicalConceptRow` does not carry a `tier` field → projection is incomplete.
4. `ExtractedConcept` has no `tier` attribute → downstream consumers cannot pass tier through.
5. `docs/GRAPH.md` has no documentation for hierarchical edge types or the `tier` column.

The remaining work stays narrow: one additive migration, two small type/projection changes, and one doc update.

## Non-Negotiable Constraints

1. The `tier` column is nullable. Existing rows remain `null` after migration.
2. Do not alter, rename, or drop any existing columns, indexes, or constraints.
3. All SELECT statements that read `concepts_canon` must include `c.tier` after HR1-S2 so the projection is complete.
4. No business logic goes in routes; tier handling belongs only in adapter and domain layers.
5. Keep `PYTHONPATH=. pytest -q` baseline test counts stable at every slice.
6. Do not retroactively assign tiers to existing rows in any migration.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-HR1-A` Alembic migration infrastructure is already in place.
- `BASE-HR1-B` `CanonicalConceptRow` and `_to_canonical_concept()` already exist as the single projection point.
- `BASE-HR1-C` `ExtractedConcept` already exists in `domain/graph/types.py`.

These are not execution targets unless an HR1 slice is blocked by them.

## Remaining Slice IDs

- `HR1-S1` Add concept_tier ENUM and tier column to concepts_canon
- `HR1-S2` Update CanonicalConceptRow and _to_canonical_concept projection
- `HR1-S3` Update ExtractedConcept domain type with optional tier
- `HR1-S4` Document new hierarchical relation types in docs/GRAPH.md

## Decision Log For Remaining Work

1. Use a PostgreSQL ENUM type (`concept_tier`) rather than a `VARCHAR` CHECK constraint, for indexed lookups and DB-level validation.
2. The `tier` column has no DEFAULT; `NULL` means "tier not yet classified" and is always valid.
3. The index `ix_concepts_canon_tier` is a composite `(workspace_id, tier)` to support workspace-scoped tier queries efficiently.
4. `CanonicalConceptRow.tier` is `str | None` (not a Python `Enum`) to keep the projection layer simple and forward-compatible.
5. `VALID_TIERS` is a module-level `frozenset` in `domain/graph/types.py`, not an Enum, to avoid importing SQLAlchemy types into the domain layer.
6. Hierarchical edge types (`contains`, `has_subtopic`, `belongs_to`) use the existing free-text `relation_type` column; no new FK column is added.

## Removal Safety Rules

1. Do not delete the existing `CanonicalConceptRow` fields or `_to_canonical_concept()` logic; only extend them.
2. If any SELECT statement must be changed, verify the full test suite passes before committing.
3. There are no planned removals in HR1. This track is additive only.

## Removal Entry Template

```text
Removal Entry - HR1.x

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

## Current Verification Status

- `PYTHONPATH=. pytest -q`: 555 passed (baseline inherited from HIERARCHY_MASTER_PLAN, as of 2026-03-01)
- No HR1-specific tests exist yet
- Post-implementation status: *not yet updated*

Current hotspots:

| File | Why it still matters |
|---|---|
| `adapters/db/migrations/versions/` | Location for the new concept_tier migration. |
| `adapters/db/graph/__init__.py` | Single projection point; must be extended with `tier`. |
| `adapters/db/graph/concepts.py` | All concept SELECT queries must include `c.tier`. |
| `domain/graph/explore.py` | Also queries `concepts_canon`; must include `c.tier`. |
| `domain/graph/types.py` | `ExtractedConcept` must gain an optional `tier` field. |
| `docs/GRAPH.md` | Must be updated with hierarchical relation types and tier column. |

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### HR1-S1. Slice 1: Add concept_tier ENUM and tier column to concepts_canon

Purpose:

- introduce the DB-level type and column so all subsequent tracks can store tier classification

Root problem:

- `concepts_canon` has no `tier` column and there is no DB type for the four tier values

Files involved:

- `adapters/db/migrations/versions/20260301_0009_concept_tier.py` (new)

Implementation steps:

1. Create a new Alembic migration file at `adapters/db/migrations/versions/20260301_0009_concept_tier.py`.
2. In `upgrade()`:
   - Create PostgreSQL ENUM type `concept_tier` with values `('umbrella', 'topic', 'subtopic', 'granular')`.
   - Add nullable column `tier concept_tier` to `concepts_canon`.
   - Add composite index `ix_concepts_canon_tier` on `(workspace_id, tier)`.
3. In `downgrade()`:
   - Drop index `ix_concepts_canon_tier`.
   - Drop column `tier` from `concepts_canon`.
   - Drop ENUM type `concept_tier`.

What stays the same:

- all existing columns and indexes on `concepts_canon`
- no existing queries require changes in this slice

Verification:

- `alembic upgrade head` runs cleanly with no errors
- `alembic downgrade -1` followed by `alembic upgrade head` produces the same result
- `PYTHONPATH=. pytest -q tests/db/` passes

Exit criteria:

- migration file exists and is syntactically correct
- `alembic upgrade head` succeeds
- test suite stable

### HR1-S2. Slice 2: Update CanonicalConceptRow and _to_canonical_concept projection

Purpose:

- propagate the new `tier` column through the adapter projection layer so all callers receive tier information

Root problem:

- `CanonicalConceptRow` has no `tier` field; `_to_canonical_concept()` does not project it; SELECT queries omit `c.tier`

Files involved:

- `adapters/db/graph/__init__.py`
- `adapters/db/graph/concepts.py`
- `domain/graph/explore.py`

Implementation steps:

1. In `adapters/db/graph/__init__.py`: add `tier: str | None` field to `CanonicalConceptRow`.
2. In `adapters/db/graph/__init__.py`: update `_to_canonical_concept()` to project `row.tier` into the result.
3. In `adapters/db/graph/concepts.py`: update every `SELECT` that reads `concepts_canon` to include `c.tier`.
4. In `domain/graph/explore.py`: update every query that SELECTs from `concepts_canon` to include `c.tier`.

What stays the same:

- all other fields on `CanonicalConceptRow`
- all existing function signatures
- no business logic changes

Verification:

- `PYTHONPATH=. pytest -q tests/db/test_graph_exploration_integration.py tests/db/test_graph_resolver_integration.py` passes
- full suite `PYTHONPATH=. pytest -q` still matches baseline count

Exit criteria:

- `CanonicalConceptRow.tier` is present and populated in all DB read paths
- no test regressions

### HR1-S3. Slice 3: Update ExtractedConcept domain type with optional tier

Purpose:

- allow the extraction pipeline (and tests) to carry tier information through the domain layer

Root problem:

- `ExtractedConcept` in `domain/graph/types.py` has no `tier` attribute; downstream consumers cannot pass tier through

Files involved:

- `domain/graph/types.py`

Implementation steps:

1. Add `tier: str | None = None` to `ExtractedConcept`.
2. Add module-level constant `VALID_TIERS: frozenset[str] = frozenset({'umbrella', 'topic', 'subtopic', 'granular'})` at the top of `domain/graph/types.py` (after imports).

What stays the same:

- all other fields on `ExtractedConcept`
- existing callers that do not pass `tier` continue to work because the field defaults to `None`

Verification:

- `PYTHONPATH=. pytest -q tests/` passes with no regressions

Exit criteria:

- `ExtractedConcept` carries `tier: str | None = None`
- `VALID_TIERS` is importable from `domain/graph/types`
- no existing tests break

### HR1-S4. Slice 4: Document new hierarchical relation types in docs/GRAPH.md

Purpose:

- make hierarchical edge types and the `tier` column part of the official graph contract

Root problem:

- `docs/GRAPH.md` has no mention of tier, `contains`, `has_subtopic`, or `belongs_to`

Files involved:

- `docs/GRAPH.md`

Implementation steps:

1. Add a new section **Hierarchical Edge Types** to `docs/GRAPH.md` describing:
   - `contains` — directed edge from an `umbrella` concept to a `topic` concept; encodes "this umbrella contains this topic".
   - `has_subtopic` — directed edge from a `topic` concept to a `subtopic` concept; encodes "this topic has this subtopic".
   - `belongs_to` — reverse directed edge from a `subtopic` to its parent `topic`, or from a `topic` to its parent `umbrella`; encodes "this concept belongs to its parent".
2. Add the `tier` column (type: `concept_tier ENUM`, nullable) to the **Logical Schema** section of `docs/GRAPH.md`, noting:
   - valid values: `umbrella`, `topic`, `subtopic`, `granular`
   - `NULL` means tier is not yet classified
   - the composite index `ix_concepts_canon_tier` is on `(workspace_id, tier)`

What stays the same:

- all other sections in `docs/GRAPH.md`
- no code changes in this slice

Verification:

- doc review: new sections are present and internally consistent
- `PYTHONPATH=. pytest -q` baseline count still passes (no code changes)

Exit criteria:

- `docs/GRAPH.md` documents all new relation types and the `tier` column
- docs are consistent with the schema changes made in HR1-S1 through HR1-S3

## Completed Verification Blocks

```text
Verification Block - HR1.x

Slice
- <slice title>

Changes made
- <file 1>: <what changed>
- <file 2>: <what changed>

Verification gates met
- [ ] Existing tests still pass: `PYTHONPATH=. pytest -q` → N passed
- [ ] Slice-specific test(s) pass: <test command>
- [ ] No new mypy/pyright errors introduced

Rollback path
- <how to undo if needed>
```

---

### Verification Block - HR1-S1

```
Verification Block - HR1-S1
Slice: Add concept_tier ENUM and tier column to concepts_canon
Changes made:
  adapters/db/migrations/versions/20260301_0009_concept_tier.py: new migration – creates concept_tier ENUM, adds tier column, adds ix_concepts_canon_tier index
Verification gates met:
- [ ] Existing tests: PYTHONPATH=. pytest -q → N passed
- [ ] Slice test(s): PYTHONPATH=. pytest -q tests/db/
- [ ] No new mypy errors
Rollback path: alembic downgrade -1 removes index, column, and ENUM type; delete migration file
```

---

### Verification Block - HR1-S2

```
Verification Block - HR1-S2
Slice: Update CanonicalConceptRow and _to_canonical_concept projection
Changes made:
  adapters/db/graph/__init__.py: added tier: str | None to CanonicalConceptRow; updated _to_canonical_concept() to project row.tier
  adapters/db/graph/concepts.py: all concept SELECT queries now include c.tier
  domain/graph/explore.py: all concepts_canon SELECT queries now include c.tier
Verification gates met:
- [ ] Existing tests: PYTHONPATH=. pytest -q → N passed
- [ ] Slice test(s): PYTHONPATH=. pytest -q tests/db/test_graph_exploration_integration.py tests/db/test_graph_resolver_integration.py
- [ ] No new mypy errors
Rollback path: revert the tier field addition and SELECT changes; re-run pytest to confirm baseline
```

---

### Verification Block - HR1-S3

```
Verification Block - HR1-S3
Slice: Update ExtractedConcept domain type with optional tier
Changes made:
  domain/graph/types.py: added tier: str | None = None to ExtractedConcept; added VALID_TIERS frozenset constant
Verification gates met:
- [ ] Existing tests: PYTHONPATH=. pytest -q → N passed
- [ ] Slice test(s): PYTHONPATH=. pytest -q tests/
- [ ] No new mypy errors
Rollback path: remove tier field and VALID_TIERS from domain/graph/types.py; re-run pytest
```

---

### Verification Block - HR1-S4

```
Verification Block - HR1-S4
Slice: Document new hierarchical relation types in docs/GRAPH.md
Changes made:
  docs/GRAPH.md: added Hierarchical Edge Types section; added tier column to Logical Schema section
Verification gates met:
- [ ] Existing tests: PYTHONPATH=. pytest -q → N passed (no code change)
- [ ] Slice test(s): doc review confirms sections are present and consistent
- [ ] No new mypy errors
Rollback path: revert docs/GRAPH.md to prior state via git checkout
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/HIERARCHY_MASTER_PLAN.md, then read docs/hierarchy/01_schema_plan.md.
Begin with the next incomplete HR1 slice exactly as described.

Execution loop for this child plan:

1. Work on one HR1 slice at a time.
2. Preserve: nullable tier column, no retroactive tier assignment in migrations, PYTHONPATH=. baseline test counts, and additive-only changes to concepts_canon and ExtractedConcept.
3. Run the listed verification gates before claiming a slice complete.
4. When a slice is complete, fill in the corresponding Verification Block in this file.
5. After every 2 completed HR1 slices OR if context is compacted/summarized, re-open docs/HIERARCHY_MASTER_PLAN.md and docs/hierarchy/01_schema_plan.md and restate which HR1 slices remain.
6. Continue to the next incomplete HR1 slice once the previous slice is verified.
7. When all HR1 slices are complete, update the Master Status Ledger in docs/HIERARCHY_MASTER_PLAN.md and immediately open docs/hierarchy/02_extractor_plan.md to continue with HR2.

Do NOT stop just because one slice is complete. Slice completion is only a checkpoint unless the master status ledger shows no remaining incomplete slices in this track.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/HIERARCHY_MASTER_PLAN.md.
Read docs/hierarchy/01_schema_plan.md.
Identify the first incomplete HR1 slice from the Remaining Slice IDs list.
Execute that slice exactly as described — make the code or doc change, run the verification gates, and fill in the Verification Block.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When all HR1 slices are complete, update docs/HIERARCHY_MASTER_PLAN.md and continue with HR2.
```
