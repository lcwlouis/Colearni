# CoLearni Refactor Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Archive snapshot of the previous full-plan version:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-remaining-rewrite.md`

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

This document replaces the earlier broad refactor plan now that the first wave of refactor work has already landed.

The old version has been archived intact. This active file now covers only the remaining refactor work so the next implementation run is not forced to rediscover what is already done.

Use this document as the source of truth for the remaining cleanup. If implementation discovers a new constraint, update this file before widening scope.

## Inputs Used

This plan is based on:

- `docs/archive/RUN_VERIFY_FIXES.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-remaining-rewrite.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- current repository layout and verification status as of 2026-02-28

## Executive Summary

The first refactor wave was successful.

The codebase is in materially better shape than before:

- schema definitions are split into `core/schemas/`
- workspaces and research routes are thin
- chat orchestration has been split into smaller domain modules
- graph repository code is split behind a small facade
- tutor, graph, KB, and sidebar UI have feature-level structure
- global CSS is now a thin aggregator over feature-scoped files
- `pytest`, web tests, and web typecheck are green

The remaining work is narrower and should stay narrow.

The main unfinished areas are:

1. ~~The legacy `/documents/upload` route is still a real implementation path, not just a compatibility wrapper.~~ → Done (R3A).
2. ~~`apps/api/routes/knowledge_base.py` still owns provider construction and background-task orchestration.~~ → Done (R3B).
3. ~~`domain/learning/practice.py` still depends directly on `domain.learning.level_up`.~~ → Done (R6A).
4. ~~`domain/learning/level_up.py` is smaller than before, but still holds too much persistence and orchestration.~~ → Done (R6A).
5. The active plan and API docs still describe some pre-refactor conditions that are no longer true. → In progress (R11B).

The right move now is a short second pass focused on unifying the upload path, finishing the shared quiz boundary, and cleaning up facades and stale docs.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. No intentional behavior change unless the slice is explicitly marked as a compatibility decision.
2. Keep PRs small. Target `<= 400 LOC net` per PR wherever possible.
3. Preserve public API contracts unless the slice explicitly updates docs, tests, and rollback notes together.
4. Keep FastAPI routes thin: request validation, service call, error translation, response.
5. Keep tutor evidence/citation behavior unchanged.
6. Do not reopen finished frontend/CSS decomposition work unless it directly blocks a remaining slice.
7. Prefer staged wrappers and facades over hard deletion when public surfaces are involved.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered landed enough for this phase:

- `R1` Schema decomposition:
  - `core/schemas/` exists and `core/schemas/__init__.py` is the compatibility facade
- `R2` Thin routes pass I:
  - `apps/api/routes/workspaces.py` delegates to `domain.workspaces.service`
  - `apps/api/routes/research.py` delegates to `domain.research.service`
- `R5` Chat orchestration split:
  - `domain/chat/respond.py` is now coordinator-sized
  - retrieval, evidence, social flow, and tutor generation helpers live in dedicated modules
- `R7` Graph repository split:
  - `adapters/db/graph/` exists
  - `adapters/db/graph_repository.py` is now a facade
- `R8` Tutor page split:
  - `apps/web/app/tutor/page.tsx` is now a container page
- `R9` Graph, KB, and sidebar split:
  - feature folders exist under `apps/web/features/`
  - stale `/practice` sidebar nav is no longer present
- `R10` CSS decomposition:
  - `apps/web/app/globals.css` is now an aggregator over `apps/web/styles/*.css`

These slices are not "perfect forever", but they are not the current execution target.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `R3A` Upload Surface Consolidation
- `R3B` Knowledge Base Route Final Thin Pass
- `R6A` Shared Quiz Core Completion
- `R11A` Cleanup and Artifact Removal
- `R11B` Docs and Contract Sync

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. Canonical upload surface:
   - `POST /workspaces/{ws_id}/knowledge-base/documents/upload`
2. Legacy upload route policy:
   - `POST /documents/upload` remains temporary compatibility surface until removal is explicitly approved
   - during this plan it should be reduced to a thin wrapper, not kept as a second implementation
3. `core/schemas/__init__.py` policy:
   - keep it for now
   - do not remove it in this phase because many imports still rely on it
4. `adapters/db/graph_repository.py` policy:
   - removable only if there is no remaining in-repo use and no compatibility requirement
5. Frontend/CSS policy:
   - do not create new decomposition work here unless a remaining backend slice forces it

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
| `domain/learning/practice.py` | 718 | Practice quiz flow — now imports shared `quiz_flow` directly (no longer depends on `level_up`). Stable. |
| `domain/learning/quiz_flow.py` | 840 | Shared quiz create/submit orchestration. Core shared module. |
| `domain/learning/level_up.py` | 45 | Thin backward-compat wrapper over `quiz_flow` and `quiz_persistence`. |
| `apps/api/routes/knowledge_base.py` | 146 | Fully thinned — HTTP concerns only. |
| `apps/api/routes/documents.py` | 169 | Compatibility wrapper over `upload_flow`. |
| `adapters/db/graph_repository.py` | 32 | Facade — still used by `domain/graph/` and tests. Kept. |

Known cleanup candidates:

- `apps/web/tsconfig.tsbuildinfo`
- `colearni_backend.egg-info/PKG-INFO`
- `colearni_backend.egg-info/SOURCES.txt`
- repo-root `.DS_Store`

Known docs drift:

- this file previously described pre-refactor file sizes and stale sidebar issues
- `docs/API.md` still documents the legacy upload route as a first-class endpoint

## Remaining Work Overview

### 1. Upload unification is not complete

The web app already uses the workspace-scoped KB upload route, but the legacy route still contains its own implementation.

That means:

- two real upload code paths still exist
- background task orchestration is duplicated
- API docs and tests still treat the legacy route as fully primary

The remaining plan should unify implementation first, then make a separate explicit decision about final public contract removal.

### 2. KB routes are thinner, but not fully thin

`apps/api/routes/knowledge_base.py` has already moved list/delete/reset behavior into the domain layer, but upload and reprocess still:

- inspect app state
- build providers
- enqueue background tasks directly

That logic should move behind a domain seam so the route returns to pure HTTP handling.

### 3. Shared quiz extraction is incomplete

The existing refactor already extracted:

- `domain/learning/quiz_generation.py`
- `domain/learning/quiz_grading.py`
- `domain/learning/practice_novelty.py`

But the most important boundary is still not finished:

- `practice.py` imports `level_up.py`
- `level_up.py` still owns shared persistence and orchestration logic
- chat quiz summary lookup still comes from `level_up.py`

The remaining slice should finish the shared quiz core so level-up and practice are sibling flows, not parent/child modules.

### 4. Cleanup is now mostly about deleting the right things, not moving more code

The second pass should remove or classify:

- generated artifacts
- dead facades
- stale docs
- stale tests or API references for deprecated paths

It should not invent new architecture work.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### R3A. Slice 1: Upload Surface Consolidation

Purpose:

- reduce the repository to one real upload implementation while preserving current public contracts

Root problem:

- `apps/api/routes/documents.py` and `apps/api/routes/knowledge_base.py` both perform ingestion orchestration
- the web app only uses the workspace-scoped route
- docs/tests still keep the legacy route alive

Files involved:

- create `domain/knowledge_base/upload_flow.py`
- slim:
  - `apps/api/routes/documents.py`
  - `apps/api/routes/knowledge_base.py`

Implementation steps:

1. Create a shared service-level upload flow that owns:
   - `IngestionRequest` assembly inputs
   - fast-ingest invocation
   - app-state runtime resolution for graph/chunk providers
   - background-task scheduling helper inputs
2. Keep transport parsing in routes only:
   - multipart/raw-body parsing in `documents.py`
   - `UploadFile` handling in `knowledge_base.py`
3. Keep public response contracts stable:
   - workspace KB route keeps its current `202 Accepted` response shape
   - legacy `/documents/upload` route keeps current status/response behavior while deprecated
4. Refactor `documents.py` into a compatibility wrapper over the shared upload flow.
5. Refactor KB upload endpoint to use the same shared upload flow.

What stays the same:

- both route paths
- current response payload shapes
- current status code behavior
- frontend upload behavior

Verification:

- `pytest -q`
- `tests/api/test_documents_upload.py`
- `tests/api/test_response_contracts.py`
- `tests/db/test_document_ingestion_integration.py`

Exit criteria:

- only one real upload implementation exists
- the legacy route is clearly marked as compatibility-only

### R3B. Slice 2: Knowledge Base Route Final Thin Pass

Purpose:

- finish route thinning for KB upload and reprocess flows

Root problem:

- `apps/api/routes/knowledge_base.py` still owns provider construction and background task wiring inline

Files involved:

- extend `domain/knowledge_base/service.py`
- extend or reuse `domain/knowledge_base/upload_flow.py`
- slim `apps/api/routes/knowledge_base.py`

Implementation steps:

1. Move provider/runtime resolution behind a domain helper.
2. Move reprocess scheduling behind a domain helper that:
   - resets document state
   - resolves runtime dependencies
   - enqueues post-ingest work
3. Keep route responsibilities limited to:
   - HTTP validation
   - file-size guardrails
   - dependency injection
   - error translation
   - response model shaping
4. Do not move raw file/body transport parsing out of the route unless it directly reduces duplication.

What stays the same:

- route paths
- response shapes
- background processing semantics
- document status behavior

Verification:

- `pytest -q`
- `tests/api/test_response_contracts.py`
- `tests/db/test_document_ingestion_integration.py`
- manual smoke:
  - upload document
  - refresh list
  - reprocess document

Exit criteria:

- `apps/api/routes/knowledge_base.py` no longer builds providers or schedules post-ingest work inline

### R6A. Slice 3: Shared Quiz Core Completion

Purpose:

- finish the split between level-up and practice so they share infrastructure without one flow depending on the other

Root problem:

- `practice.py` still imports `level_up.py`
- `level_up.py` still owns persistence and orchestration that should be shared

Files involved:

- create `domain/learning/quiz_persistence.py`
- create `domain/learning/quiz_flow.py`
- optionally create `domain/learning/quiz_errors.py` if exception sharing becomes noisy
- slim:
  - `domain/learning/level_up.py`
  - `domain/learning/practice.py`
- update imports in:
  - `domain/chat/response_service.py`
  - `apps/api/routes/quizzes.py`
  - `apps/jobs/quiz_gardener.py`
  - `domain/learning/__init__.py`
  - affected tests

Implementation steps:

1. Move shared quiz DB reads/writes into `quiz_persistence.py`:
   - quiz creation writes
   - quiz item persistence
   - attempt lookup / idempotent replay helpers
   - latest quiz summary lookup
2. Move generic create/submit orchestration into `quiz_flow.py`:
   - create quiz from normalized items
   - submit quiz with shared grading pipeline
   - keep hooks/flags for:
     - quiz type
     - mastery update on/off
     - retry hint
3. Keep level-up specific behavior in `level_up.py` only:
   - mastery transitions
   - public level-up errors or adapters over shared errors
   - level-up specific defaults
4. Keep practice specific behavior in `practice.py` only:
   - novelty filtering
   - flashcard generation
   - practice-specific validation and error mapping
5. Update chat quiz summary access so it imports from the shared quiz module, not `level_up.py`.
6. End state:
   - `practice.py` does not import `level_up.py`
   - `level_up.py` and `practice.py` are sibling wrappers over shared quiz core modules

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
- `tests/domain/test_spaced_repetition.py`

Exit criteria:

- `domain/learning/practice.py` no longer imports `domain.learning.level_up`
- quiz summary lookup no longer lives behind `level_up.py`

### R11A. Slice 4: Cleanup and Artifact Removal

Purpose:

- remove low-signal repo noise and delete only the compatibility layers that are actually ready to go

Files involved:

- `.gitignore`
- generated artifacts and repo noise
- potential facade removals:
  - `adapters/db/graph_repository.py`
  - other dead helpers discovered during earlier slices

Implementation steps:

1. Stop tracking generated artifacts if they are still tracked.
2. Remove repo-root `.DS_Store`.
3. Remove dead imports and stale helper references introduced by the remaining slices.
4. Evaluate `adapters/db/graph_repository.py`:
   - remove it only if no internal imports remain and no compatibility need is documented
   - otherwise keep it and document why it stays
5. Do NOT remove `core/schemas/__init__.py` in this slice.
6. Do NOT remove `/documents/upload` in this slice unless `R11B` updates docs/tests/contracts in the same change and rollback is straightforward.

What stays the same:

- application behavior
- schema package import surface

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- `git status --short` shows no tracked generated-noise files remaining

Exit criteria:

- generated artifacts no longer pollute diffs
- only justified compatibility facades remain

### R11B. Slice 5: Docs and Contract Sync

Purpose:

- make docs and contract tests match the actual post-refactor state

Root problem:

- the old plan and API docs still describe pre-refactor conditions
- the legacy upload route is still documented as first-class instead of compatibility-only

Files involved:

- `docs/REFACTOR_PLAN.md`
- `docs/API.md`
- `tests/api/test_response_contracts.py`
- any docs/tests directly tied to removal or deprecation decisions

Implementation steps:

1. Update this file with actual completion state after the remaining slices land.
2. Update `docs/API.md` to reflect the upload decision:
   - if legacy route remains:
     - mark it deprecated and compatibility-only
     - clearly call the workspace-scoped KB route canonical
   - if legacy route is removed:
     - delete the old docs section
     - update tests and rollback notes in the same slice
3. Remove stale claims from docs:
   - pre-refactor file-size inventory that is no longer true
   - stale sidebar cleanup items already resolved
4. Align response contract tests with the final intended public API.

What stays the same:

- documented behavior should match real code, not vice versa

Verification:

- `pytest -q`
- `tests/api/test_response_contracts.py`
- manual review of docs against code paths touched in `R3A`, `R3B`, and `R6A`

Exit criteria:

- no active plan/doc says something materially false about the current codebase
- upload contract status is explicit and unambiguous

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `R3A` Upload Surface Consolidation
   - This removes the biggest remaining duplicate implementation path.

2. `R3B` Knowledge Base Route Final Thin Pass
   - Finish route thinning once upload implementation is shared.

3. `R6A` Shared Quiz Core Completion
   - Finish the major remaining backend boundary after upload/KB seams are stable.

4. `R11A` Cleanup and Artifact Removal
   - Only after the real implementation moves are complete.

5. `R11B` Docs and Contract Sync
   - Finish by making the docs and tests match the final state.

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

- `R3A` / `R3B`
  - `tests/api/test_documents_upload.py`
  - `tests/api/test_response_contracts.py`
  - `tests/db/test_document_ingestion_integration.py`
- `R6A`
  - `tests/db/test_level_up_quiz_flow_integration.py`
  - `tests/db/test_practice_flow_integration.py`
  - `tests/domain/test_level_up_feedback_contract.py`
- `R11A`
  - clean `git status --short`
- `R11B`
  - docs reviewed against active code paths

Manual smoke checklist:

1. Sources page uploads a document, shows it in the list, and reprocesses it.
2. Legacy upload route, if still present, returns the documented compatibility response.
3. Practice quiz generation and submission still work without updating mastery.
4. Level-up quiz generation and submission still update mastery correctly.

## What Not To Do

Do not do the following during the remaining refactor:

- do not redesign the frontend again
- do not reopen CSS decomposition for aesthetic changes
- do not remove `core/schemas/__init__.py` yet
- do not delete `/documents/upload` before docs/tests/rollback notes are updated together
- do not move unrelated graph or retrieval code while finishing the quiz split
- do not change public response payloads as a side effect of module cleanup

## Removal Ledger

Append removal entries here during implementation.

### Removal Entry - R3A

Removed artifact
- Inline upload orchestration in `apps/api/routes/documents.py` (~60 lines of ingestion/provider/scheduling logic)
- Inline upload orchestration in `apps/api/routes/knowledge_base.py` (~40 lines of provider/scheduling logic)

Reason for removal
- Duplicated upload implementation across two routes

Replacement
- `domain/knowledge_base/upload_flow.py` (shared `execute_upload`, `resolve_settings`, `resolve_post_ingest_context`, `schedule_post_ingest`)

Reverse path
- Revert commit `0752765`

Compatibility impact
- Internal only. Both route paths and response shapes preserved.

Verification
- 296 tests pass. `test_documents_upload.py`, `test_response_contracts.py`, `test_document_ingestion_integration.py` all green.

### Removal Entry - R3B

Removed artifact
- Inline reprocess orchestration in `apps/api/routes/knowledge_base.py` (~15 lines of reset/provider/scheduling logic)

Reason for removal
- Route still owned provider construction and background task wiring for reprocess

Replacement
- `domain/knowledge_base/service.reprocess_document()` in `domain/knowledge_base/service.py`

Reverse path
- Revert commit `760d430`

Compatibility impact
- Internal only. Route paths, response shapes, and background processing semantics preserved.

Verification
- 296 tests pass. `test_response_contracts.py`, `test_document_ingestion_integration.py` all green.

### Removal Entry - R6A

Removed artifact
- Quiz create/submit orchestration logic in `domain/learning/level_up.py` (~850 lines)
- `get_latest_quiz_summary_for_concept` in `domain/learning/level_up.py`

Reason for removal
- `level_up.py` mixed quiz orchestration, persistence, and level-up specific behavior. `practice.py` depended on `level_up` module.

Replacement
- `domain/learning/quiz_flow.py` (shared quiz create/submit orchestration, 840 lines)
- `domain/learning/quiz_persistence.py` (shared quiz DB reads, 69 lines)
- `domain/learning/level_up.py` retained as thin re-export wrapper with backward-compat aliases

Reverse path
- Revert commit `bd22808`

Compatibility impact
- Internal only. All public names re-exported via `level_up.py` aliases. Route contracts, quiz payloads, grading semantics unchanged.

Verification
- 296 tests pass. `test_level_up_quiz_flow_integration.py`, `test_practice_flow_integration.py`, `test_level_up_feedback_contract.py`, `test_spaced_repetition.py` all green.

### Removal Entry - R11A

Removed artifact
- `get_mastered_neighbor_context()` in `domain/learning/level_up.py` (dead function, ~50 lines)

Reason for removal
- Defined but never called anywhere in the codebase

Replacement
- None (true deletion of dead code)

Reverse path
- Revert commit `43584f7`

Compatibility impact
- None — function was internal and unused

Verification
- `grep -rn get_mastered_neighbor_context` returns 0 hits; 296 tests pass

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
Begin with the current slice in execution order. If starting fresh, begin with slice R3A (Upload Surface Consolidation) exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/REFACTOR_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
