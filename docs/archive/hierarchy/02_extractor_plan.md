# Extractor Plan (HR2) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for Track HR2: Extractor Prompts & Logic.
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
   - after every 2 HR2 sub-slices
   - after any context compaction / summarization event
   - before claiming any HR2 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one HR2 sub-slice at a time
   - prefer commit message format: `chore(hierarchy): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` here and update the master status ledger in `docs/HIERARCHY_MASTER_PLAN.md`.
5. Do not widen this plan into tutor context injection (HR3), UI visuals (HR4), or schema migration work (HR1) except where this plan explicitly calls for an interface seam.
6. **HR2 depends on HR1.** The `tier` field must already be present on `ExtractedConcept` (added in HR1) before HR2-S2 wires tier into the extraction parser. HR2-S1 (prompt changes) may land before HR1 is complete; HR2-S2 and later are blocked until HR1 is done.
7. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.
8. Run Python verification from the repo root with `PYTHONPATH=.`.

## Purpose

This plan extends the graph extraction pipeline to recognise and propagate concept tier
(`umbrella`, `topic`, `subtopic`, `granular`) and to emit structural hierarchy edges
(`contains`, `has_subtopic`, `belongs_to`).

Earlier work already landed:

- `domain/graph/types.py` with `ExtractedConcept`, `ExtractedEdge`, `RawGraphExtraction`
- `domain/graph/extraction.py` with `extract_raw_graph_from_chunk()`
- `core/prompting/assets/graph/extract_chunk_v1.md` as the active extraction prompt
- `adapters/db/graph/concepts.py` with `insert_raw_concepts()` and concept upsert helpers

This plan exists because the extraction pipeline has no tier awareness and the prompt does
not instruct the LLM to classify concept position in the learning hierarchy.

## Inputs Used

- `docs/HIERARCHY_MASTER_PLAN.md`
- `docs/GRAPH.md`
- `domain/graph/types.py`
- `domain/graph/extraction.py`
- `domain/graph/resolver.py`
- `domain/graph/resolver_apply.py`
- `adapters/db/graph/concepts.py`
- `core/prompting/assets/graph/extract_chunk_v1.md`
- `tests/domain/test_graph_extraction.py`
- `tests/db/test_graph_resolver_integration.py`

## Executive Summary

What is already in good shape:

- The extraction prompt (`extract_chunk_v1.md`) already produces structured JSON for concepts and edges.
- `_ConceptPayload` in `domain/graph/extraction.py` already validates the LLM response schema.
- `adapters/db/graph/concepts.py` already persists `extracted_json` as JSONB, so a `tier` key can be stored without a schema change on `concepts_raw`.
- `edges_canon.relation_type` is a free-text field with no CHECK constraint; new relation types can be emitted immediately.

What is still materially missing:

1. The extraction prompt does not instruct the LLM to classify concept tier.
2. `_ConceptPayload` does not parse a `tier` field from the LLM JSON response.
3. `ExtractedConcept` has no `tier` field (added in HR1 – this plan depends on that landing first).
4. `insert_raw_concepts()` does not write `tier` into `extracted_json`.
5. The resolver/merge path does not promote `tier` from `concepts_raw` to `concepts_canon`.
6. The extraction prompt does not instruct the LLM to emit `contains`, `has_subtopic`, or `belongs_to` structural edges.

The remaining work must stay narrow:
- Extend the extraction prompt in-place; do not create a new prompt version unless strictly necessary.
- Add `tier` to `_ConceptPayload` as optional; validate against `VALID_TIERS`.
- Wire `tier` through `ExtractedConcept` → `extracted_json` → `concepts_canon.tier` at merge time.
- Emit hierarchical edge types; rely on the existing free-text `relation_type` field.

## Non-Negotiable Constraints

