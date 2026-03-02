# Practice Memory + Quiz Robustness Refactor Plan

Last updated: 2026-03-01

Archive snapshots:
- `docs/archive/2026-03-01-practice-memory-robustness-snapshot.md`

## Plan Completeness Checklist

1. archive snapshot path(s) ✅
2. current verification status ✅
3. ordered slice list with stable IDs ✅
4. verification block template ✅
5. removal entry template ✅
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✅

## Non-Negotiable Run Rules

1. Re-open and re-read this file:
   - at the start of the run
   - after every 2 completed slices
   - after any context compaction/summarization moment
   - before claiming any slice complete
2. A slice is complete only if:
   - code/docs are changed
   - behavior is verified
   - verification gates below are met
3. Execute in small PR-sized chunks (one slice/sub-slice at a time).
4. Every completed slice must include a Verification Block.
5. Do not reopen completed slices unless blocked by current slice assumptions.
6. If behavior-change risk widens scope, stop and update this plan first.
7. Keep routes thin; business logic stays in domain/core layers.

## Purpose

This is a task-specific refactor plan to fix practice/quiz memory continuity and generation robustness, without resetting the repo-wide canonical `docs/REFACTOR_PLAN.md`.

## Inputs Used

This plan is based on:

- `docs/prompt_templates/refactor_plan.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- runtime error trace provided in user report
- current practice/quiz code in `apps/api/routes/practice.py`, `domain/learning/practice.py`, `domain/learning/quiz_flow.py`, `domain/learning/quiz_persistence.py`

## Executive Summary

Already in good shape:

- Core practice and level-up quiz generation/submission flows exist.
- Practice flashcards already have stateful persistence + ratings path.
- Novelty fingerprint history exists for flashcard/quiz generation.

Materially missing:

1. Retrieval/reuse API contracts for prior flashcards and prior quizzes.
2. Explicit level-up → practice reuse path while preserving tutor context continuity.
3. Robustness guardrails around bounded quiz item counts in retries/fallback path.

This plan stays narrow to persistence retrieval, reuse semantics, and generation robustness only.

## Non-Negotiable Constraints

1. No business logic in FastAPI routes.
2. Preserve existing response contracts unless adding new endpoints/schemas.
3. Keep quiz/practice generation bounded by configured min/max item budgets.
4. Keep mastery mutation unchanged for practice flows (`update_mastery=False`).
5. Add tests for all new behavior changes.

## Completed Work (Do Not Reopen Unless Blocked)

- `S0` Shared quiz generation/grading split into `quiz_generation.py`, `quiz_grading.py`, `quiz_flow.py`.
- `S10` Stateful flashcard persistence + rating endpoints and novelty storage landed.
- `S11` Practice novelty fingerprinting and dedup scaffolding landed.

## Remaining Slice IDs

- none

## Decision Log For Remaining Work

1. Retrieval should be additive (new read endpoints) rather than changing existing create/submit contracts.
2. Level-up quizzes stay typed as `level_up`; reuse into practice occurs via explicit copy/promotion operation.
3. Practice generation failures should degrade predictably (validated fallback) instead of 500.
4. Novelty behavior should prioritize avoiding repeats, then gracefully permit bounded reuse when exhausted.

## Removal Safety Rules

1. Do not remove routes/schemas/helpers without a removal entry and rollback path.
2. Prefer staged deprecations over hard deletions.
3. For public API changes, include compatibility notes and migration guidance.
4. Maintain a Removal Ledger section in this file during execution.

## Removal Entry Template

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

- `pytest -q`: passed (`607 passed`)
- `npm --prefix apps/web test`: passed (`13 files, 87 tests`)
- `npm --prefix apps/web run typecheck`: passed

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `domain/learning/practice.py` | ~140-340 | retry/fallback count bounds can exceed allowed range and fail with 500 |
| `apps/api/routes/practice.py` | full route | no retrieval endpoints for prior quizzes/flashcard runs |
| `domain/learning/quiz_persistence.py` | add query helpers | no list/get read models for reusable quiz history |
| `core/schemas/practice.py` + `core/schemas/quizzes.py` | add read contracts | retrieval/reuse payloads missing |
| `domain/chat/session_memory.py` | flashcard-only snapshot | level-up/practice quiz continuity can be expanded |

## Remaining Work Overview

### 1. Retrieval + Reuse Gaps

Practice flashcards and quizzes are persisted but not surfaced as retrievable reusable user-facing history. This prevents continuity across turns and sessions.

### 2. Level-up Lifecycle Gap

Level-up quizzes are persisted but not explicitly retrievable/reusable as practice artifacts after pass/fail outcomes.

### 3. Robustness Gap in Practice Quiz Generation

Overfetch for novelty can exceed max item bounds, causing validation failure and 500 in fallback path.

## Implementation Sequencing

### PMR-01. Slice 1: Practice quiz robustness bounds + retry hardening

Purpose:

- Eliminate 500 failures from out-of-bounds `question_count` in generation retries/fallback.

Root problem:

- `overfetch` can exceed max items (3..6), and fallback path calls `auto_items` with invalid count.

Files involved:

- `domain/learning/practice.py`
- `tests/db/test_practice_flow_integration.py`

Implementation steps:

1. Clamp requested generation count to `[MIN_ITEMS, MAX_ITEMS]` before prompt/retry/fallback usage.
2. Ensure fallback generation always uses bounded count.
3. Add regression test reproducing the overfetch/fallback failure and verifying 201 response.

What stays the same:

- Existing `/practice/quizzes` create/submit route contracts.
- Practice scoring and mastery non-mutation behavior.

Verification:

- `pytest -q tests/db/test_practice_flow_integration.py -k "practice_quiz"`

Exit criteria:

- No 500 when novelty history is large.
- Practice quiz creation returns bounded item list and valid mixed types.

### PMR-02. Slice 2: Practice quiz retrieval/reuse read APIs

Purpose:

- Expose prior practice quizzes so user can retrieve/reuse instead of losing context after next actions.

Root problem:

- No API to list/get prior practice quizzes and attempts by user/concept.

Files involved:

- `domain/learning/quiz_persistence.py`
- `domain/learning/practice.py`
- `apps/api/routes/practice.py`
- `core/schemas/quizzes.py`
- tests under `tests/db/` and/or `tests/api/`

Implementation steps:

1. Add persistence query helpers for listing recent practice quizzes and loading quiz detail.
2. Add domain read functions in `practice.py` to enforce workspace/user/concept scope.
3. Add routes:
   - `GET /workspaces/{ws_id}/practice/quizzes`
   - `GET /workspaces/{ws_id}/practice/quizzes/{quiz_id}`
4. Include latest attempt summary in retrieval response.

What stays the same:

- Existing create/submit route behavior.
- Existing quiz table ownership/scoping.

Verification:

- targeted pytest for new routes and scoping

Exit criteria:

- User can retrieve previous practice quizzes with attempts.

### PMR-03. Slice 3: Stateful flashcard retrieval/reuse read APIs

Purpose:

- Make previously generated flashcards retrievable and reusable, including rating state.

Root problem:

- Stateful cards are stored but there is no route to list previous runs/cards by concept/user.

Files involved:

- `domain/learning/practice.py`
- `apps/api/routes/practice.py`
- `core/schemas/practice.py`
- tests under `tests/db/` and/or `tests/api/`

Implementation steps:

1. Add read helpers for flashcard runs + cards joined with user progress/ratings.
2. Add routes:
   - `GET /workspaces/{ws_id}/practice/flashcards/runs`
   - `GET /workspaces/{ws_id}/practice/flashcards/runs/{run_id}`
3. Ensure responses include `self_rating`, `passed`, and due metadata when available.

What stays the same:

- Existing generation/rating endpoints.

Verification:

- targeted pytest for retrieval/scoping

Exit criteria:

- User can return to previous flashcard sets with progress state.

### PMR-04. Slice 4: Level-up retrieval + promote-to-practice flow

Purpose:

- Make level-up quizzes retrievable and reusable as practice after pass/fail.

Root problem:

- Level-up rows exist but no explicit promote/reuse operation.

Files involved:

- `domain/learning/quiz_flow.py`
- `domain/learning/quiz_persistence.py`
- `domain/learning/level_up.py`
- `domain/learning/practice.py`
- `apps/api/routes/quizzes.py` and/or `apps/api/routes/practice.py`
- schemas/tests

Implementation steps:

1. Add read endpoint(s) for level-up history by concept/user.
2. Add promotion operation that copies existing level-up quiz items into a new `practice` quiz row.
3. Enforce ownership + workspace scope.

What stays the same:

- Original level-up records remain immutable.
- Mastery updates happen only through level-up submission, not promotion.

Verification:

- targeted pytest for promotion and retrieval semantics

Exit criteria:

- User can reuse past level-up content in practice mode without losing original attempt history.

### PMR-05. Slice 5: Tutor continuity context for practice + level-up

Purpose:

- Keep prior quiz and flashcard outcomes available to tutor context for the same topic.

Root problem:

- Existing tutor context includes flashcard snapshot; quiz continuity is limited and can be improved.

Files involved:

- `domain/chat/session_memory.py`
- `domain/chat/stream.py`
- prompt/context tests

Implementation steps:

1. Add concise per-concept practice + level-up snapshot loader.
2. Thread snapshot into tutor prompt assembly where topic/concept is known.
3. Keep token budget bounded with strict limits.

What stays the same:

- Existing tutor style and mastery gating policy.

Verification:

- targeted tests for prompt context inclusion and limits

Exit criteria:

- Tutor receives stable recent assessment context for topic continuity.

## Execution Order (Update After Each Run)

1. `PMR-01` Practice quiz robustness bounds + retry hardening ✅ completed 2026-03-01
2. `PMR-02` Practice quiz retrieval/reuse read APIs ✅ completed 2026-03-01
3. `PMR-03` Stateful flashcard retrieval/reuse read APIs ✅ completed 2026-03-01
4. `PMR-04` Level-up retrieval + promote-to-practice flow ✅ completed 2026-03-01
5. `PMR-05` Tutor continuity context for practice + level-up ✅ completed 2026-03-01

Re-read this file after every 2 completed slices and restate remaining slices.

## Verification Block Template

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

Run at the end of each non-doc slice:

```bash
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
```

Run additionally when relevant:

```bash
ruff check .
```

Slice-specific emphasis:

- `PMR-01`
  - `pytest -q tests/db/test_practice_flow_integration.py -k "practice_quiz"`
- `PMR-02`
  - practice quiz retrieval route tests + workspace scoping checks
- `PMR-03`
  - flashcard run retrieval route tests + progress field assertions
- `PMR-04`
  - level-up promotion semantic tests + no mastery mutation checks
- `PMR-05`
  - tutor context snapshot tests with bounded output size

Manual smoke checklist:

1. Create practice quiz, navigate away, then retrieve it by list/detail endpoint.
2. Generate stateful flashcards, rate some cards, then reload run and verify ratings persist.
3. Promote a completed level-up quiz into practice and submit it without changing mastery.

## What Not To Do

- do not rewrite the full tutor orchestration runtime in this refactor
- do not introduce unbounded generation loops or unbounded retrieval payloads
- do not change mastery pass criteria or policy thresholds in this refactor

## Removal Ledger

No removals logged yet.

## Slice Verification Log

```text
Verification Block - PMR-01

