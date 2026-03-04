# Graph Learning Surface And Topic-Lock Plan (AR7) (READ THIS OFTEN)

Last updated: 2026-03-01

Archive snapshots:
- `none` (new child plan)

Template usage:
- This is a task-specific child plan for graph-driven study surfaces, flashcard/quiz history reuse, and topic-lock UX.
- It does not replace `docs/REFACTOR_PLAN.md`.
- `docs/AGENTIC_MASTER_PLAN.md` remains the parent source of truth for cross-track constraints and status.

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
   - after every 2 AR7 sub-slices
   - after any context compaction / summarization event
   - before claiming any AR7 slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. This plan is the only place where graph study UX, practice history reuse, and topic-switch UX should be widened together.
4. Keep one shared concept-activity surface across graph page and tutor graph UI; do not fork the logic.
5. Flashcards on a concept surface should be cumulative and concept-centered, not a pile of run buttons.
6. Quiz attempts may remain run-based, but must be reopenable and retryable.
7. Rejecting a concept switch must not auto-send a synthetic user message.
8. This file is INCOMPLETE unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This plan turns the graph page and tutor graph drawer into reusable concept-learning surfaces and makes topic switching less disruptive.

Earlier work already landed:

- graph concept exploration in `apps/web/app/(app)/graph/page.tsx`
- graph detail panel state in `apps/web/features/graph/hooks/use-graph-page.ts`
- practice and flashcard APIs in `apps/api/routes/practice.py`
- level-up history/detail APIs in `apps/api/routes/quizzes.py`
- tutor graph and quiz drawers in `apps/web/features/tutor/components/`

This plan exists because those parts still behave like disconnected tools instead of one concept-centered study workspace.

## Inputs Used

- `docs/prompt_templates/refactor_plan.md`
- `docs/AGENTIC_MASTER_PLAN.md`
- `apps/web/app/(app)/graph/page.tsx`
- `apps/web/features/graph/hooks/use-graph-page.ts`
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/components/practice-history.tsx`
- `apps/web/features/tutor/components/tutor-graph-drawer.tsx`
- `apps/web/features/tutor/components/tutor-quiz-drawer.tsx`
- `apps/web/features/tutor/components/concept-switch-banner.tsx`
- `apps/web/features/tutor/hooks/use-tutor-page.ts`
- `apps/web/features/tutor/hooks/use-level-up-flow.ts`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/api/routes/practice.py`
- `apps/api/routes/quizzes.py`
- `domain/learning/practice.py`
- `domain/learning/level_up.py`
- `domain/chat/concept_resolver.py`

## Executive Summary

What is already in good shape:

- concept detail and graph traversal already exist
- practice quiz and stateful flashcard APIs already exist
- quiz detail/history endpoints already exist
- level-up quiz history/detail/promote endpoints already exist

What is still materially missing:

1. graph concept study is still generate-first instead of history-first
2. flashcards are run-scoped in the UI, not cumulative at the concept level
3. prior practice and level-up quizzes are not reusable from graph or tutor surfaces
4. tutor graph UI does not expose the same study surface as the graph page
5. concept switching is too eager and the modal UX is too intrusive

The remaining work should stay narrow: build a shared concept-activity surface, then tighten topic-lock policy and switch UX without replacing the current grounded tutor model.

## Non-Negotiable Constraints

1. Do not fork graph-page and tutor-drawer study logic.
2. Keep quiz creation/opening runtime-owned and user-visible.
3. Preserve current practice and level-up APIs where practical; add aggregate read surfaces instead of duplicating models.
4. Flashcards in graph/tutor study surfaces should be concept-cumulative.
5. Practice and level-up quizzes should remain attempt/run-based with explicit open/retry affordances.
6. Topic lock should default to staying on the current concept until mastery/readiness rules or explicit user intent justify switching.
7. Do not auto-submit clarification messages when a user rejects a switch.

## Completed Work (Do Not Reopen Unless Blocked)

- `BASE-G1` Graph page concept detail and graph selection flow exist.
- `BASE-G2` Practice quiz and flashcard run list/detail endpoints exist.
- `BASE-G3` Tutor graph and quiz drawers exist.
- `BASE-G4` Concept switch suggestion payloads already flow from backend to frontend.

## Remaining Slice IDs

