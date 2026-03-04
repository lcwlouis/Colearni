# Colearni Refinement — Frontend Chat UX Plan

Last updated: 2026-03-04

Parent plan: `docs/CREF_MASTER_PLAN.md`

Archive snapshots:
- `docs/archive/cref/05_frontend_chat_ux_plan_v0.md`

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template (inherited from master)
5. removal entry template (inherited from master)
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (template in master plan).
5. If implementation uncovers a behavior change risk, STOP and update this plan and the master plan before widening scope.
6. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

This track addresses multiple UX issues on the chat page frontend. The chat page's slideover panel needs restructuring (collapse to a button, fix sizing), practice tools need better access, the level-up button is misplaced, chat titles should reflect the current topic, and users need a regeneration button for bad responses.

These are mostly frontend-only changes with minimal backend coupling, except for the regeneration button which depends on CREF4.4 (regeneration endpoint) and the chat title which may need a small backend adjustment.

## Inputs Used

- `docs/CREF_MASTER_PLAN.md` (parent plan)
- `docs/FRONTEND.md` — component inventory, stack, patterns
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — current slideover
- `apps/web/components/level-up-card.tsx` — level-up button
- `domain/chat/title_gen.py` — title generation logic

## Executive Summary

What works today:
- Tutor slideover with Graph, Level-up, Practice tabs
- Level-up card with start quiz button
- Chat title generation from query/concept name
- Practice quiz and flashcard display in slideover

What this track fixes or adds:
1. Collapse slideover into a toggle button (hamburger or info icon)
2. Add generate flashcards/quizzes buttons to the practice slide
3. Fix concept graph slide sizing in the slideover
4. Remove level-up quiz button from the main chat page
5. Set chat title to current topic name
6. Add regeneration button for assistant messages (frontend side)

## Non-Negotiable Constraints

1. Follow FRONTEND.md patterns: App Router, React 19, no anti-patterns
2. Keep client components small — push logic to server components where possible
3. No `useEffect` for data fetching
4. Test with vitest where applicable
5. Must work on mobile viewports (slideover → button is a mobile improvement)

## Completed Work (Do Not Reopen Unless Blocked)

- Tutor slideover with tabs
- Level-up card component
- Practice quiz/flashcard display
- Sigma.js graph in slideover

## Remaining Slice IDs

- `CREF5.1` Collapse Slideover to Toggle Button
- `CREF5.2` Practice Slide Buttons
- `CREF5.3` Fix Concept Graph Slide Sizing
- `CREF5.4` Remove Level-Up Quiz Button
- `CREF5.5` Chat Title from Current Topic
- `CREF5.6` Regeneration Button UI

## Decision Log

1. Slideover collapses to an icon button (info/hamburger) in the top-right of the chat area. Clicking opens the slideover panel.
2. Practice slide gets "Generate Flashcards" and "Generate Quiz" buttons similar to the graph page's concept detail panel.
3. Graph slide sizing fix: ensure the Sigma container fills 100% width of the slideover.
4. Level-up quiz button removed from the main chat area — it remains accessible from the slideover's Level-up tab.
5. Chat title = concept display name from the session's current topic. Fallback to existing title gen if no topic is set.
6. Regeneration button appears on hover of assistant messages, similar to ChatGPT's regenerate icon.

## Current Verification Status

- `cd apps/web && npm run lint`: baseline to be recorded
- `cd apps/web && npm run typecheck`: baseline to be recorded

Hotspots:

| File | Why it matters |
|---|---|
| `apps/web/features/tutor/components/tutor-slide-over.tsx` | Slideover layout — CREF5.1, 5.2, 5.3 |
| `apps/web/components/level-up-card.tsx` | Level-up button — CREF5.4 |
| `domain/chat/title_gen.py` | Title generation — CREF5.5 |
| `apps/web/components/chat-response.tsx` | Regeneration button — CREF5.6 |

## Implementation Sequencing

### CREF5.1. Slice 1: Collapse Slideover to Toggle Button

Purpose:
- Replace the always-visible slideover with a toggle button that opens/closes the panel.

Root problem:
- The slideover takes up screen real estate and is always visible. On smaller screens or when the user wants to focus on the chat, it's intrusive.

Files involved:
- `apps/web/features/tutor/components/tutor-slide-over.tsx`
- Parent page component that renders the slideover

Implementation steps:
1. Add a toggle button (info icon or hamburger) to the chat page header/toolbar
2. The slideover starts closed by default
3. Clicking the button toggles the slideover open/closed
4. Use a smooth slide animation (CSS transition or Radix UI Sheet)
5. Persist the open/closed state in `localStorage`
6. Update the layout so chat area expands when slideover is closed