Root cause
- Practice quiz novelty overfetch used unbounded question_count for prompt/retry/fallback paths.
- Fallback called auto_items with out-of-range count (>6), triggering QuizValidationError and 500.

Files changed
- domain/learning/practice.py
- tests/db/test_practice_flow_integration.py

What changed
- Added hard clamp for generation_count to [MIN_ITEMS, MAX_ITEMS] before generation paths.
- Updated fallback helper to enforce safe_count bounds defensively.
- Added regression test covering seen-history overfetch + LLM failure fallback path.

Commands run
- PYTHONPATH=. pytest -q tests/db/test_practice_flow_integration.py -k "practice_quiz"

Manual verification steps
- Triggered practice quiz create path under fallback conditions with novelty history present via integration test.

Observed outcome
- Targeted practice quiz suite passed (5 passed, 1 deselected).
- No 500; quiz creation returns 201 with bounded mixed-item payload.

Verification Block - PMR-02

Root cause
- Practice quizzes were persisted but had no list/detail retrieval API for user-scoped reuse.
- No typed response contract exposed latest attempt summary for continuity.

Files changed
- core/schemas/quizzes.py
- core/schemas/__init__.py
- domain/learning/quiz_persistence.py
- domain/learning/practice.py
- apps/api/routes/practice.py
- tests/api/test_response_contracts.py
- tests/db/test_practice_flow_integration.py