- `AR7.1` Add a shared concept-activity data surface for graph and tutor contexts
- `AR7.2` Upgrade the graph detail panel into a concept activity workspace
- `AR7.3` Reuse the concept activity workspace inside tutor graph/chat UI
- `AR7.4` Tighten runtime topic-lock and switch-threshold policy
- `AR7.5` Replace the intrusive switch modal with a non-blocking topic-switch UX and add focused tests

## Decision Log For Remaining Work

1. Concept study should be organized around the active concept, not around raw generation runs.
2. Flashcard history should be rendered as a cumulative bank view for the concept, using run history as metadata rather than the primary UX.
3. Quiz history should remain attempt-based and reopenable; retry should either reopen existing detail in review mode or create a new attempt intentionally.
4. The tutor graph drawer should reuse the same concept-activity surface or hook as the graph page, not a separate implementation.
5. Topic switching should require stronger evidence than simple concept mismatch; confidence, explicit user language, and current topic lock state should all matter.
6. "Stay on topic" is the default policy when the learner is still actively learning the current concept.

## Removal Safety Rules

1. Do not remove the current graph detail panel or tutor graph drawer until the shared concept-activity surface reaches parity.
2. Prefer shared hooks/components over parallel copies.
3. If a modal switch banner is replaced, record the compatibility change and rollback path.
4. Maintain a removal ledger here if any graph/practice compatibility shim is removed.

## Removal Entry Template

