# CoLearni Refactor Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-remaining-rewrite.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-template-rewrite.md`

Template source:
- `docs/prompt_templates/refactor_plan.md`

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

## Purpose

This document is now the follow-up refactor plan after the second refactor wave.

The previous active version has been archived. This file now targets only the items that were still missed in the post-refactor review:

- the shared quiz persistence split is only partially complete
- the legacy upload route is deprecated in human docs but not fully in route metadata
- the active plan itself still contains stale prose from before completed slices landed

Use this document as the source of truth for the remaining cleanup. If implementation discovers a new constraint, update this file before widening scope.

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

The refactor is mostly successful.

The expected structural outcomes are already in place:

- schema definitions are split into `core/schemas/`
- workspaces and research routes are thin
- upload implementation is shared through `domain/knowledge_base/upload_flow.py`
- KB reprocess orchestration is behind the domain layer
- `practice.py` now depends on shared quiz core, not `level_up.py`
- `level_up.py` is a thin compatibility wrapper
- frontend feature decomposition and CSS decomposition are landed
- `pytest`, web tests, and web typecheck are green

The remaining work is small but still worth doing because it affects source-of-truth quality and architectural finish:

1. `domain/learning/quiz_flow.py` still contains most shared quiz SQL, so the persistence seam promised in the prior plan is only partially complete.
2. `/documents/upload` is deprecated in docs but not fully marked as deprecated in FastAPI/OpenAPI metadata.
3. `apps/api/routes/documents.py` still points users at the wrong replacement path string (`/kb/...` instead of `/knowledge-base/...`).
4. This plan still contains stale narrative sections that say completed work is unfinished.

The right move now is a short final pass focused on persistence extraction, contract metadata sync, and plan closeout.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. No intentional behavior change unless the slice is explicitly marked as a contract metadata fix.
2. Keep PRs small. Target `<= 400 LOC net` per PR wherever possible.
3. Preserve public API contracts unless the slice explicitly updates docs, tests, and rollback notes together.
4. Keep FastAPI routes thin: request validation, service call, error translation, response.
5. Keep tutor evidence/citation behavior unchanged.
6. Do not reopen finished frontend or CSS work.
7. Prefer staged wrappers and facades over hard deletion when public surfaces are involved.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `R1` Schema decomposition
- `R2` Thin routes pass I
- `R3A` Upload surface consolidation
- `R3B` Knowledge base route final thin pass
- `R5` Chat orchestration split
- `R6A` Shared quiz core initial completion
- `R7` Graph repository split
- `R8` Tutor page split
- `R9` Graph, KB, and sidebar split
- `R10` CSS decomposition
- `R11A` Cleanup and artifact removal

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `R6B` Quiz Persistence Finalization
- `R11B` Contract Metadata and Docs Sync
- `R11C` Final Plan Closeout

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

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

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

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

- `pytest -q`: passing
- `npm --prefix apps/web test`: passing
- `npm --prefix apps/web run typecheck`: passing

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `domain/learning/quiz_flow.py` | 873 | Shared quiz orchestration still contains most DB queries and persistence writes. |
| `domain/learning/quiz_persistence.py` | 69 | Only partially filled; currently holds summary lookup only. |
| `apps/api/routes/documents.py` | 169 | Compatibility route is thin, but route metadata and deprecation strings are still inconsistent. |
| `docs/REFACTOR_PLAN.md` | active | Still contains stale sections if not rewritten cleanly. |

Known cleanup candidates outside this plan:

- `docs/DRIFT_REPORT.md`
- `docs/GENERATION_STATUS_PLAN.md`
- `docs/LLM_CALL_FLOWS.md`

These are not automatic deletion candidates. Review them separately as normal docs work.

## Remaining Work Overview

### 1. Shared quiz persistence extraction is only partially finished

The outcome-level architecture improved:

- `practice.py` no longer imports `level_up.py`
- `level_up.py` is a wrapper
- shared orchestration exists in `quiz_flow.py`

But the seam promised in the prior plan is only partial:

- `quiz_persistence.py` only contains the latest-summary lookup
- `quiz_flow.py` still performs concept lookup, quiz creation, item inserts, attempt replay queries, attempt insert, and quiz status updates directly

That leaves the shared quiz core cleaner than before, but still heavier than intended.

### 2. Upload deprecation metadata is not fully synced

The docs now describe `/documents/upload` as deprecated and compatibility-only, but the route itself is still missing explicit FastAPI deprecation metadata.

That means:

- generated OpenAPI does not communicate deprecation cleanly
- test coverage does not assert the deprecation contract
- code comments and API docs are not fully aligned

### 3. Replacement path strings are inconsistent

The legacy documents route still tells users to use `/api/workspaces/{ws_id}/kb/documents/upload`, but the canonical route is `/workspaces/{ws_id}/knowledge-base/documents/upload`.

That mismatch is small, but it is exactly the kind of drift that causes confusion in later maintenance and support work.