What stays the same:
- Slideover content (Graph, Level-up, Practice tabs)
- All functionality within the slideover
- Tab switching logic

Verification:
- `cd apps/web && npm run lint && npm run typecheck`
- Manual check: button toggles slideover open/closed
- Verify chat area resizes properly when slideover closes

Exit criteria:
- Slideover is hidden by default, opened via button
- Smooth animation
- State persisted across page loads

### CREF5.2. Slice 2: Practice Slide Buttons

Purpose:
- Add "Generate Flashcards" and "Generate Quiz" buttons to the practice tab of the slideover, similar to the graph page's concept detail panel.

Root problem:
- The practice slide in the chat slideover doesn't have generate buttons, making it less useful than the graph page for practice tool access.

Files involved:
- `apps/web/features/tutor/components/tutor-slide-over.tsx` (practice tab)
- `apps/web/features/graph/` (reference implementation for buttons)

Implementation steps:
1. Add "Generate Flashcards" and "Generate Quiz" buttons to the practice tab
2. Wire the buttons to the same API calls used on the graph page
3. Use the current session's concept_id as the target concept
4. Show loading state during generation
5. Display generated content inline in the practice tab

What stays the same:
- Practice quiz/flashcard display components
- Backend practice API
- Graph page buttons (this duplicates them to the chat slideover)

Verification:
- `cd apps/web && npm run lint && npm run typecheck`
- Manual check: buttons appear in practice tab, generate content works

Exit criteria:
- Both buttons present and functional
- Generated content displays in the practice tab
- Loading states work correctly

### CREF5.3. Slice 3: Fix Concept Graph Slide Sizing

Purpose:
- Fix the Sigma.js graph container in the slideover to fill the full width of the panel.

Root problem:
- The concept graph in the slideover has a sizing issue — it doesn't fill the width, leaving an awkward gap.

Files involved:
- `apps/web/features/tutor/components/tutor-slide-over.tsx`
- `apps/web/components/sigma-graph.tsx` (or wherever the graph is rendered in the slideover)

Implementation steps:
1. Inspect the graph container's CSS — likely a fixed width or missing `w-full`
2. Ensure the Sigma container has `width: 100%` and appropriate `height`
3. Check for padding/margin issues in the slideover tab content area
4. Verify the graph resizes correctly when the slideover opens (Sigma may need a resize event)
5. Add `sigma.refresh()` call after slideover animation completes if needed

What stays the same:
- Graph data fetching
- Graph interaction (click, hover, zoom)
- All other slideover tabs

Verification:
- `cd apps/web && npm run lint && npm run typecheck`
- Manual check: graph fills the full width of the slideover panel
- Verify graph is interactive (click, zoom work)

Exit criteria:
- Graph fills slideover width
- No awkward gaps or overflow
- Graph is fully interactive

### CREF5.4. Slice 4: Remove Level-Up Quiz Button

Purpose:
- Remove the level-up quiz button/card from the main chat page area.

Root problem:
- The level-up quiz button is on the main chat page, which is cluttered. It should only be accessible from the slideover's Level-up tab.

Files involved:
- Parent chat page component that renders `level-up-card.tsx`
- `apps/web/components/level-up-card.tsx` (may need adjustment)

Implementation steps:
1. Find where `LevelUpCard` is rendered in the main chat area
2. Remove the rendering from the main chat page
3. Ensure it's still rendered in the slideover's Level-up tab
4. Clean up any orphaned props or state related to the removed button

What stays the same:
- Level-up card component itself
- Level-up functionality in the slideover
- Quiz generation and grading

Verification:
- `cd apps/web && npm run lint && npm run typecheck`
- Manual check: no level-up button on main chat page
- Verify level-up is still accessible from slideover

Exit criteria:
- Level-up button removed from main chat area
- Still accessible from slideover
- No orphaned code

### CREF5.5. Slice 5: Chat Title from Current Topic

Purpose:
- Set the chat session title to the currently active topic/concept name instead of generating it from the query.

Root problem:
- Chat titles are generated from the user's first query, which can be vague. Using the concept name is more descriptive and consistent.

Files involved:
- `domain/chat/title_gen.py`
- `domain/chat/session_memory.py` (calls title generation)
- Frontend: session list display