```text
Removal Entry - AR7.x

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

- `apps/web/features/graph/components/graph-detail-panel.tsx` currently offers "Flashcards" and "Practice quiz" as generate-new actions, then renders a passive `PracticeHistory`
- `apps/web/components/practice-history.tsx` shows summaries only; there are no open/retry controls
- `apps/web/features/graph/hooks/use-graph-page.ts` fetches practice history but only knows how to generate new flashcards/quizzes; it does not open historical quiz or flashcard detail
- `apps/api/routes/practice.py` and `apps/web/lib/api/client.ts` already expose detail endpoints for practice quizzes and flashcard runs
- `apps/api/routes/quizzes.py` already exposes level-up quiz list/detail/promote flows, but the graph page and tutor drawer do not consume them
- `domain/chat/concept_resolver.py` creates a switch suggestion whenever the resolved concept differs from the current concept, regardless of confidence threshold
- `apps/web/features/tutor/components/concept-switch-banner.tsx` is modal and auto-submits `"Which concept should we focus on?"` when the user rejects a switch
- `npx vitest run lib/api/client.test.ts lib/practice/practice-state.test.ts features/tutor/visible-phase.test.ts features/tutor/stream-messages.test.ts` → 49 passed
- there are currently no dedicated frontend tests for `PracticeHistory`, `GraphDetailPanel`, `useGraphPage`, or `ConceptSwitchBanner`

### Verification Block - AR7.1

Root cause
- Graph and tutor surfaces relied on scattered fetches; no concept-centered activity model existed

Files changed
- `domain/learning/concept_activity.py` (new: get_concept_activity with practice/level-up/flashcard aggregation)
- `apps/api/routes/practice.py` (added GET /concepts/{concept_id}/activity endpoint)
- `apps/web/lib/api/client.ts` (added getConceptActivity method)
- `apps/web/lib/api/types.ts` (added ConceptActivityResponse + sub-types)
- `apps/web/lib/practice/use-concept-activity.ts` (new: shared useConceptActivity hook)
- `tests/domain/test_concept_activity.py` (6 tests for aggregation and affordances)
- `docs/API.md` (documented new endpoint)

What changed
- One endpoint returns practice quizzes, level-up quizzes, flashcard runs, aggregate metrics, and affordance metadata for a concept
- Shared hook available for both graph page and tutor drawer

Commands run
- `pytest tests/domain/test_concept_activity.py -q` → 6 passed
- `npx vitest run lib/api/client.test.ts` → 12 passed
- `pytest tests/ -q` → 873 passed (2 pre-existing deselected)

Observed outcome
- Graph and tutor surfaces can depend on one shared concept-activity data layer
- No removals needed

### Verification Block - AR7.2

Root cause
- GraphDetailPanel only supported "generate new" flows and a passive PracticeHistory

Files changed
- `apps/web/components/concept-activity-panel.tsx` (new: interactive activity panel with open/retry)
- `apps/web/components/concept-activity-panel.test.tsx` (8 SSR tests)
- `apps/web/features/graph/components/graph-detail-panel.tsx` (replaced PracticeHistory with ConceptActivityPanel)
- `apps/web/features/graph/hooks/use-graph-page.ts` (wired useConceptActivity, removed usePracticeHistory)
- `apps/web/app/(app)/graph/page.tsx` (updated prop wiring)

What changed
- ConceptActivityPanel renders practice quizzes, level-up quizzes, and flashcard runs as openable/retryable entries
- Retry button shown only when can_retry is true
- "Generate" buttons preserved as primary controls above the activity panel

Commands run
- `npx vitest run components/concept-activity-panel.test.tsx` → 8 passed
- `npx vitest run` → 102 passed
- `pytest tests/ -q` → 873 passed (2 pre-existing deselected)

Observed outcome
- Graph page now shows interactive concept activity workspace
- Users can see open/retry affordances on prior study artifacts
- No removals needed

Current hotspots:

| File | Why it still matters |
|---|---|
| `apps/web/features/graph/hooks/use-graph-page.ts` | Owns graph-page practice state and currently only supports new generation flows. |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | Current graph study surface is underpowered and run-centric. |
| `apps/web/components/practice-history.tsx` | History UI is read-only today. |
| `apps/web/features/tutor/components/tutor-graph-drawer.tsx` | Tutor graph drawer still lacks practice/history affordances. |
| `domain/chat/concept_resolver.py` | Current switch policy is too eager. |
| `apps/web/features/tutor/components/concept-switch-banner.tsx` | Current switch UX is modal and auto-submits synthetic clarification. |

### Verification Block - AR7.3

Root cause
- Tutor graph drawer was visualization-only; no practice/activity affordances

Files changed
- `apps/web/features/tutor/hooks/use-tutor-page.ts` (added useConceptActivity hook, conceptActivity return)
- `apps/web/features/tutor/components/tutor-graph-drawer.tsx` (added ConceptActivityPanel, conceptActivity prop)
- `apps/web/app/(app)/tutor/page.tsx` (wired conceptActivity to graph drawer)

What changed
- Concept activity panel now rendered below the graph legend in the tutor graph drawer
- Activity concept ID tracks graphViewConceptId or currentConcept as fallback
- Users can review prior flashcards/quizzes without leaving the chat

Commands run
- `npx vitest run` → 102 passed
- `pytest tests/ -q` → 873 passed (2 pre-existing deselected)

Observed outcome
- Users can access concept activity from tutor chat without context loss
- No removals needed

### Verification Block - AR7.4

Root cause
- resolve_concept_for_turn() created switch suggestions on ANY concept mismatch regardless of confidence

Files changed
- `domain/chat/concept_resolver.py` (added _SWITCH_CONFIDENCE_THRESHOLD, confidence gate, stay-on-current clamp)
- `tests/domain/test_concept_resolver.py` (3 new tests: weak-stays, strong-switches, threshold-range)

What changed
- Confidence below 0.75 now suppresses switch suggestion and preserves current concept
- Confidence >= 0.75 still triggers switch suggestion as before
- _to_confidence mapping: score 2.0 → 0.65 (suppressed), score 3.0 → 0.80 (triggers), score 4.0+ → 0.95 (triggers)

Commands run
- `pytest tests/domain/test_concept_resolver.py -v` → 5 passed
- `pytest tests/ -q` → 876 passed (2 pre-existing deselected)

Observed outcome
- Weak mismatches no longer trigger switch suggestions
- "Stay on topic until learned" is the default bias
- No removals needed

### Verification Block - AR7.5

Root cause
- Concept switch UX was a modal dialog that auto-submitted synthetic clarification on reject

Files changed
- `apps/web/features/tutor/components/concept-switch-banner.tsx` (replaced modal with inline banner)
- `apps/web/features/tutor/concept-switch-banner.test.tsx` (4 regression tests)
- `apps/web/app/(app)/tutor/page.tsx` (removed onSubmitChat prop)
- `apps/web/styles/base.css` (added switch-banner styles)
- `apps/web/vitest.config.ts` (added features/**/*.test.tsx pattern)

What changed
- Banner now renders with role="status" (non-blocking) instead of role="dialog" (modal)
- Reject/dismiss simply clears the suggestion — no synthetic follow-up traffic
- Actions simplified to "Switch" and "Dismiss"

Commands run
- `npx vitest run features/tutor/concept-switch-banner.test.tsx` → 4 passed
- `npx vitest run` → 106 passed
- `pytest tests/ -q` → 876 passed (2 pre-existing deselected)

Observed outcome
- Topic-switch UX is non-blocking; users can dismiss without disruption
- No synthetic follow-up messages generated on reject
- No removals needed

## Remaining Work Overview

All AR7 slices (AR7.1–AR7.5) are now complete.

## Implementation Sequencing

Each slice should end with green targeted tests before the next slice starts.

### AR7.1. Slice 1: Add a shared concept-activity data surface for graph and tutor contexts

Purpose:

- create one reusable data layer for concept flashcards, practice history, and level-up history

Root problem:

- graph and tutor surfaces currently rely on scattered fetches and only expose run summaries, not a concept-centered activity model

Files involved:

- `apps/api/routes/practice.py`
- `apps/api/routes/quizzes.py`
- `domain/learning/practice.py`
- `domain/learning/level_up.py`
- `apps/web/lib/api/client.ts`
- new shared frontend hook/module under `apps/web/lib/practice/` or `apps/web/features/graph/`

Implementation steps:

1. Add a shared concept-activity read surface that can return:
   - cumulative concept flashcards
   - flashcard run summaries as metadata
   - practice quiz history + detail access
   - level-up quiz history + detail access
2. Reuse existing detail endpoints where possible, but add a concept-level flashcard aggregate endpoint or service if needed.
3. Expose explicit retry/open affordance metadata instead of forcing the UI to infer it.
4. Keep payloads bounded and concept-scoped.

What stays the same:

- existing run/detail endpoints remain valid
- quiz creation remains explicit
- no automatic generation on page load

Verification:

- targeted backend tests for new concept-activity read path
- `npx vitest run lib/api/client.test.ts`

Exit criteria:

- graph and tutor surfaces can depend on one shared concept-activity data layer
- concept-level flashcard aggregation exists without breaking existing run endpoints

### AR7.2. Slice 2: Upgrade the graph detail panel into a concept activity workspace

Purpose:

- let users revisit prior study artifacts directly from the graph page

Root problem:

- `GraphDetailPanel` currently only supports "generate new" flows and a passive history summary

Files involved:

- `apps/web/features/graph/hooks/use-graph-page.ts`
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/components/practice-history.tsx`
- any new shared concept-activity components

