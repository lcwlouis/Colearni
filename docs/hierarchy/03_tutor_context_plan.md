# Tutor Context Injection Plan (HR3) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for injecting concept hierarchy context into the tutor retrieval path.
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
   - after every 2 HR3 sub-slices
   - after any context compaction / summarization event
   - before claiming any HR3 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one HR3 sub-slice at a time
   - prefer commit message format: `chore(hierarchy): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` here and update the master status ledger.
5. Do not widen this plan into schema migration, extractor prompt changes, or frontend UI work except where this plan explicitly calls for a data-reading seam.
6. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan injects concept hierarchy context into the tutor's retrieval path so that when the active concept is a `subtopic` or `granular` node, the tutor receives the names and descriptions of its ancestor concepts as additional system context. This addresses **Topic Drift**: without ancestor context the LLM tends toward associative tangents when operating on deeply nested concepts.

Earlier work already landed:

- flat hybrid retrieval and concept-bias boosting in `domain/chat/retrieval_context.py`
- concept inference and switch-suggestion policy in `domain/chat/concept_resolver.py`
- hierarchical edge types (`belongs_to`, `has_subtopic`) as additive `relation_type` values (HR1)
- `tier` column on `concepts_canon` (HR1)

This plan exists because the hierarchy data introduced by HR1 is not yet read by the tutor context path.

## Inputs Used

- `docs/HIERARCHY_MASTER_PLAN.md`
- `docs/GRAPH.md`
- `domain/graph/explore.py`
- `domain/chat/retrieval_context.py`
- `domain/chat/concept_resolver.py`
- `core/schemas/chat.py`
- `adapters/db/graph/concepts.py`

## Executive Summary

What is already in good shape:

- `domain/graph/explore.py` already has a recursive CTE pattern (`_RANKED_REACH_CTE`) and a `get_concept_detail()` function using the same `concepts_canon` / `edges_canon` schema.
- `domain/chat/retrieval_context.py` already has `apply_concept_bias()` as a post-retrieval step that can serve as a model for injecting additional context.
- `domain/chat/concept_resolver.py` resolves the active concept before retrieval in both blocking and streaming paths.
- `ConceptInfo` already carries `concept_id` and `canonical_name`; it only needs `tier` added.

What is still materially missing:

1. No function to walk ancestor edges upward from a concept to return its ancestry chain.
2. No injection of ancestor names/descriptions into the tutor system context when the concept tier is `subtopic` or `granular`.
3. `ConceptInfo` and the resolved-concept API payload do not carry `tier`, so callers cannot gate ancestor injection without an extra DB lookup.

The remaining work is narrow: one new pure function in `explore.py`, one small extension to `retrieval_context.py`, and a minimal schema/resolver change to surface `tier` on the existing resolved-concept payload.

## Non-Negotiable Constraints