Implementation steps:
1. Modify `generate_session_title()` to prioritize `concept_name` when available
2. If a concept is set for the session, use it directly as the title (e.g., "Python Loops")
3. If no concept is set, fall back to existing query-based generation
4. When the concept changes mid-session, update the title to reflect the new concept
5. Update tests

What stays the same:
- Session list display
- Fallback title generation for sessions without a concept

Verification:
- `pytest -q tests/`
- Manual check: new chat session shows concept name as title
- Verify title updates when concept changes

Exit criteria:
- Chat title matches current concept name
- Fallback works for sessions without concepts
- Existing sessions are not affected

### CREF5.6. Slice 6: Regeneration Button UI

Purpose:
- Add a regeneration button to assistant messages in the chat UI.

Root problem:
- Users cannot retry a bad response without rephrasing. A regen button provides a quick retry.

Files involved:
- `apps/web/components/chat-response.tsx`
- Frontend API client (call CREF4.4 endpoint)

Implementation steps:
1. Add a regeneration icon button (↻) that appears on hover of assistant messages
2. Clicking calls `POST /chat/sessions/{id}/messages/{id}/regenerate`
3. Replace the current assistant message with the new streamed response
4. Show loading state during regeneration
5. Handle errors (show toast notification)
6. Only show on the last assistant message (or on failed messages)

What stays the same:
- Message display format
- Streaming consumption logic
- All other message interactions

Verification:
- `cd apps/web && npm run lint && npm run typecheck`
- Manual check: regen button appears on hover, clicking regenerates the response
- Verify old message is replaced with new one

Exit criteria:
- Regen button visible on hover
- Regeneration works with streaming
- Error handling with user feedback

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the master plan's Self-Audit Convergence Protocol may reopen slices in this child plan. The audit uses a **Fresh-Eyes** approach: the auditor treats each slice as if it has NOT been implemented, independently analyzes what should exist, then compares against actual code.

When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. The auditor's fresh-eyes analysis is recorded in the Audit Workspace below
4. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
5. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
6. The reopened slice is **re-implemented from scratch** — do not just patch the previous attempt. Re-read the slice definition, think about what needs to happen, implement it properly, then verify.
7. Only the specific issue identified in the Audit Report is addressed — do not widen scope

**IMPORTANT**: Tests passing is necessary but NOT sufficient for marking a reopened slice as done. The auditor must confirm the logic is correct through code review, not just test results.

## Audit Workspace

This section is initially empty. During the Self-Audit Convergence Protocol, the auditor writes their fresh-eyes analysis here. For each slice being audited:

1. **Before looking at any code**, write down what SHOULD exist based on the slice definition
2. **Then** open the code and compare against the independent analysis
3. Document gaps, verdict, and reasoning

```text
(Audit entries will be appended here during the audit convergence loop)
```

## Execution Order (Update After Each Run)

1. `CREF5.1` Collapse Slideover to Toggle Button
2. `CREF5.2` Practice Slide Buttons
3. `CREF5.3` Fix Concept Graph Slide Sizing
4. `CREF5.4` Remove Level-Up Quiz Button
5. `CREF5.5` Chat Title from Current Topic
6. `CREF5.6` Regeneration Button UI

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
cd apps/web && npm run lint
cd apps/web && npm run typecheck
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read docs/CREF_MASTER_PLAN.md, then read docs/cref/05_frontend_chat_ux_plan.md.
Begin with the next incomplete CREF5 slice exactly as described.

Execution loop for this child plan:

1. Work on one CREF5 slice at a time.
2. Follow FRONTEND.md patterns. App Router, React 19. No anti-patterns. Small client components.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed CREF5 slices OR if context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and docs/cref/05_frontend_chat_ux_plan.md and restate which CREF5 slices remain.
6. Continue to the next incomplete CREF5 slice once the previous slice is verified.
7. When all CREF5 slices are complete, immediately re-open docs/CREF_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because CREF5 is complete. CREF5 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

If this child plan is being revisited during an audit cycle:
- Treat every reopened slice as if it has NOT been implemented.
- In the Audit Workspace, write what SHOULD exist BEFORE looking at code.
- Then compare against actual implementation.
- Re-implement from scratch if gaps are found — do not just patch.
- Tests passing is NOT sufficient — confirm logic correctness through code review.
- Only work on slices marked as "reopened". Do not re-examine slices that passed the audit.

START:

Read docs/CREF_MASTER_PLAN.md.
Read docs/cref/05_frontend_chat_ux_plan.md.
Begin with the current CREF5 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When CREF5 is complete, immediately return to docs/CREF_MASTER_PLAN.md and continue with the next incomplete child plan.
```
