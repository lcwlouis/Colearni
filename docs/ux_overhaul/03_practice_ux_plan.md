# CoLearni UX Overhaul — Practice & Learning UX Plan

Last updated: 2026-03-02

Parent plan: `docs/UX_OVERHAUL_MASTER_PLAN.md`

Archive snapshots:
- `none` (new plan)

## Plan Completeness Checklist

1. archive snapshot path(s) ✓
2. current verification status ✓
3. ordered slice list with stable IDs ✓
4. verification block template (inherited from master) ✓
5. removal entry template (inherited from master) ✓
6. final section `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✓

## Non-Negotiable Run Rules

1. Re-read this file at start, after every 2 slices, after context compaction, before completion claims.
2. A slice is ONLY complete with code changed + behavior verified + verification block produced.
3. Work PR-sized: `chore(refactor): <slice-id> <short description>`.
4. If a behavior change risk is discovered, STOP and update this plan.
5. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

Redesign the flashcard and quiz UX so that users can review their learning history, retry practice quizzes, and access flashcards as a unified deck rather than fragmented generation sessions.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- User requirements (verbatim from session)
- Code investigation of flashcard/quiz backend APIs and frontend components
- `apps/api/routes/flashcards.py`, `apps/api/routes/practice_quiz.py`
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/features/graph/components/concept-activity-panel.tsx`

## Executive Summary

What exists today:
- Backend APIs: `listFlashcardRuns`, `getFlashcardRun`, `listPracticeQuizzes`, `getPracticeQuiz`
- Flashcards stored per `run_id` in `practice_flashcard_bank` with dedup fingerprints
- Exhaustion detection: returns `has_more: false` + `exhausted_reason` when content is exhausted
- `ConceptActivityPanel` shows past flashcard runs and quiz history but with limited UX
- Practice quizzes have `can_retry` flag; level-up quizzes do NOT

What this track adds:
1. **Unified flashcard stack** — all flashcards for a concept merged into one deck, not separate sessions
2. **"Generate more" button** — LLM decides if there's more content; button disabled when exhausted
3. **Quiz history browser** — list of past quizzes with datetime, click to view, retry button
4. **Quiz retry flow** — reset answers and let user attempt again (practice only)

## Non-Negotiable Constraints

1. Level-up quizzes are NEVER retryable — only practice quizzes
2. Flashcard dedup fingerprints must be preserved — no duplicate cards across generations
3. "Generate more" must respect LLM exhaustion signal — cannot generate infinitely
4. Existing flashcard and quiz API contracts must not break
5. Concept detail panel layout: Flashcards section + Quizzes section below description/aliases/connections

## Completed Work

- Backend APIs for listing and getting flashcard runs / practice quizzes — fully functional
- Exhaustion detection in flashcard generation — works correctly
- `ConceptActivityPanel` shows basic run list

## Remaining Slice IDs

- `UXP.1` Unified flashcard stack viewer
- `UXP.2` Generate-more with exhaustion awareness
- `UXP.3` Quiz history browser with retry
- `UXP.4` Remove redundant practice buttons and improve layout
- `UXP.5` Port original flashcard and quiz designs

## Decision Log

1. Flashcard stack view: merge all `run_id` sessions into one flat list, sorted by creation date, shown as a swipeable/flippable card deck.
2. "Generate more" button lives at the bottom of the flashcard stack — clicking triggers a new generation run, appends new cards to the deck.
3. When exhausted, the button is replaced with a text message: "All available content has been covered" (or similar).
4. Quiz history: chronological list with the most recent quiz at the top. Each entry shows: datetime, score (if completed), status.
5. Clicking a quiz entry opens it in review mode (read-only, showing correct/incorrect answers).
6. "Retry" button on a quiz clears the user's answers and lets them attempt the same questions again.
7. These views are accessible from the concept detail panel (graph side panel) under expandable sections.

## Current Verification Status

- `PYTHONPATH=. pytest -q`: 922 passed
- `npx vitest run`: 106 passed

Hotspots:

| File | Role |
|---|---|
| `apps/web/features/graph/components/graph-detail-panel.tsx` | Main concept detail panel — add flashcard/quiz sections |
| `apps/web/features/graph/components/concept-activity-panel.tsx` | Existing activity panel — refactor |
| `apps/api/routes/flashcards.py` | Flashcard endpoints |
| `apps/api/routes/practice_quiz.py` | Practice quiz endpoints |
| `domain/practice/flashcard_service.py` | Flashcard generation + exhaustion logic |
| `domain/practice/quiz_service.py` | Quiz generation + retry logic |