What changed
- Added typed schemas for practice quiz history list/detail + latest attempt summary.
- Added persistence read helpers for listing quizzes and loading quiz detail with latest graded attempt.
- Added domain read functions (`list_practice_quizzes`, `get_practice_quiz`) with scope validation.
- Added API endpoints:
  - `GET /workspaces/{ws_id}/practice/quizzes`
  - `GET /workspaces/{ws_id}/practice/quizzes/{quiz_id}`
- Added/updated tests for OpenAPI contracts and integration behavior (latest attempt + workspace scoping).

Commands run
- PYTHONPATH=. pytest -q tests/api/test_response_contracts.py tests/db/test_practice_flow_integration.py -k "practice or response_contracts"

Manual verification steps
- Created practice quiz via API.
- Retrieved quiz list (with concept filter) before and after submission.
- Retrieved quiz detail and verified items + latest attempt summary.
- Verified wrong-workspace detail request returns 403.

Observed outcome
- Targeted suite passed (53 passed).
- New retrieval endpoints return typed payloads with latest attempt summary and preserve workspace/user scoping.

Verification Block - PMR-03

Root cause
- Stateful flashcards were persisted but had no run-level retrieval API for user-scoped reuse.
- Existing response contracts did not expose run metadata with per-card progress fields for continuity.