1. `tier` is optional everywhere in the extraction pipeline. The LLM may omit it; the parser must fall back to `None` gracefully.
2. Do not introduce a new prompt file or version for HR2-S1 unless the current file is incompatible; extend `extract_chunk_v1.md` in place.
3. `VALID_TIERS` must be a single authoritative constant defined in `domain/graph/types.py` and imported by both the parser and any tier-validation helper.
4. The tier-promotion upsert in HR2-S3 must never overwrite a non-null canon tier with `null`.
5. Conflict resolution at merge time follows the specificity order: `granular > subtopic > topic > umbrella`.
6. Do not break existing graph resolver, gardener, or exploration tests. Every slice must verify `PYTHONPATH=. pytest -q tests/` against the pre-existing baseline.
7. Hierarchical edges (`contains`, `has_subtopic`, `belongs_to`) are structural, not semantic. Document this distinction in `docs/GRAPH.md` as part of HR2-S4.
8. Keep routes thin – all tier/hierarchy logic belongs in domain or adapter layers.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-E1` `ExtractedConcept`, `ExtractedEdge`, `RawGraphExtraction` are typed and tested in `domain/graph/types.py`.
- `BASE-E2` `extract_raw_graph_from_chunk()` validates LLM output and normalises concepts/edges.
- `BASE-E3` `insert_raw_concepts()` stores `extracted_json` as JSONB; the column can already hold a `tier` key.
- `BASE-E4` `edges_canon.relation_type` is unconstrained free-text; `contains`, `has_subtopic`, `belongs_to` can be stored without a migration.

These are not execution targets unless an HR2 slice is blocked by them.

## Remaining Slice IDs

- `HR2-S1` Update extraction prompt to classify concept tier
- `HR2-S2` Update extraction response parsing to read tier (**blocked on HR1**)
- `HR2-S3` Promote tier from `concepts_raw` to `concepts_canon` at merge time (**blocked on HR1 + HR2-S2**)
- `HR2-S4` Update extraction to emit hierarchical edges

## Decision Log For Remaining Work

1. Extend `extract_chunk_v1.md` in place rather than versioning a new prompt file; the change is additive and the task_type/version header can be bumped if needed in a follow-on.
2. `VALID_TIERS` is a `frozenset[str]` constant in `domain/graph/types.py` to avoid circular imports.
3. `_ConceptPayload.tier` is typed `str | None` with no enum enforcement at Pydantic level; validation against `VALID_TIERS` happens in the `ExtractedConcept` constructor path inside `extract_raw_graph_from_chunk()`.
4. The `tier` value is written to `extracted_json` as `{"description": ..., "tier": "..."}` in `insert_raw_concepts()`; no `concepts_raw` schema change is required.
5. Tier promotion at merge time uses a targeted SQL update that only fills `tier` when the canon row has `tier IS NULL`; the conflict resolution (granular > subtopic > topic > umbrella) is applied in the Python layer before the SQL call, not in a SQL expression.
6. HR2-S4 adds two sentences to the extraction prompt instructing the LLM to emit structural edges; no new prompt template is introduced.

## Removal Safety Rules

1. Do not delete the current extraction prompt or parser without recording what is removed, why, and how to restore it.
2. Prefer extending existing functions over replacing them.
3. If `_ConceptPayload` or `_RawGraphPayload` in `extraction.py` is modified, record the diff in the verification block.
4. Maintain the detailed removal ledger in this plan and summarise meaningful removals in `docs/HIERARCHY_MASTER_PLAN.md`.

## Removal Entry Template

```text
Removal Entry - HR2.x

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

- `PYTHONPATH=. pytest -q`: 555 passed (inherited from HIERARCHY_MASTER_PLAN baseline, 2026-03-01)
- `npm --prefix apps/web test`: 87 passed (13 test files, 2026-03-01)
- No HR2-specific tests exist yet

Current hotspots:

| File | Why it matters for HR2 |
|---|---|
| `core/prompting/assets/graph/extract_chunk_v1.md` | Active extraction prompt; must be extended with tier classification and hierarchical edge instructions. |
| `domain/graph/extraction.py` | Contains `_ConceptPayload` and `extract_raw_graph_from_chunk()`; must parse `tier` from LLM output. |
| `domain/graph/types.py` | `ExtractedConcept` must gain a `tier` field (HR1 dependency); `VALID_TIERS` constant defined here. |
| `adapters/db/graph/concepts.py` | `insert_raw_concepts()` must write `tier` into `extracted_json`; `create_canonical_concept()` / `update_canonical_concept()` must accept and persist `tier`. |
| `domain/graph/resolver.py` | Resolver merge path must propagate `tier` when creating or updating canon rows. |

## Remaining Work Overview

### HR2-S1. Slice 1: Update extraction prompt to classify concept tier

Purpose:

- Instruct the LLM to emit a `tier` field on each concept so that extraction produces tier-classified output from the first document processed after deployment.

Root problem:

- The current extraction prompt has no mention of tiers; the LLM has no guidance to classify concepts as umbrella, topic, subtopic, or granular.

Files involved:

- `core/prompting/assets/graph/extract_chunk_v1.md`

Implementation steps:

1. Add a brief rule (under `---Non-negotiable rules---`) instructing the LLM to classify each concept as one of `umbrella`, `topic`, `subtopic`, or `granular`, or omit the field entirely when confidence is low.
2. Add a `tier` field to the JSON schema example in the `---Output contract---` section.
3. Add a short explanation of the four tiers directly in the prompt so the LLM has grounding.
4. Keep the change additive; do not rename or remove any existing field.

What stays the same:

- All other prompt rules, fields, and failure behavior.
- The `_ConceptPayload` parser is not changed in this slice (tier field is not yet wired).

Verification:

- Prompt file `core/prompting/assets/graph/extract_chunk_v1.md` is modified.
- `PYTHONPATH=. pytest -q tests/` passes (no behavioral change yet; parser ignores unknown fields due to `extra="forbid"` – note: must confirm this does not reject `tier` before HR2-S2 lands; if it does, temporarily set `extra="ignore"` or defer the prompt change until HR2-S2).

Exit criteria:

- The prompt clearly instructs tier classification with a JSON schema example showing the `tier` field.
- All existing tests still pass.

### HR2-S2. Slice 2: Update extraction response parsing to read tier

**Blocked on HR1** – `ExtractedConcept.tier` must exist before this slice can pass type checks.

Purpose:

- Parse the `tier` field emitted by the LLM and propagate it through to `ExtractedConcept` and `concepts_raw.extracted_json`.

Root problem:

- `_ConceptPayload` does not declare a `tier` field; any `tier` in the LLM response is currently rejected by `extra="forbid"`.
- `ExtractedConcept` has no `tier` field to carry the value forward.
- `insert_raw_concepts()` does not write `tier` into `extracted_json`.

Files involved:

- `domain/graph/types.py` (add `VALID_TIERS` constant; `tier` field already added by HR1)
- `domain/graph/extraction.py` (add `tier` to `_ConceptPayload`; validate against `VALID_TIERS` in `extract_raw_graph_from_chunk()`)
- `adapters/db/graph/concepts.py` (`insert_raw_concepts()` writes `tier` into `extracted_json`)
- `tests/domain/test_graph_extraction.py` (add tier-parsing unit tests)

Implementation steps:

1. Add `VALID_TIERS: frozenset[str] = frozenset({"umbrella", "topic", "subtopic", "granular"})` to `domain/graph/types.py`.
2. Add `tier: str | None = None` to `_ConceptPayload` in `domain/graph/extraction.py`.
3. In `extract_raw_graph_from_chunk()`, when constructing `ExtractedConcept`, read `concept.tier`; set to `None` if the value is not in `VALID_TIERS`.
4. Update `insert_raw_concepts()` in `adapters/db/graph/concepts.py` to include `"tier": concept.tier` in the `extracted_json` dict (omitting the key if `tier` is `None`).
5. Add unit tests in `tests/domain/test_graph_extraction.py` covering:
   - Valid tier values pass through unchanged.
   - Unrecognized tier value is silently set to `None`.
   - Missing `tier` key in LLM output produces `tier=None` on `ExtractedConcept`.