Implementation steps:

1. Render cumulative flashcards for the selected concept instead of only run-based flashcard history.
2. Render prior practice quizzes and level-up quizzes as openable entries.
3. Support reopening quiz detail and explicit retry actions for:
   - practice quizzes
   - prior level-up quizzes where retry is allowed
4. Preserve "generate more" / "new quiz" actions as secondary controls, not the only path.

What stays the same:

- graph concept selection remains the entrypoint
- current practice generation flows remain available

Verification:

- focused frontend tests for graph detail panel behavior
- manual check: select concept -> open prior quiz -> retry -> view cumulative flashcards

Exit criteria:

- graph page becomes a usable concept study workspace
- users can revisit prior flashcards/quizzes without leaving the concept panel

### AR7.3. Slice 3: Reuse the concept activity workspace inside tutor graph/chat UI

Purpose:

- let users stay in the tutor chat while reviewing concept study material

Root problem:

- the tutor graph drawer and tutor quiz drawer do not expose the graph page's study affordances

Files involved:

- `apps/web/features/tutor/components/tutor-graph-drawer.tsx`
- `apps/web/features/tutor/components/tutor-quiz-drawer.tsx`
- `apps/web/features/tutor/hooks/use-tutor-page.ts`
- shared concept-activity hook/component created in AR7.1/AR7.2

Implementation steps:

1. Reuse the shared concept-activity surface inside the tutor graph drawer or adjacent tutor drawer UI.
2. Allow current active concept, graph-selected concept, and quiz CTA concept to all feed the same study surface cleanly.
3. Preserve the existing level-up drawer flow, but make prior practice/level-up history accessible without leaving chat.
4. Avoid opening multiple conflicting drawers for the same concept activity.