Files changed
- core/schemas/practice.py
- core/schemas/__init__.py
- domain/learning/practice.py
- apps/api/routes/practice.py
- tests/api/test_response_contracts.py
- tests/db/test_practice_flow_integration.py

What changed
- Added typed schemas for flashcard run list/detail payloads and due metadata on stateful cards.
- Added domain retrieval functions (`list_flashcard_runs`, `get_flashcard_run`) with workspace/user scoping and UUID validation.
- Added API endpoints:
  - `GET /workspaces/{ws_id}/practice/flashcards/runs`
  - `GET /workspaces/{ws_id}/practice/flashcards/runs/{run_id}`
- Added/updated tests for OpenAPI contracts and integration behavior (run retrieval + progress state + scoping).

Commands run
- PYTHONPATH=. pytest -q tests/api/test_response_contracts.py tests/db/test_practice_flow_integration.py -k "practice or flashcard or response_contracts"

Manual verification steps
- Generated stateful flashcards.
- Listed flashcard runs (with concept filter) and verified run metadata.
- Rated a flashcard and retrieved run detail to verify persisted self-rating/passed/due metadata fields.
- Verified wrong-workspace detail request returns 403.

Observed outcome
- Targeted suite passed (58 passed).
- New flashcard run retrieval endpoints return scoped run and card-progress state for reuse.

Verification Block - PMR-04

Root cause
- Level-up quizzes were persisted but had no retrieval API for user-scoped history/detail access.
- There was no explicit operation to reuse a level-up quiz as a practice quiz while preserving mastery mutation policy.

Files changed
- core/schemas/quizzes.py
- core/schemas/__init__.py
- domain/learning/level_up.py
- apps/api/routes/quizzes.py
- tests/api/test_response_contracts.py
- tests/db/test_level_up_quiz_flow_integration.py