What stays the same:

- All existing `ExtractedConcept` construction paths for `name`, `context_snippet`, `description`.
- The merge/de-dupe logic for concepts within a single chunk.

Verification:

- Unit test: `PYTHONPATH=. pytest -q tests/domain/test_graph_extraction.py` passes.
- Full suite: `PYTHONPATH=. pytest -q tests/` passes.

Exit criteria:

- `ExtractedConcept.tier` is populated from LLM output for recognized values and `None` otherwise.
- `concepts_raw.extracted_json` contains the `tier` key whenever the LLM emits a recognized tier.
- All prior extraction tests still pass.

### HR2-S3. Slice 3: Promote tier from `concepts_raw` to `concepts_canon` at merge time

**Blocked on HR1 + HR2-S2.**

Purpose:

- Ensure that when raw concepts are resolved and merged into `concepts_canon`, the `tier` value from `concepts_raw.extracted_json` is promoted to `concepts_canon.tier`.

Root problem:

- Even after HR2-S2 stores `tier` in `extracted_json`, the resolver never reads it, so `concepts_canon.tier` remains `NULL` forever.

Files involved:

- `domain/graph/resolver.py` (read `tier` from `ExtractedConcept` when creating/updating canon rows)
- `adapters/db/graph/concepts.py` (`create_canonical_concept()` and `update_canonical_concept()` accept and persist `tier`)
- `domain/graph/resolver_apply.py` (add `pick_tier()` helper implementing specificity ordering)
- `tests/domain/test_graph_extraction.py` or new `tests/domain/test_tier_promotion.py` (unit tests for `pick_tier()`)
- `tests/db/test_graph_resolver_integration.py` (integration test for tier promotion at merge time)

Implementation steps:

1. Add a `pick_tier(existing: str | None, incoming: str | None) -> str | None` helper to `domain/graph/resolver_apply.py` that returns the more specific tier, using the order `granular > subtopic > topic > umbrella`. If both are `None`, return `None`; if only one is set, return it.
2. Update `create_canonical_concept()` in `adapters/db/graph/concepts.py` to accept an optional `tier: str | None` parameter and write it to the `concepts_canon.tier` column.
3. Update `update_canonical_concept()` in `adapters/db/graph/concepts.py` to accept an optional `tier: str | None = None` parameter; update `concepts_canon.tier` only when the incoming tier is more specific than the existing one (use the `pick_tier()` logic), never setting `tier` to `NULL` from a non-null value.
4. Update the resolver (`domain/graph/resolver.py`) to read `concept.tier` from the `ExtractedConcept` and pass it through `pick_tier()` before calling the canon create/update helpers.
5. Add a unit test for `pick_tier()` in `tests/domain/` covering all conflict combinations.
6. Add or extend an integration test in `tests/db/test_graph_resolver_integration.py` to verify that a concept with a recognized tier ends up with that tier on the canon row after resolution.

What stays the same:

- All existing resolver merge logic for aliases, descriptions, and embeddings.
- The `merge_description()` and `merge_aliases()` functions are unchanged.
- The resolver budget system is unchanged.
- Existing canon rows with `tier IS NULL` remain `NULL` unless a matching raw concept provides a tier.

Verification:

- `PYTHONPATH=. pytest -q tests/db/test_graph_resolver_integration.py` passes.
- `PYTHONPATH=. pytest -q tests/` passes.

Exit criteria:

- Canon rows gain a non-null `tier` when any matching raw concept carries one.
- Canon tier is never downgraded to a less-specific tier.
- All existing resolver integration tests still pass.

### HR2-S4. Slice 4: Update extraction to emit hierarchical edges

Purpose:

- Instruct the LLM to emit `contains`, `has_subtopic`, and `belongs_to` edge relation types when a clear parent→child structural relationship exists in the chunk.

Root problem:

- The extraction prompt describes generic semantic edges; it does not distinguish structural hierarchy edges from knowledge edges, and the LLM never emits `contains`, `has_subtopic`, or `belongs_to` relation types.

Files involved:

- `core/prompting/assets/graph/extract_chunk_v1.md`
- `docs/GRAPH.md` (document the new relation types)

Implementation steps:

1. Add a rule in the `---Non-negotiable rules---` section of the extraction prompt stating:
   - When a concept is a parent of another (e.g., a topic that structurally contains a subtopic), emit an edge with `relation_type` set to `contains` (parent→child), `has_subtopic` (topic→subtopic), or `belongs_to` (child→parent reverse).
   - These edges are *structural* (hierarchy), not semantic (knowledge). Emit them only when the parent/child relationship is explicit in the chunk, not inferred.
2. Add example entries for `contains`, `has_subtopic`, and `belongs_to` in the JSON schema example in `---Output contract---`.
3. Update `docs/GRAPH.md` to document `contains`, `has_subtopic`, and `belongs_to` as structural hierarchy relation types with a note that they are additive and do not replace semantic edge types.
4. No code changes required – the existing `ExtractedEdge` and `relation_type` field already handle arbitrary strings.

What stays the same:

- All semantic edge types already in use.
- No schema changes; `relation_type` remains a free-text field.
- The extraction parser in `domain/graph/extraction.py` is unchanged.

Verification:

- Prompt file `core/prompting/assets/graph/extract_chunk_v1.md` is modified.
- `docs/GRAPH.md` is updated with the three new relation type entries.
- `PYTHONPATH=. pytest -q tests/` passes (no behavioral change to the parser).
- Existing edge tests in `tests/domain/test_graph_extraction.py` still pass.

Exit criteria:

- The extraction prompt can produce `contains`, `has_subtopic`, and `belongs_to` edges when the LLM sees a clear structural relationship.
- `docs/GRAPH.md` documents the structural vs. semantic edge distinction.
- All existing tests still pass.

## Completed Verification Blocks

*(None yet – updated as slices complete.)*

```text
Verification Block - HR2-Sx

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

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/HIERARCHY_MASTER_PLAN.md, then read docs/hierarchy/02_extractor_plan.md.
Begin with the next incomplete HR2 slice exactly as described.

Pre-flight check:
- HR2-S1 (prompt change) may proceed independently.
- HR2-S2, HR2-S3 are blocked until HR1 (tier field on ExtractedConcept) is complete.
  Confirm HR1 is done before starting HR2-S2.
- HR2-S4 (hierarchical edges in prompt) may proceed independently of HR1.

Execution loop for this child plan:

1. Work on one HR2 slice at a time.
2. Never overwrite a non-null concepts_canon.tier with null; never downgrade tier specificity.
3. Keep all tier validation against VALID_TIERS in domain/graph/types.py.
4. Run the listed verification steps before claiming a slice complete.
5. When a slice is complete, add:
   - the Verification Block for that slice
   - a summary of all Removal Entries added during that slice
   - an update to the Master Status Ledger in docs/HIERARCHY_MASTER_PLAN.md
6. After every 2 completed HR2 slices OR if context is compacted/summarized, re-open
   docs/HIERARCHY_MASTER_PLAN.md and docs/hierarchy/02_extractor_plan.md and restate
   which HR2 slices remain.
7. Continue to the next incomplete HR2 slice once the previous slice is verified.
8. When all HR2 slices are complete, immediately re-open docs/HIERARCHY_MASTER_PLAN.md,
   update HR2 status to complete, and select the next incomplete track.

Do NOT stop just because one HR2 slice is complete.
HR2 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions,
a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/HIERARCHY_MASTER_PLAN.md.
Read docs/hierarchy/02_extractor_plan.md.
Identify the first unblocked HR2 slice and begin it now.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When HR2 is complete, immediately return to docs/HIERARCHY_MASTER_PLAN.md and continue
with the next incomplete child plan.
```
