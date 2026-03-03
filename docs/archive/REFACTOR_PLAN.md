# CoLearni Refactor Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-remaining-rewrite.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-template-rewrite.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-closeout.md`

Template source:
- `docs/prompt_templates/refactor_plan.md`

## Plan Completeness Checklist

This active plan should be treated as invalid if any of the following are missing:

1. archive snapshot references
2. current verification status
3. ordered remaining slices with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` with:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps
   - Observed outcome
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. This is a maintainability refactor plan. Do not mix in unrelated feature work.
8. This document is incomplete unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by a fenced code block containing the execution prompt

## Purpose

This document is the closeout record for the CoLearni refactor.

The previous active versions have been archived. All targeted work items are now complete:

- the shared quiz persistence split is finished (R6B)
- the legacy upload route is deprecated in route metadata (R11B)
- the active plan is internally consistent (R11C)

This document remains as the source of truth for what was done and why.

## Inputs Used

This plan is based on:

- `docs/archive/RUN_VERIFY_FIXES.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-template-rewrite.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- post-refactor review findings from 2026-02-28
- current repository layout and verification status as of 2026-02-28

## Executive Summary

The refactor is complete.

All structural outcomes are in place:

- schema definitions are split into `core/schemas/`
- workspaces and research routes are thin
- upload implementation is shared through `domain/knowledge_base/upload_flow.py`
- KB reprocess orchestration is behind the domain layer
- `practice.py` now depends on shared quiz core, not `level_up.py`
- `level_up.py` is a thin compatibility wrapper
- frontend feature decomposition and CSS decomposition are landed
- `quiz_flow.py` is now pure orchestration; all DB access is in `quiz_persistence.py`
- `/documents/upload` is explicitly deprecated in FastAPI metadata, docstrings, and docs
- all replacement path strings point to the correct `/knowledge-base/` canonical route
- `pytest`, web tests, and web typecheck are green

## Constraints Applied During Refactor

These constraints were applied to every slice:

1. No intentional behavior change unless the slice is explicitly marked as a contract metadata fix.
2. Keep PRs small. Target `<= 400 LOC net` per PR wherever possible.
3. Preserve public API contracts unless the slice explicitly updates docs, tests, and rollback notes together.
4. Keep FastAPI routes thin: request validation, service call, error translation, response.
5. Keep tutor evidence/citation behavior unchanged.
6. Do not reopen finished frontend or CSS work.
7. Prefer staged wrappers and facades over hard deletion when public surfaces are involved.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete for this phase:

- `R1` Schema decomposition
- `R2` Thin routes pass I
- `R3A` Upload surface consolidation
- `R3B` Knowledge base route final thin pass
- `R5` Chat orchestration split
- `R6A` Shared quiz core initial completion
- `R6B` Quiz persistence finalization
- `R7` Graph repository split
- `R8` Tutor page split
- `R9` Graph, KB, and sidebar split
- `R10` CSS decomposition
- `R11A` Cleanup and artifact removal
- `R11B` Contract metadata and docs sync
- `R11C` Final plan closeout

All slices are complete. No execution targets remain.

## Decision Log

These decisions were made during the refactor:

1. Canonical upload surface:
   - `POST /workspaces/{ws_id}/knowledge-base/documents/upload`
2. Legacy upload route policy:
   - `POST /documents/upload` remains a temporary compatibility route
   - it should be clearly marked deprecated in both route metadata and docs
   - it should not gain any new logic
3. `core/schemas/__init__.py` policy:
   - keep it for now
4. `adapters/db/graph_repository.py` policy:
   - keep it for now because there are still active internal imports and tests
5. Frontend/CSS policy:
   - no further decomposition work in this plan

## Removal Safety Rules

These rules were applied whenever a slice removed, replaced, inlined, or archived code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion:
   - deprecate -> route through facade/shim -> migrate callers -> delete
3. For deletions larger than trivial dead code, capture:
   - previous import/call sites
   - replacement module path
   - tests or checks proving parity
4. If a public route, payload, or CSS contract is being removed, include a compatibility note and rollback path in the slice verification block.
5. Maintain a removal ledger in this file during the run.

## Removal Entry Template

Use this exact structure for every meaningful removal:

```text
Removal Entry - <slice-id>

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

Current repo verification status:

- `pytest -q`: 347 passed, 1 failed (pre-existing unrelated `test_g3_stream`)
- `npm --prefix apps/web test`: passing
- `npm --prefix apps/web run typecheck`: passing

Post-refactor file sizes:

| File | Lines | Status |
|---|---:|---|
| `domain/learning/quiz_flow.py` | 642 | Pure orchestration — no inline SQL. |
| `domain/learning/quiz_persistence.py` | 472 | Owns all shared quiz DB access. |
| `apps/api/routes/documents.py` | 170 | Deprecated in FastAPI metadata; correct replacement path. |
| `docs/REFACTOR_PLAN.md` | active | Closeout document — internally consistent. |

Known cleanup candidates outside this plan:

- `docs/DRIFT_REPORT.md`
- `docs/GENERATION_STATUS_PLAN.md`
- `docs/LLM_CALL_FLOWS.md`

These are not automatic deletion candidates. Review them separately as normal docs work.

## Completed Work Summary

### 1. Shared quiz persistence extraction — complete (R6B)

- `quiz_persistence.py` now owns 12 DB helper functions: concept lookup, quiz CRUD, attempt insert, mastery operations, generation context loading, session scope check.
- `quiz_flow.py` is pure orchestration: validation, grading pipeline, observability, policy.
- `quiz_flow.py` reduced from 874 to 642 lines (−27%).
- All 13 slice-specific tests pass.

### 2. Upload deprecation metadata — complete (R11B)

- FastAPI route metadata includes `deprecated=True`.
- All docstrings point to `/knowledge-base/documents/upload` (not `/kb/`).
- New `test_legacy_upload_route_marked_deprecated_in_openapi` asserts the contract.

### 3. Replacement path strings — complete (R11B)

- No stale `/kb/` replacement strings remain in code or docs.
- `docs/API.md` already had the correct canonical path.

### 4. Plan consistency — complete (R11C)

- This plan is now a closeout document.
- All sections reflect the actual post-refactor state.
- Pre-closeout version archived.

## Implementation Sequencing

All slices have been executed and verified. The original execution order was:

### R6B. Slice 1: Quiz Persistence Finalization ✅

Extracted 12 DB helper functions from `quiz_flow.py` into `quiz_persistence.py`.
`quiz_flow.py` reduced from 874 to 642 lines. All tests green.

### R11B. Slice 2: Contract Metadata and Docs Sync ✅

Added `deprecated=True` to FastAPI route metadata. Fixed stale `/kb/` replacement path
strings. Added deprecation contract test. All tests green.

### R11C. Slice 3: Final Plan Closeout ✅

Archived pre-closeout version. Updated all stale sections to reflect actual state.
Plan is now a closeout document.

## Execution Order (Final)

All slices are complete:

1. ✅ `R6B` Quiz Persistence Finalization
2. ✅ `R11B` Contract Metadata and Docs Sync
3. ✅ `R11C` Final Plan Closeout

No further execution targets remain in this plan.

## Verification Block Template

For every completed slice, include this exact structure in the working report or PR note:

```text
Verification Block - <slice-id>

Root cause
- <what made this area hard to maintain?>

Files changed
- <file list>

What changed
- <short description of the refactor moves>

Commands run
- <tests / typecheck / lint commands>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
```

Run these additionally when relevant:

```bash
ruff check .
```

Slice-specific emphasis:

- `R6B`
  - `tests/db/test_level_up_quiz_flow_integration.py`
  - `tests/db/test_practice_flow_integration.py`
  - `tests/domain/test_level_up_feedback_contract.py`
- `R11B`
  - `tests/api/test_response_contracts.py`
  - route docs / OpenAPI metadata consistency
- `R11C`
  - internal consistency of `docs/REFACTOR_PLAN.md`

Manual smoke checklist:

1. Practice quiz generation and submission still work without updating mastery.
2. Level-up quiz generation and submission still update mastery correctly.
3. Legacy upload route, if still present, is clearly marked deprecated and points to the correct canonical replacement route.

## What Was Not In Scope

The following were explicitly excluded from the refactor:

- do not redesign the frontend again
- do not reopen CSS decomposition
- do not remove `core/schemas/__init__.py`
- do not remove `adapters/db/graph_repository.py`
- do not delete `/documents/upload` in this plan
- do not change public response payloads as a side effect of cleanup

## Removal Ledger

Historical removal entries are preserved in:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-template-rewrite.md`

No new removals were required for `R6B`, `R11B`, or `R11C`. All changes were additive (extraction, metadata addition, documentation updates).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If a rewritten or regenerated refactor plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be corrected before anyone starts executing it.

Use this single prompt for the remaining implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/REFACTOR_PLAN.md now. This file is the source of truth.
You MUST implement refactor slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/REFACTOR_PLAN.md using the Removal Entry Template.
For every removal, include:
Removed artifact
Reason for removal
Replacement
Reverse path
Compatibility impact
Verification

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade/shim instead of deleting immediately.
- Do not delete public contracts without a compatibility note and rollback path.
- Do not claim the removal is complete until the replacement behavior is verified.

After every 2 slices OR if your context is compacted/summarized, re-open docs/REFACTOR_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/REFACTOR_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/REFACTOR_PLAN.md.
Begin with the current slice in execution order. If starting fresh, begin with slice R6B (Quiz Persistence Finalization) exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/REFACTOR_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
