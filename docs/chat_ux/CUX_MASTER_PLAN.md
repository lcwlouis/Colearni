# Chat UI/UX Overhaul — Master Plan

Last updated: 2026-03-05

Archive snapshots:
- `none`

Template usage:
- This is the cross-track execution plan for the Chat UI/UX overhaul.
- It does not replace any other active plans.
- All child plans are subordinate to this document.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s) ✅
2. current verification status ✅
3. ordered track list with stable IDs ✅
4. verification block template ✅
5. removal entry template ✅
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✅

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the child plan are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (see template below).
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. Routes must stay thin — no business logic in API handlers.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

The current Tutor Chat experience has several UX friction points: chats can drift across multiple topics creating confusion, the title bar shows a static "Tutor Chat" label instead of the actual topic, topic display is unreliable, the slideover panel is cluttered, and quizzes lack revisitability. The topic hierarchy (umbrella → topic → subtopic → granular) is not surfaced to users or leveraged by the agent.

The existing backend has a per-turn concept resolver (`concept_resolver.py`) that can switch topics mid-chat, and a deterministic title generator (`title_gen.py`) that derives titles from the resolved concept. The frontend has a slideover with three tabs (graph, level-up, practice) and an inline concept-switch banner.

This plan restructures the chat experience around a **1-topic-per-chat** model, surfaces topic hierarchy, refactors the slideover into a collapsible sidebar, and improves quiz revisitability.

## Inputs Used

This plan is based on:

- User feedback (13 specific requests)
- `docs/PRODUCT_SPEC.md` — chat response model, mastery states, quiz card spec
- `docs/ARCHITECTURE.md` — conductor pipeline, concept resolver, evidence planner
- `docs/GRAPH.md` — tier system (umbrella/topic/subtopic/granular), canonical graph
- `docs/FRONTEND.md` — component patterns, Next.js App Router, Sigma.js
- `docs/CODEX.md` — boundary rules, budget constraints, thin routes
- Current codebase: `apps/web/app/(app)/tutor/page.tsx`, `domain/chat/concept_resolver.py`, `domain/chat/title_gen.py`, `adapters/db/chat.py`, `core/schemas/chat.py`

## Executive Summary

What is already in good shape:
- Per-turn concept resolution with confidence scoring
- Deterministic title generation (no LLM)
- Concept tier system in canonical graph
- Streaming chat with phases/activities
- Level-up quiz and practice mode foundations
- Slideover with graph/quiz/practice tabs

What is critically broken or materially missing:
1. **No 1-topic enforcement** — chats can drift across unrelated topics, creating confusion
2. **Static "Tutor Chat" header** — doesn't show the actual topic/session title
3. **Buggy topic display** — `currentConcept` sometimes null, requires refresh
4. **Title generation ignores topic binding** — title should simply be the topic name
5. **Slideover cluttered** — three separate header buttons; should be a single toggle
6. **Practice tab missing generate buttons** — flashcards/quizzes can only be generated from graph page
7. **Concept graph sizing broken** — doesn't fill slideover width
8. **Level-up quiz button in header is dead weight** — remove it
9. **Quizzes not revisitable** — no way to re-take or review past quizzes
10. **Adjacent/wildcard suggestions in chat area** — should be in sidebar
11. **No topic hierarchy awareness** — agent doesn't know umbrella→topic→subtopic chain
12. **No hierarchy display** — frontend doesn't show where current concept sits in the tree

## Non-Negotiable Constraints

1. **Small PRs** — each track should produce ≤ 400 LOC net per slice
2. **Thin routes** — no business logic in API handlers
3. **Tests required** — pytest for all new backend behavior
4. **Evidence-first** — user-visible answers must include citations or refuse in strict mode
5. **Budgets** — obey resolver + gardener budgets in docs/GRAPH.md
6. **Backward compatibility** — existing chat sessions must remain accessible (concept_id nullable for old sessions)

## Completed Work (Do Not Reopen Unless Blocked)

- Concept resolver per-turn resolution
- Deterministic title generation
- Sigma.js graph rendering
- Level-up quiz grading pipeline
- Practice flashcard stack
- Concept-switch banner

## Remaining Track IDs

- `CUX1` Chat-Topic Binding — enforce 1 topic per chat, derive title from topic
- `CUX2` Topic Hierarchy Awareness — surface hierarchy to agent and frontend
- `CUX3` Header & Navigation Refactor — clean up top bar, collapse slideover trigger
- `CUX4` Slideover & Practice UX — fix sizing, add generate buttons, quiz revisitability
- `CUX5` Suggestion Relocation — move adjacent/wildcard suggestions to sidebar

## Child Plan Map