1. **HR3 depends on HR1.** The `tier` column and `belongs_to` / `has_subtopic` edge types must exist before any HR3 slice can be verified end-to-end. Run HR1 first.
2. If no hierarchical edges exist for a concept, `get_ancestor_chain()` MUST return an empty list immediately; the tutor fallback to existing behavior must be exact.
3. If `tier` is `None` or the ancestor chain is empty, ancestor injection is skipped entirely — no partial or empty "Concept hierarchy context:" string must be prepended.
4. No route contract breakage: adding `tier` to `ConceptInfo` and to any API payload must be additive (optional field, default `None`).
5. Keep routes thin — all hierarchy lookup logic belongs in `domain/graph/explore.py` and `domain/chat/`, not in FastAPI route handlers.
6. Preserve `verify_assistant_draft()` as the final answer gate.
7. `PYTHONPATH=. pytest -q` baseline must stay green after every slice.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-H1` `edges_canon.relation_type` is already a free-text field; `belongs_to` and `has_subtopic` are valid additive values.
- `BASE-H2` `domain/graph/explore.py` already demonstrates the recursive CTE and session-guard patterns to reuse.
- `BASE-H3` `domain/chat/concept_resolver.py` already queries `concepts_canon` for `id` and `canonical_name`; adding `tier` to that query is a one-line change.

These are not execution targets unless an HR3 slice is blocked by them.

## Remaining Slice IDs

- `HR3-S1` Add ancestor lookup function to `domain/graph/explore.py`
- `HR3-S2` Inject ancestor context into retrieval context when concept tier is `subtopic` or `granular`
- `HR3-S3` Expose `tier` on the concept resolution API response

## Decision Log For Remaining Work

1. Ancestor lookup walks edges whose `relation_type` is `belongs_to` or `has_subtopic`. These are the two hierarchical upward-direction edge types introduced by HR1. The traversal direction treats the active concept as the child.
2. `max_depth=3` is the default cap for `get_ancestor_chain()`. Three levels is sufficient to reach an umbrella from a granular node (granular→subtopic→topic→umbrella). This avoids unbounded recursive queries.
3. The ancestor chain is prepended as a single plain-text line: `"Concept hierarchy context: <name1> > <name2> > ..."` where items are ordered from nearest to furthest ancestor. The separator `" > "` is intentionally human-readable and prompt-safe.
4. `tier` is stored as a plain `str | None` in Python (not an enum class) for schema-level compatibility; the DB enum values are `umbrella`, `topic`, `subtopic`, `granular`.
5. `ConceptInfo` is extended with an optional `tier: str | None = None` field. This is backward-compatible because it is a frozen dataclass with a default value.
6. The `tier` field on the API payload is `str | None` (optional). Callers that do not need it can ignore it.
7. Ancestor injection happens in `domain/chat/retrieval_context.py` as a new exported function `build_ancestor_context_line()`. The callers (`respond.py`, `stream.py`) are responsible for prepending this line to the system context block.

## Removal Safety Rules

1. Do not delete any existing function, class, or field from `concept_resolver.py` or `retrieval_context.py` — only add.
2. If `ConceptInfo` gains a new field, ensure all existing construction sites pass the default (no positional-argument breakage).
3. Maintain a removal ledger here if anything is replaced.

## Removal Entry Template

```text
Removal Entry - HR3.x

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

- `PYTHONPATH=. pytest -q`: 555 passed (inherited from HIERARCHY_MASTER_PLAN baseline, as of 2026-03-01)
- `npm --prefix apps/web test`: 87 passed (13 test files, as of 2026-03-01)
- HR3-specific tests: none yet

Current hotspots:

| File | Why it still matters |
|---|---|
| `domain/graph/explore.py` | Must gain `get_ancestor_chain()` before HR3-S2 can be implemented. |
| `domain/chat/retrieval_context.py` | Will gain `build_ancestor_context_line()` in HR3-S2. |
| `domain/chat/concept_resolver.py` | Must fetch and propagate `tier` in HR3-S3. |
| `core/schemas/chat.py` | May need `tier: str \| None` added to the resolved-concept payload in HR3-S3. |

## Remaining Work Overview

### 1. No ancestor lookup function exists

`domain/graph/explore.py` has recursive CTE infrastructure but no function that walks upward through hierarchical edges to collect ancestor names and descriptions.

### 2. Tutor context is flat

`domain/chat/retrieval_context.py` retrieves and biases chunks but never prepends any hierarchy-aware system context. The tutor LLM sees no information about where a granular or subtopic concept sits in the broader knowledge graph.

### 3. Tier is invisible to callers

`ConceptInfo` and the API payload produced by `resolve_concept_for_turn()` carry only `concept_id` and `canonical_name`. Without `tier`, callers must issue a second DB round-trip to gate ancestor injection, which is wasteful and fragile.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### HR3-S1. Slice 1: Add ancestor lookup function to `domain/graph/explore.py`

Purpose:

- provide a reusable function that walks `edges_canon` upward through `belongs_to` and `has_subtopic` edges to return the ancestor chain for a given concept

Root problem:

- no function exists to traverse hierarchy edges upward; callers have no way to build ancestry context without writing ad-hoc SQL

Files involved:

- `domain/graph/explore.py`
- `tests/domain/test_ancestor_chain.py` (new) — or `tests/db/test_ancestor_chain.py` if the test requires a live DB fixture

Implementation steps:

1. Add `get_ancestor_chain(session, workspace_id, concept_id, max_depth=3) -> list[dict[str, str]]` to `domain/graph/explore.py`.
2. Guard at the top: if `session` does not have an `execute` attribute, return `[]` immediately.
3. Use a recursive CTE walking `edges_canon` where `relation_type IN ('belongs_to', 'has_subtopic')` and the active concept is either `src_id` or `tgt_id`, following the upward direction only (parent side).
4. Cap recursion at `max_depth` to satisfy the no-unbounded-loops budget rule.
5. Return a list of `{"name": canonical_name, "description": description}` dicts, ordered from nearest to furthest ancestor. Return `[]` if no hierarchical edges are found.
6. Add to `__all__` in `explore.py`.
7. Write unit tests using a mock session (or a minimal in-memory fixture) that cover: no-edges guard, single ancestor, max_depth cap, empty workspace.

What stays the same:

- all existing functions in `explore.py` are untouched
- no public route or schema changes

Verification:

- `PYTHONPATH=. pytest -q tests/domain/` (or `tests/db/`) passes
- New test file covers guard path, happy path, and depth cap

Exit criteria:

- `get_ancestor_chain()` is callable and returns the expected structure
- All new and existing tests pass

### HR3-S2. Slice 2: Inject ancestor context into retrieval context when concept tier is `subtopic` or `granular`

Purpose:

- prepend a brief ancestry context string to the tutor system context block when the resolved concept is a `subtopic` or `granular` node

Root problem:

- the tutor LLM currently has no knowledge of where a granular concept sits in the hierarchy, leading to topic drift when operating on deeply nested nodes

Files involved:

- `domain/chat/retrieval_context.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- `tests/domain/test_ancestor_injection.py` (new)

Implementation steps:

1. Add `build_ancestor_context_line(session, workspace_id, concept_id, tier) -> str | None` to `domain/chat/retrieval_context.py`.
2. Inside that function:
   a. If `tier` is `None` or not in `{"subtopic", "granular"}`, return `None` immediately.
   b. Call `get_ancestor_chain(session, workspace_id=workspace_id, concept_id=concept_id)`.
   c. If the chain is empty, return `None`.
   d. Format as `"Concept hierarchy context: " + " > ".join(item["name"] for item in chain)` and return the string.
3. In `domain/chat/respond.py`, after concept resolution and before prompt assembly, call `build_ancestor_context_line()` and — if non-`None` — prepend the result to the system context string passed to the LLM.
4. Apply the same change to `domain/chat/stream.py` to maintain blocking/streaming parity.
5. Write unit tests for `build_ancestor_context_line()` covering: `tier=None` guard, `tier="topic"` guard, empty chain, non-empty chain formatting.

What stays the same:

- if the guard fires or the chain is empty, the tutor path is byte-for-byte identical to the pre-HR3 behavior
- no changes to retrieval, reranking, or answer verification

Verification:

- `PYTHONPATH=. pytest -q tests/domain/` passes
- New test file covers all guard paths and formatting
- Manual tutor chat turn on a `subtopic` concept shows ancestry prefix in the assembled prompt (log or trace output)

Exit criteria:

- `build_ancestor_context_line()` is tested and exported
- Both blocking and streaming paths inject context identically
- Guards ensure zero regression when `tier` is `None` or chain is empty

### HR3-S3. Slice 3: Expose `tier` on the concept resolution API response

Purpose:

- surface the resolved concept's `tier` on `ConceptInfo` and on any API payload that carries resolved-concept data, so callers can gate ancestor injection without a second DB round-trip

Root problem:

- `ConceptInfo` only has `concept_id` and `canonical_name`; callers must issue a separate query to learn the tier, which is wasteful and will be called in every tutor turn

Files involved:

- `domain/chat/concept_resolver.py`
- `core/schemas/chat.py` (or wherever the resolved-concept API payload is defined)
- `tests/domain/test_concept_resolver.py` (extend existing) or a new test file

Implementation steps:

1. In `domain/chat/concept_resolver.py`:
   a. Add `tier: str | None = None` to the `ConceptInfo` frozen dataclass.
   b. Update `_concept_by_id()` to also `SELECT tier` from `concepts_canon`.
   c. Populate `ConceptInfo.tier` from that row in all construction sites inside `concept_resolver.py`.
   d. In `_fallback_resolution()`, leave `tier=None` (fallback cannot know the tier).
2. In `core/schemas/chat.py` (or wherever `ConceptResolution`/`ConceptInfo` is re-serialized into an API schema), add `tier: str | None = None` as an optional field.
3. Ensure no existing positional-argument `ConceptInfo(...)` call breaks — the field must use a keyword default.
4. Extend or add unit tests asserting that `_concept_by_id()` returns the correct tier when the DB row has a tier set, and `None` when it does not.

What stays the same:

- all existing `ConceptResolution` fields are unchanged
- no route handler logic changes
- fallback resolution returns `tier=None` (unchanged behavior)

Verification:

- `PYTHONPATH=. pytest -q` passes with no regressions
- New/extended test asserts `ConceptInfo.tier` is populated correctly
- No route contract breakage: `tier` field is optional with a `None` default

Exit criteria:

- `ConceptInfo.tier` is available to callers in both blocking and streaming paths
- API payload round-trips correctly with `tier=None` for old rows and a tier string for new ones

## Completed Verification Blocks

```text
Verification Block - HR3.x