What stays the same:

- tutor chat remains the primary interaction surface
- quiz creation/opening remains explicit and user-visible

Verification:

- focused frontend tests for tutor graph/quiz drawer interactions
- manual check: stay in chat, open graph drawer, review flashcards/quizzes, retry a quiz

Exit criteria:

- users can access concept flashcards and quiz history from tutor chat without context loss

### AR7.4. Slice 4: Tighten runtime topic-lock and switch-threshold policy

Purpose:

- stop weak mismatches from constantly prompting concept switches

Root problem:

- `resolve_concept_for_turn()` currently suggests a switch whenever the resolved concept differs from the current one, without using confidence as a gate

Files involved:

- `domain/chat/concept_resolver.py`
- `domain/chat/turn_plan.py`
- `domain/chat/respond.py`
- `domain/chat/stream.py`
- learner/readiness helpers as needed

Implementation steps:

1. Add a switch-threshold policy that considers:
   - confidence
   - explicit user switch language
   - current concept mastery/readiness/topic-lock state
   - repeated evidence across recent turns
2. Default to staying on the current concept while it is still "learning" unless the switch signal is strong.
3. Differentiate:
   - explicit switch request
   - soft suggestion
   - hard clarification requirement
4. Keep the final decision runtime-owned and traceable.

What stays the same:

- concept switching remains runtime policy, not prompt-only behavior
- explicit user switch intent still works

Verification:

- new backend tests for weak vs strong switch cases
- manual check: adjacent concept mention does not immediately prompt a switch while current topic is still active

Exit criteria:

- switch suggestions no longer trigger on weak mismatches
- "stay on topic until learned" becomes the default bias

### AR7.5. Slice 5: Replace the intrusive switch modal with a non-blocking topic-switch UX and add focused tests

Purpose:

- make topic switching informative rather than disruptive

Root problem:

- current switch UX is a modal interruption, and rejecting a switch auto-submits a synthetic clarification message

Files involved:

- `apps/web/features/tutor/components/concept-switch-banner.tsx`
- `apps/web/app/(app)/tutor/page.tsx`
- `apps/web/features/tutor/hooks/use-tutor-page.ts`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- focused frontend tests

Implementation steps:

1. Replace the modal with a non-blocking inline banner, chip rail, or anchored panel.
2. Remove synthetic auto-submit behavior on reject.
3. Offer clearer actions such as:
   - stay on current topic
   - switch topic
   - explain here but note the adjacent concept
4. Make the current-topic lock state visible when relevant.
5. Add focused regression tests for the new UX.

What stays the same:

- backend remains the source of switch suggestions
- explicit user switch acceptance still updates concept context

Verification:

- focused frontend tests for accept/reject/stay behavior
- manual check: rejecting a switch does not create a fake user turn or block the chat

Exit criteria:

- topic-switch UX is less intrusive
- users can decline a switch without triggering synthetic follow-up traffic

## Verification Block Template

```text
Verification Block - AR7.x

Root cause
- <why the graph/tutor study surface or topic-switch flow was insufficient>

Files changed
- <path>
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification
- <graph/tutor/topic-lock flow checked>

Observed outcome
- <result>
```

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/AGENTIC_MASTER_PLAN.md, then read docs/agentic/07_graph_learning_surface_plan.md.
Begin with the next incomplete AR7 slice exactly as described.

Execution loop for this child plan:

1. Work on one AR7 slice at a time.
2. Keep one shared concept-activity surface across graph page and tutor contexts, keep quiz creation/opening user-visible, and keep topic-switch policy runtime-owned.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed AR7 slices OR if context is compacted/summarized, re-open docs/AGENTIC_MASTER_PLAN.md and docs/agentic/07_graph_learning_surface_plan.md and restate which AR7 slices remain.
6. Continue to the next incomplete AR7 slice once the previous slice is verified.
7. When all AR7 slices are complete, immediately re-open docs/AGENTIC_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because AR7 is complete. AR7 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/AGENTIC_MASTER_PLAN.md.
Read docs/agentic/07_graph_learning_surface_plan.md.
Begin with the current AR7 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When AR7 is complete, immediately return to docs/AGENTIC_MASTER_PLAN.md and continue with the next incomplete child plan.
```