| Track | Child Plan | Status |
|---|---|---|
| `CUX1` Chat-Topic Binding | `docs/chat_ux/01_chat_topic_binding_plan.md` | audit-passed |
| `CUX2` Topic Hierarchy Awareness | `docs/chat_ux/02_topic_hierarchy_plan.md` | audit-passed |
| `CUX3` Header & Navigation Refactor | `docs/chat_ux/03_header_nav_plan.md` | audit-passed |
| `CUX4` Slideover & Practice UX | `docs/chat_ux/04_slideover_practice_plan.md` | audit-passed |
| `CUX5` Suggestion Relocation | `docs/chat_ux/05_suggestion_relocation_plan.md` | audit-passed |

## Decision Log

1. **1 topic per chat**: A chat session is bound to exactly one concept (topic or umbrella tier). Subtopic exploration is allowed but the session's root topic is immutable after creation.
2. **Title = topic name**: `title_gen.py` output is replaced by the concept's `canonical_name`. No LLM, no word-extraction heuristics.
3. **Concept resolver scoped to subtopics**: The per-turn resolver still resolves the *active subtopic* within the session's root topic, but does NOT suggest switching to an unrelated topic. `ConceptSwitchSuggestion` becomes "start new chat" instead of "switch in place".
4. **Slideover → collapsible sidebar**: The three header buttons (Show graph, Level-up quiz, Practice) are replaced by a single hamburger/info toggle. The sidebar tabs remain.
5. **Quiz revisitability**: Past level-up and practice quizzes are shown in a list with "Retry" buttons. Retrying creates a new quiz attempt (doesn't mutate the old one).
6. **Hierarchy breadcrumb**: Frontend shows `Umbrella › Topic › Subtopic` breadcrumb in the sidebar/info panel, not in the header (to keep the header clean).
7. **Backward compatibility**: `concept_id` on `chat_sessions` is nullable — old sessions without a bound topic continue to work as before.

## Clarifications Requested (Already Answered)

1. "At most 1 topic per chat" → Interpreted as: session bound to one `topic` or `umbrella` tier concept. Subtopic exploration within that topic is allowed.
2. "Chat title shouldn't be generated" → Interpreted as: title = `concept.canonical_name` of the bound topic, set at session creation.
3. "Chats should focus on topics and umbrellas" → Interpreted as: concept resolver filters candidates to `tier IN ('topic', 'umbrella')` for session binding. Subtopics are exploration targets, not session identities.

## Deferred Follow-On Scope

- Multi-topic chat sessions (explicitly excluded by user request)
- LLM-based title generation (explicitly excluded)
- Mastery state changes from practice quizzes (per spec: practice quizzes don't mutate mastery)
- Graph gardener changes (out of scope)

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in each child plan during the run.

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

- `make test`: baseline (to be captured at kickoff)
- `cd apps/web && npm run lint`: baseline (to be captured at kickoff)
- `cd apps/web && npx tsc --noEmit`: baseline (to be captured at kickoff)

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `apps/web/app/(app)/tutor/page.tsx` | Main chat page — most changes land here |
| `apps/web/features/tutor/components/tutor-slide-over.tsx` | Slideover refactor target |
| `apps/web/hooks/use-tutor-page.ts` | State management hub for all chat UI state |
| `domain/chat/concept_resolver.py` | Concept resolution scoping changes |
| `domain/chat/title_gen.py` | Title derivation replacement |
| `adapters/db/chat.py` | Session-topic binding schema changes |
| `core/schemas/chat.py` | Schema additions for topic binding |

## Remaining Work Overview

### CUX1. Chat-Topic Binding

Every chat session must be bound to exactly one concept at creation time. The session's `concept_id` is immutable. The chat title is derived directly from the bound concept's `canonical_name` — no generation logic. The concept resolver is scoped to only resolve subtopics within the bound topic's subtree. The `ConceptSwitchSuggestion` mechanism is repurposed: instead of switching in-place, it suggests "Start a new chat about X".

**Slices:**
- **S1.1**: Add `concept_id` (FK → `concepts_canon.id`) to `chat_sessions` table + Alembic migration. Nullable for backward compatibility with existing sessions.
- **S1.2**: Update `create_chat_session()` to accept optional `concept_id`. When provided, set title = concept's `canonical_name`. Update `ChatSessionSummary` schema to include `concept_id`.
- **S1.3**: Simplify `title_gen.py` — when session has `concept_id`, title = concept name (skip all heuristics). Keep fallback for legacy sessions.
- **S1.4**: Scope concept resolver to bound topic's subtree — when session has `concept_id`, only resolve subtopics/granular nodes that are descendants of that concept.
- **S1.5**: Repurpose `ConceptSwitchSuggestion` — when resolver detects an unrelated topic, suggest "Start a new chat about X" instead of switching in-place.
- **S1.6**: Frontend — update session creation flow to pass `concept_id`, display title from `ChatSessionSummary.title`.
- **S1.7**: Fix buggy topic display — derive `currentConcept` from session's bound `concept_id` on load (not from first-turn resolution). Eliminate race condition causing intermittent display.

### CUX2. Topic Hierarchy Awareness

The agent must know the full hierarchy path (umbrella → topic → subtopic) when the user is exploring a subtopic. The `retrieval_context.py` already has `build_ancestor_context()` — this needs to be reliably included in every turn's context. The frontend must display the hierarchy breadcrumb.

**Slices:**
- **S2.1**: Ensure `build_ancestor_context()` is always called for the active concept and included in the system prompt. Currently only called for subtopic/granular tiers — extend to always provide hierarchy context.
- **S2.2**: Add `hierarchy_path` field to chat response stream metadata — list of `{concept_id, name, tier}` from root to current active concept.
- **S2.3**: Frontend — display hierarchy breadcrumb (e.g., "Machine Learning › Neural Networks › Backpropagation") in the sidebar info panel.
- **S2.4**: Agent prompt updates — inject "Current session topic: {topic}. Currently exploring: {subtopic} (under {topic} under {umbrella})" into system context.

### CUX3. Header & Navigation Refactor

The top bar shows the chat title (= topic name) instead of "Tutor Chat". The level-up quiz button is removed. The three slideover triggers collapse into a single toggle.

**Slices:**
- **S3.1**: Replace static "Tutor Chat" text with session title in header. Fall back to "New Chat" if no title set.
- **S3.2**: Remove level-up quiz button from header bar.
- **S3.3**: Replace "Show graph" and "Practice" buttons with a single hamburger/info toggle button that opens the sidebar.
- **S3.4**: Sidebar opens to last-used tab (persist in local state) or defaults to "graph" tab.

### CUX4. Slideover & Practice UX

Fix concept graph sizing, add flashcard/quiz generation buttons, and make quizzes revisitable.

**Slices:**
- **S4.1**: Fix concept graph sizing — ensure `<SigmaGraph>` fills the full width of the slideover container (remove hardcoded 320px width constraint).
- **S4.2**: Add "Generate flashcards" and "Generate quizzes" buttons to practice tab (reuse logic from graph page's existing generate buttons).
- **S4.3**: Add quiz history list to practice tab — show past quizzes with scores and "Retry" buttons. Clicking retry creates a new quiz attempt for the same concept.
- **S4.4**: Verify retry creates new attempt (doesn't mutate old quiz record). Ensure quiz history updates after retry.

### CUX5. Suggestion Relocation

Move the concept-switch banner from inline chat area to the sidebar.

**Slices:**
- **S5.1**: Remove `<ConceptSwitchBanner>` from chat timeline area.
- **S5.2**: Add suggestions section to sidebar — show active `ConceptSwitchSuggestion` as a card with "Start new chat" action (per CUX1 decision).
- **S5.3**: Restyle suggestion as sidebar card — topic name, brief reason, and action button.

## Cross-Track Execution Order

Tracks should be executed in this order. Each track's child plan defines its internal slice order.

1. `CUX1` Chat-Topic Binding — foundational; all other tracks depend on the 1-topic model
2. `CUX3` Header & Navigation Refactor — depends on CUX1 (title from topic binding)
3. `CUX2` Topic Hierarchy Awareness — depends on CUX1 (bound topic determines hierarchy root)
4. `CUX4` Slideover & Practice UX — independent of CUX1-3, can run in parallel with CUX2
5. `CUX5` Suggestion Relocation — depends on CUX3 (sidebar must exist before moving suggestions there)

Dependencies between tracks:

- `CUX3` depends on `CUX1` because the header title comes from the topic binding
- `CUX2` depends on `CUX1` because hierarchy is rooted at the bound topic
- `CUX5` depends on `CUX3` because suggestions move to the sidebar created in CUX3
- `CUX4` is independent and can run in parallel with CUX2/CUX3

## Master Status Ledger

| Track | Status | Last note |
|---|---|---|
| `CUX1` Chat-Topic Binding | ✅ done | All 7 slices complete |
| `CUX2` Topic Hierarchy Awareness | ✅ done | All 4 slices complete |
| `CUX3` Header & Navigation Refactor | ✅ done | All 4 slices complete |
| `CUX4` Slideover & Practice UX | ✅ done | All 4 slices complete |
| `CUX5` Suggestion Relocation | ✅ done | All 3 slices complete |

## Verification Block Template

For every completed slice, include this exact structure in the child plan:

```text
Verification Block - <slice-id>

Root cause
- <what made this area insufficient?>

Files changed
- <file list>

What changed
- <short description of the changes>

Commands run
- <tests / typecheck / lint commands>

Logic review
- <For each changed file: describe what the code actually does, not just
  what you intended. Trace the data flow. Confirm edge cases are handled.
  "Tests pass" is not sufficient — explain WHY the logic is correct.>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
make test
cd apps/web && npm run lint
cd apps/web && npx tsc --noEmit
```

## What Not To Do

Do not do the following during this project:

- Do not add LLM-based title generation
- Do not allow multi-topic chat sessions
- Do not mutate mastery state from practice quizzes
- Do not refactor the graph gardener
- Do not change the streaming protocol (phases/activities)
- Do not add new API routes for existing functionality — extend current ones
- Do not break existing chat session backwards compatibility

## Self-Audit Convergence Protocol

After all implementation tracks reach "done" in the Master Status Ledger, the run enters a self-audit convergence loop. The agent does NOT stop — it automatically audits its own work.

### Why This Exists

Agents working top-to-bottom through a plan commonly miss edge cases, leave subtle regressions, or make assumptions that don't hold once later slices land. **Passing tests do NOT prove correctness.** Tests only check what they were written to check — they miss logic errors, silent data drops, dead code paths, and integration mismatches. This protocol forces a fresh-eyes review that catches what tests cannot.

### Fresh-Eyes Audit Principle

**The auditor must treat every slice as if it has NOT been implemented.** Do not skim Verification Blocks or trust prior claims. Instead:

1. Read the slice requirements as if seeing them for the first time.
2. **Before looking at any code**, independently write down what should exist.
3. **Only then** open the actual code and compare.
4. For every point in your "should-exist" list, verify it truly exists and is correct.
5. **Do not trust test names.** Read test bodies and confirm meaningful assertions.

### Convergence Loop

```text
AUDIT_CYCLE = 0
MAX_AUDIT_CYCLES = 3

while AUDIT_CYCLE < MAX_AUDIT_CYCLES:
    AUDIT_CYCLE += 1
    
    1. Re-read docs/chat_ux/CUX_MASTER_PLAN.md and every child plan in order.
    2. For each completed slice, perform the FRESH-EYES AUDIT.
    3. Run the full Verification Matrix.
    4. Produce an Audit Report.
    5. If CONVERGED (0 issues): update Master Status Ledger → "✅ audit-passed".
    6. If NEEDS_REPASS: reopen affected slices, re-implement, continue.
```

### Audit Cycle Budget

- **Maximum 3 audit cycles** to prevent unbounded loops.
- If cycle 3 still finds issues, produce a final handoff report for manual review.

### Audit Workspace

(Initially empty — populated during audit cycles)

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

Use this single prompt for the implementation phase:

```text
Read docs/chat_ux/CUX_MASTER_PLAN.md.
Select the first child plan in execution order that still has incomplete slices.
Read that child plan and begin with its current incomplete slice exactly as described.

Execution loop:

1. Work on exactly one sub-slice at a time and keep the change set PR-sized.
2. Preserve all constraints in docs/chat_ux/CUX_MASTER_PLAN.md and the active child plan.
3. Run the slice verification steps before claiming completion.
4. When a slice is complete, update:
   - the active child plan with a Verification Block
   - the active child plan with any Removal Entries added during that slice
   - docs/chat_ux/CUX_MASTER_PLAN.md with the updated status ledger
5. After every 2 completed slices OR if your context is compacted/summarized, re-open docs/chat_ux/CUX_MASTER_PLAN.md and the active child plan.
6. If the active child plan still has incomplete slices, continue to the next slice.
7. If the active child plan is complete, pick the next incomplete child plan.

Stop only if:
- verification fails
- repo behavior does not match plan assumptions
- a blocker requires user input
- completing the next slice would force risky scope expansion

Do NOT stop because one child plan is complete.
The run is only complete when docs/chat_ux/CUX_MASTER_PLAN.md shows no remaining incomplete tracks.

Additional constraints:
- Routes must stay thin (no business logic)
- Tests required for all new backend behavior (pytest)
- ≤ 400 LOC net per slice
- Do not break existing chat session backwards compatibility

START:

Read docs/chat_ux/CUX_MASTER_PLAN.md.
Pick the first incomplete child plan in execution order.
Begin with the current slice in that child plan exactly as described.

--- SELF-AUDIT PHASE ---

When all tracks complete, enter the self-audit convergence loop (max 3 cycles).
The run is ONLY complete when all tracks show "audit-passed" or 3 audit cycles exhausted.
```