### 4. The active plan must stop contradicting itself

The previous active version mixed:

- completed-slice status updates
- stale prose from before those slices were done

This final pass should leave the plan internally consistent so it can serve as a real closeout/source-of-truth document.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### R6B. Slice 1: Quiz Persistence Finalization

Purpose:

- finish the shared quiz seam so orchestration and persistence are more clearly separated

Root problem:

- `quiz_flow.py` still owns most shared quiz SQL directly
- `quiz_persistence.py` does not yet justify its intended role as the shared DB layer

Files involved:

- extend `domain/learning/quiz_persistence.py`
- slim `domain/learning/quiz_flow.py`
- update affected imports/tests if helper signatures change

Implementation steps:

1. Move shared DB reads/writes from `quiz_flow.py` into `quiz_persistence.py`, including as appropriate:
   - concept lookup for quiz creation
   - quiz row insert
   - quiz item insert
   - persisted item reload
   - existing graded-attempt lookup
   - mastery lookup used on replay
   - attempt insert
   - quiz status updates
2. Keep `quiz_flow.py` responsible for:
   - orchestration
   - validation ordering
   - grading pipeline sequencing
   - observability
   - policy decisions such as `update_mastery`
3. Keep public wrappers stable:
   - `domain/learning/level_up.py`
   - `domain/learning/practice.py`
4. Do not redesign quiz payloads or grading behavior.

What stays the same:

- route contracts
- quiz payloads
- grading semantics
- mastery update behavior
- practice remains non-leveling

Verification:

- `pytest -q`
- `tests/db/test_level_up_quiz_flow_integration.py`
- `tests/db/test_practice_flow_integration.py`
- `tests/domain/test_level_up_feedback_contract.py`

Exit criteria:

- `quiz_persistence.py` owns the shared DB helpers that `quiz_flow.py` currently inlines
- `quiz_flow.py` reads primarily as orchestration rather than mixed SQL + orchestration

### R11B. Slice 2: Contract Metadata and Docs Sync

Purpose:

- make the legacy upload deprecation contract consistent across route metadata, docs, and tests

Root problem:

- docs say deprecated, but FastAPI route metadata does not
- route docstrings still point at the wrong replacement path

Files involved:

- `apps/api/routes/documents.py`
- `docs/API.md`
- `tests/api/test_response_contracts.py`
- this file if assumptions change during the slice

Implementation steps:

1. Mark the legacy upload route deprecated in FastAPI route metadata if not already.
2. Fix stale route replacement strings:
   - replace `/kb/documents/upload`
   - with `/knowledge-base/documents/upload`
3. Make sure `docs/API.md` and route docstrings say the same thing about:
   - deprecation status
   - compatibility-only status
   - canonical replacement path
4. Add or update API contract tests to assert the final intended contract if practical.

What stays the same:

- route path
- response shape
- compatibility behavior

Verification:

- `pytest -q`
- `tests/api/test_response_contracts.py`
- manual inspection of generated OpenAPI route metadata if needed

Exit criteria:

- no stale `/kb/...` replacement strings remain
- the legacy route is explicitly deprecated in code and docs

### R11C. Slice 3: Final Plan Closeout

Purpose:

- leave `docs/REFACTOR_PLAN.md` as a truthful closeout document instead of a half-finished execution note

Root problem:

- the current plan has stale sections that describe completed work as unfinished

Files involved:

- `docs/REFACTOR_PLAN.md`
- optionally archive one more snapshot if the final closeout materially changes structure

Implementation steps:

1. Remove stale "remaining work" prose that no longer matches the codebase.
2. Update current verification status and remaining work to the actual post-`R6B` and post-`R11B` state.
3. If all slices are complete:
   - mark them complete explicitly
   - keep a short residual-risk section if anything intentionally remains
4. If the final document becomes more of a closeout than an execution plan:
   - archive the pre-closeout version first
   - keep the active file concise and accurate

What stays the same:

- the document remains the source of truth

Verification:

- manual review of the document for internal consistency
- `pytest -q` if any linked tests/docs changed in the same slice

Exit criteria:

- no active section in this file materially contradicts another section
- the plan accurately reflects what is done versus what remains

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `R6B` Quiz Persistence Finalization
2. `R11B` Contract Metadata and Docs Sync
3. `R11C` Final Plan Closeout

Re-read this file after every 2 completed slices and restate which slices remain.

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

## What Not To Do

Do not do the following during the remaining refactor:

- do not redesign the frontend again
- do not reopen CSS decomposition
- do not remove `core/schemas/__init__.py`
- do not remove `adapters/db/graph_repository.py`
- do not delete `/documents/upload` in this plan
- do not change public response payloads as a side effect of cleanup

## Removal Ledger

Historical removal entries are preserved in:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-template-rewrite.md`

Append any new removal entries for `R6B`, `R11B`, or `R11C` below.

## Unified Refactor Prompt

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