Slice
- <slice title>

Changes made
- <file 1>: <what changed>
- <file 2>: <what changed>

Verification gates met
- [ ] Existing tests still pass: `PYTHONPATH=. pytest -q` → N passed
- [ ] Slice-specific test(s) pass: <test command and result>
- [ ] No new mypy/pyright errors introduced
- [ ] (Frontend only) `npm --prefix apps/web test` still passes

Rollback path
- <how to undo if needed>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/HIERARCHY_MASTER_PLAN.md, then read docs/hierarchy/03_tutor_context_plan.md.

Confirm that HR1 (Schema & Migrations) is marked complete in the Master Status Ledger before
proceeding. HR3 cannot be verified end-to-end without the `tier` column and hierarchical
edge relation types from HR1.

Execution loop for this child plan:

1. Work on one HR3 slice at a time in order: HR3-S1 → HR3-S2 → HR3-S3.
2. For HR3-S1: implement `get_ancestor_chain()` in `domain/graph/explore.py`, write unit
   tests in `tests/domain/` or `tests/db/`, run `PYTHONPATH=. pytest -q` and confirm green.
3. For HR3-S2: implement `build_ancestor_context_line()` in `domain/chat/retrieval_context.py`,
   wire it into both `domain/chat/respond.py` and `domain/chat/stream.py`, write unit tests,
   run `PYTHONPATH=. pytest -q tests/domain/` and confirm green.
4. For HR3-S3: extend `ConceptInfo` with `tier: str | None = None`, update `_concept_by_id()`
   to fetch `tier`, add `tier` to the relevant API schema, run `PYTHONPATH=. pytest -q` and
   confirm no regressions and no route contract breakage.
5. After each slice:
   - Fill in the Verification Block template in this file with the actual commands run and
     results observed.
   - Update the Master Status Ledger in docs/HIERARCHY_MASTER_PLAN.md.
   - Commit with message format: `chore(hierarchy): <slice-id> <short description>`
6. After every 2 completed HR3 slices OR if context is compacted/summarized, re-open
   docs/HIERARCHY_MASTER_PLAN.md and docs/hierarchy/03_tutor_context_plan.md and restate
   which HR3 slices remain.
7. When all HR3 slices are complete, immediately re-open docs/HIERARCHY_MASTER_PLAN.md,
   update the Master Status Ledger, and continue with the next incomplete track.

Constraints to preserve throughout:
- If `tier` is None or ancestor chain is empty, skip injection entirely (exact fallback).
- `get_ancestor_chain()` must return [] immediately if no hierarchical edges exist.
- `ConceptInfo.tier` must default to None to avoid breaking existing construction sites.
- Blocking and streaming paths must be kept in parity at every slice.

Do NOT stop just because one HR3 slice is complete. Continue to the next slice.
Stop only if verification fails, the code no longer matches plan assumptions, HR1 is not yet
complete, or the next slice would widen scope beyond this plan.

START:

Read docs/HIERARCHY_MASTER_PLAN.md.
Read docs/hierarchy/03_tutor_context_plan.md.
Confirm HR1 is complete.
Begin with HR3-S1 exactly as described above.
Do not proceed to HR3-S2 until HR3-S1 is verified.
```