What changed
- Added typed level-up history/detail schemas and promote-to-practice response schema.
- Added domain retrieval helpers for level-up list/detail and a promotion operation that clones level-up items into a new `practice` quiz.
- Added API endpoints:
  - `GET /workspaces/{ws_id}/quizzes/level-up`
  - `GET /workspaces/{ws_id}/quizzes/level-up/{quiz_id}`
  - `POST /workspaces/{ws_id}/quizzes/level-up/{quiz_id}/promote`
- Added/updated contract + integration tests verifying retrieval, promotion semantics, and no mastery mutation on promoted practice submission.

Commands run
- PYTHONPATH=. pytest -q tests/db/test_level_up_quiz_flow_integration.py -k "history_and_promote"
- PYTHONPATH=. pytest -q tests/api/test_response_contracts.py tests/db/test_level_up_quiz_flow_integration.py tests/db/test_practice_flow_integration.py -k "level_up or promote or response_contracts or practice"

Manual verification steps
- Created and submitted level-up quiz.
- Retrieved level-up list/detail and confirmed latest attempt summary.
- Promoted level-up quiz to practice and submitted promoted practice quiz.
- Verified promoted practice submission response omits mastery fields and mastery row remains unchanged.

Observed outcome
- Promotion-specific integration test passed.
- Targeted cross-suite passed (70 passed).
- Level-up retrieval and promote-to-practice flows are now available with scoped API contracts.

Verification Block - PMR-05

Root cause
- Tutor context had flashcard progress snapshot support but lacked a bounded, explicit snapshot of recent level-up/practice quiz outcomes per concept.
- Without a dedicated snapshot loader wired into both blocking and streaming flows, continuity for topic-specific follow-up tutoring was incomplete.

Files changed
- domain/chat/session_memory.py
- domain/chat/respond.py
- domain/chat/stream.py
- tests/domain/test_quiz_progress_snapshot.py

What changed
- Added `load_quiz_progress_snapshot()` in session memory with bounded retrieval (`QUIZ_PROGRESS_LIMIT`) and optional concept scoping.
- Included both `practice` and `level_up` quiz outcomes (score/passed or status fallback) in a concise `QUIZ PROGRESS SNAPSHOT` section.
- Wired quiz snapshot into both blocking (`respond.py`) and streaming (`stream.py`) tutor prompt assembly paths.
- Added span attribute in blocking path for snapshot length observability.
- Added dedicated unit tests for snapshot formatting and error/rollback behavior.

Commands run
- PYTHONPATH=. pytest -q tests/domain/test_quiz_progress_snapshot.py tests/domain/test_g1_progress.py tests/domain/test_g5_trace.py tests/domain/test_s1_phase_semantics.py tests/domain/test_u5_reasoning_summary.py tests/domain/test_u6_answer_parts.py
- PYTHONPATH=. pytest -q tests/api/test_chat_respond.py

Manual verification steps
- Verified snapshot loader behavior for scored and unattempted quiz rows via unit tests.
- Verified blocking and streaming chat test suites remain green after wiring.

Observed outcome
- PMR-05 targeted suites passed (46 + 13 tests).
- Tutor prompt assembly now has bounded level-up/practice continuity context in both blocking and streaming paths.
```

Removal entries in this slice: none.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/PRACTICE_MEMORY_ROBUSTNESS_REFACTOR_PLAN.md now. This file is the source of truth.
You MUST implement refactor slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/PRACTICE_MEMORY_ROBUSTNESS_REFACTOR_PLAN.md using the Removal Entry Template.
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

After every 2 slices OR if your context is compacted/summarized, re-open docs/PRACTICE_MEMORY_ROBUSTNESS_REFACTOR_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/PRACTICE_MEMORY_ROBUSTNESS_REFACTOR_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/PRACTICE_MEMORY_ROBUSTNESS_REFACTOR_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/PRACTICE_MEMORY_ROBUSTNESS_REFACTOR_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```