## Implementation Sequencing

### UXP.1. Unified flashcard stack viewer

Purpose:
- Show all flashcards for a concept as a single deck instead of separate generation sessions

Files involved:
- `apps/web/features/graph/components/flashcard-stack.tsx` (new)
- `apps/web/features/graph/components/graph-detail-panel.tsx` (modified)
- `apps/web/lib/api/flashcards.ts` (may need a new endpoint or client-side merge)

Implementation steps:
1. Create `flashcard-stack.tsx`:
   - Fetch all flashcard runs for the selected concept
   - Merge all cards into a single array, sorted by creation date (oldest first)
   - Display as a stack: show one card at a time with flip animation (front: question, back: answer)
   - Navigation: prev/next buttons, progress indicator (e.g., "5/23")
   - If no flashcards exist, show a "Generate flashcards" button
2. Add a "Flashcards" section to `graph-detail-panel.tsx`:
   - Below Description, Aliases, and Connections
   - Expandable/collapsible section
   - Opens the `FlashcardStack` component when expanded
3. Ensure the flashcard dedup fingerprints prevent duplicates when multiple runs are merged.

Verification:
- `npx vitest run`
- Manual: select concept with existing flashcards → unified stack shows all cards
- Manual: navigate through cards → prev/next works, flip works
- Manual: concept with no flashcards → "Generate flashcards" button shown

Exit criteria:
- All flashcards for a concept visible in one stack
- No duplicate cards shown
- Navigation through the deck is smooth

### UXP.2. Generate-more with exhaustion awareness

Purpose:
- Let users generate additional flashcards and automatically disable when content is exhausted

Files involved:
- `apps/web/features/graph/components/flashcard-stack.tsx` (modified)
- Backend may need no changes (exhaustion is already detected)

Implementation steps:
1. Add "Generate more" button at the end of the flashcard stack (after the last card)
2. On click: call the existing flashcard generation endpoint for this concept
3. Poll or await the result; append new cards to the existing stack
4. If the response returns `has_more: false`:
   - Disable the button
   - Show exhaustion message: "All content for this concept has been covered"
5. Show a loading state while generating.
6. After generation completes, automatically navigate to the first new card.

Verification:
- Manual: click "Generate more" → new cards appear in the stack
- Manual: generate until exhausted → button disables with message
- Manual: loading state visible during generation

Exit criteria:
- Users can request more flashcards without leaving the view
- Exhaustion is clearly communicated
- No duplicate cards generated

### UXP.3. Quiz history browser with retry

Purpose:
- Show past quizzes for a concept with the ability to view results and retry

Files involved:
- `apps/web/features/graph/components/quiz-history.tsx` (new)
- `apps/web/features/graph/components/quiz-viewer.tsx` (new or refactored from existing)
- `apps/web/features/graph/components/graph-detail-panel.tsx` (modified)

Implementation steps:
1. Create `quiz-history.tsx`:
   - Fetch all practice quizzes for the selected concept
   - Display as a chronological list (most recent first)
   - Each entry shows: date/time, score (if completed), question count, status
   - Click an entry → opens quiz in review mode
2. Create `quiz-viewer.tsx` (or refactor existing quiz component):
   - Review mode: show questions with user's answers, correct answers highlighted
   - Retry mode: same questions, answers cleared, user can attempt again
   - "Retry" button visible only on practice quizzes (NOT level-up)
3. Add "Quizzes" section to `graph-detail-panel.tsx`:
   - Below Flashcards section
   - Expandable/collapsible
   - Shows quiz history list when expanded
4. Retry implementation:
   - When "Retry" is clicked, create a new attempt record (or reset the existing one, depending on backend design)
   - The quiz questions stay the same, only answers are cleared
   - After retry completion, score is updated

Verification:
- `npx vitest run`
- Manual: select concept with past quizzes → history list shown with dates and scores
- Manual: click a quiz → opens in review mode with correct/incorrect highlighting
- Manual: click "Retry" on a practice quiz → answers cleared, can re-answer
- Manual: level-up quiz → no "Retry" button

Exit criteria:
- Past quizzes are browsable per concept
- Quiz review mode shows correct answers
- Retry works for practice quizzes only
- Level-up quizzes have no retry option

### UXP.4. Remove redundant practice buttons and improve layout

Purpose:
- Remove duplicate inline flashcard/quiz buttons from graph detail panel
- The collapsible sections (Flashcards, Quizzes) already provide full functionality
- Consider replacing dropdown/collapsible sections with always-visible tabbed sections if space allows
- User preference: avoid dropdowns where possible — prefer tabs or always-visible sections

