# CUX4 — Slideover & Practice UX

Parent plan: `docs/chat_ux/CUX_MASTER_PLAN.md`
Last updated: 2026-03-05

## Purpose

Fix the concept graph sizing issue in the slideover, add flashcard and quiz generation buttons to the practice tab (matching the graph page's existing generate functionality), and make past quizzes revisitable with retry capability.

## Dependencies

- Independent of CUX1-3. Can run in parallel with other tracks.

## Slices

### S4.1 — Fix concept graph sizing in slideover

**What:** The `<SigmaGraph>` component in the slideover's "graph" tab doesn't fill the available width. It appears to have a hardcoded width constraint (320px). Make it responsive to fill the slideover's full width.

**Files to change:**
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — update graph container sizing (remove hardcoded width, use `width: 100%` or flex)
- Possibly `apps/web/components/sigma-graph/stable-sigma-container.tsx` — ensure it respects parent container size

**Exit criteria:**
- Graph fills the full width of the slideover panel
- Graph height remains proportional (no squishing)
- Graph interactions (zoom, pan, click) still work correctly
- No layout overflow or scrollbar issues

---

### S4.2 — Add generate buttons to practice tab

**What:** The practice tab in the slideover currently shows flashcard stack and quiz history but lacks buttons to generate new flashcards or quizzes. Add "Generate flashcards" and "Generate quizzes" buttons similar to those on the graph page's concept detail panel.

**Files to change:**
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — add generate buttons to practice tab section
- Reuse existing generate logic from graph page (find the existing handlers and API calls)
- `apps/web/hooks/use-tutor-page.ts` — expose generate handlers if not already available

**Exit criteria:**
- "Generate flashcards" button visible in practice tab
- "Generate quizzes" button visible in practice tab
- Buttons trigger same generation logic as graph page
- Loading states shown during generation
- Generated items appear in the respective lists after completion

---

### S4.3 — Quiz history with retry

**What:** Past quizzes (both level-up and practice) should be shown in a scrollable list in the practice tab. Each quiz entry shows the concept name, score, date, and a "Retry" button.

**Files to change:**
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — enhance quiz history section
- `apps/web/components/quiz-history.tsx` or equivalent — add retry button to each quiz entry
- API integration — ensure quiz history endpoint returns necessary data

**Exit criteria:**
- Quiz history shows all past quizzes for the current concept
- Each entry shows: concept name, score (e.g., "4/5"), date, pass/fail status
- "Retry" button on each quiz entry
- List is scrollable when many quizzes exist

---

### S4.4 — Retry creates new attempt

**What:** When user clicks "Retry" on a past quiz, create a new quiz attempt for the same concept. The old quiz record is not mutated. The new attempt appears in the history after completion.

**Files to change:**
- `apps/web/components/quiz-history.tsx` or equivalent — retry click handler
- API call to create new quiz with same concept_id
- Ensure quiz history list refreshes after new attempt

**Exit criteria:**
- Retry creates a fresh quiz (new questions, new ID)
- Old quiz record unchanged in history
- New quiz appears in history after submission
- User can retry any quiz, any number of times

---

## Removal Ledger

(Populated during implementation)

## Audit Workspace

(Initially empty — populated during audit cycles)