Files involved:
- `apps/web/features/graph/components/graph-detail-panel.tsx`

Implementation steps:
1. Remove the inline "Flashcards" and "Practice quiz" buttons (currently above the collapsible sections)
2. Convert the `<details>/<summary>` collapsible sections to tabs or always-visible cards
3. Keep the "Close" button for dismissing the panel
4. Ensure the practice sections are easily discoverable without needing to click a dropdown

Exit criteria:
- No duplicate buttons for the same action
- Flashcard and quiz sections are visible without clicking dropdowns
- Panel layout is clean and intuitive

### UXP.5. Port original flashcard and quiz designs

Purpose:
- Port the original flashcard card design (flip animation, styling, front/back layout) into the unified FlashcardStack viewer
- Port the original quiz design (question layout, answer marking with green/red, score display) into the QuizHistory retry view
- Fix: retry submit button must show answer marking (correct/incorrect highlighting) after submission, same as original quiz

Files involved:
- `apps/web/features/graph/components/flashcard-stack.tsx` (or wherever the unified stack lives)
- `apps/web/features/graph/components/quiz-history.tsx` (or wherever quiz retry lives)
- Original flashcard component (find and reference for design porting)
- Original quiz component (find and reference for design porting)

Implementation steps:
1. Find the original flashcard component design (pre-UXP changes) — port its card layout, flip animation, and styling
2. Find the original quiz component design — port its question rendering, answer choice highlighting (green for correct, red for incorrect), and score display
3. In FlashcardStack: use the ported card design for each card in the stack
4. In QuizHistory retry: after submit, show marking on each answer (green/red highlighting) just like the original quiz
5. Ensure "Generate more" button uses the same card design for new cards

Exit criteria:
- Flashcard stack uses original card design with flip animation
- Quiz retry shows answer marking after submission
- Visual consistency with the proven original designs

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the Self-Audit Convergence Protocol may reopen slices in this child plan. When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
4. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
5. Only the specific issue identified in the Audit Report is addressed — do not widen scope

## Execution Order (Update After Each Run)

1. `UXP.1` Unified flashcard stack viewer
2. `UXP.2` Generate-more with exhaustion awareness
3. `UXP.3` Quiz history browser with retry
4. `UXP.4` Remove redundant practice buttons and improve layout
5. `UXP.5` Port original flashcard and quiz designs

## Verification Matrix

```bash
PYTHONPATH=. pytest -q
npx vitest run  # from apps/web/
```

## Removal Ledger

### Removal Entry — UXP.4

**Removed artifact**
- Inline "Flashcards" and "Practice quiz" buttons in `graph-detail-panel.tsx`
- Inline `StatefulFlashcardList` rendering
- Inline `PracticeQuizCard` rendering
- Inline flashcard error state display
- `<details>/<summary>` collapsible sections for Flashcards, Quizzes, and Chat

**Reason for removal**
- Duplicate functionality — FlashcardStack and QuizHistory in tabbed sections provide the same and better UX
- Collapsible sections replaced with always-visible tabs per user preference

**Replacement**
- Tabbed section with three tabs: Flashcards (FlashcardStack), Quizzes (QuizHistory), 💬 Chat (ConceptChatLinks)

**Reverse path**
- `git revert` the commit

**Compatibility impact**
- Internal only — all props still accepted in `GraphDetailPanelProps` interface; no upstream callers break

**Verification**
- FlashcardStack in Flashcards tab works identically
- QuizHistory with retry in Quizzes tab works identically
- Chat tab renders ConceptChatLinks identically
- ConceptActivityPanel remains below tabs

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/03_practice_ux_plan.md.
Begin with the next incomplete UXP slice exactly as described.

Execution loop for this child plan:

1. Work on one UXP slice at a time.
2. Level-up quizzes are NEVER retryable — only practice quizzes. Flashcard dedup fingerprints must be preserved. "Generate more" must respect the LLM exhaustion signal (has_more=false). Keep flashcard awareness bounded.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed UXP slices OR if context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/03_practice_ux_plan.md and restate which UXP slices remain.
6. Continue to the next incomplete UXP slice once the previous slice is verified.
7. When all UXP slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXP is complete. UXP completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle, only work on slices marked as "reopened". Produce audit-prefixed Verification Blocks. Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/03_practice_ux_plan.md.
Begin with the current UXP slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXP is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue with the next incomplete child plan.
```
