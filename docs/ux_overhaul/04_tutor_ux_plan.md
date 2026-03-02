# CoLearni UX Overhaul — Tutor & Chat UX Plan

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

## Purpose

Improve the tutor chat experience: onboarding concept selection, streaming status display, and graph-to-chat navigation. These are interaction polish items that collectively make the chat feel responsive and connected to the knowledge graph.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- User requirements (verbatim)
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/features/tutor/components/chat-response.tsx`
- `apps/web/features/graph/components/graph-detail-panel.tsx`

## Executive Summary

What exists:
- Onboarding slide with concept chips — clicking puts text in input box, user must press Send
- Streaming status: appends new status strings, only animates the latest one (previous ones become static)
- "Thinking..." tag with static `...` followed by current status
- No way to start a chat about a topic from the graph

What this track changes:
1. **Onboarding concept click** → auto-sends with a confirm step (not just text in box)
2. **Streaming status** → replace-mode like ChatGPT reasoning: shows current status with animation, replaces previous
3. **"Thinking" tag** → shows animated current status (not "Thinking..." then status separately)
4. **Graph → Chat navigation** → "Start a chat about this topic" button in graph detail panel + show active chats for that topic

## Non-Negotiable Constraints

1. Confirm button before auto-sending — user should be able to cancel
2. Streaming status must still be visible — just replace-mode, not hidden
3. Graph detail panel must not become cluttered — chat links should be in an expandable section
4. Active chat links must deep-link to the correct chat

## Completed Work

- Onboarding concept chips render correctly
- Streaming status is received from backend
- Chat list exists in sidebar

## Remaining Slice IDs

- `UXT.1` Onboarding auto-send with confirm
- `UXT.2` Streaming status replace-mode animation
- `UXT.3` Graph-to-chat navigation

## Decision Log

1. Onboarding confirm flow: click concept → show a small confirm dialog/card with the auto-generated prompt text + "Start learning" and "Cancel" buttons. Confirm → send. Cancel → dismiss.
2. Status replace-mode: display a single line for status, replace text with smooth crossfade/slide animation as new statuses arrive. All statuses should be animated (not just the latest).
3. "Thinking..." tag should display the CURRENT status string inside it with animation, NOT as a separate element. E.g., `🔄 Analysing question...` → `🔄 Checking mastery level...` (same element, text replaces).
4. Graph → Chat: show "Start a new chat about {topic}" button at the bottom of the concept detail panel. Also show a list of active chats that mention this concept.
5. Active chats: query chats where the topic or concept was discussed (may need a backend association or keyword match).

## Current Verification Status

- `npx vitest run`: 106 passed

Hotspots:

| File | Role |
|---|---|
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Onboarding slide with concept chips |
| `apps/web/features/tutor/components/chat-response.tsx` | Streaming status display |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | Graph detail panel — add chat navigation |
| `apps/web/styles/tutor.css` | Tutor styling |

## Implementation Sequencing

### UXT.1. Onboarding auto-send with confirm

Purpose:
- Clicking a concept on the onboarding slide should present a confirm step, then auto-send the prompt

Files involved:
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/features/tutor/components/onboarding-confirm.tsx` (new)
- `apps/web/styles/tutor.css`

Implementation steps:
1. Create `onboarding-confirm.tsx`:
   - A small card/modal that appears when a concept chip is clicked
   - Shows the auto-generated prompt (e.g., "Teach me about {concept}")
   - Two buttons: "Start learning" (primary) and "Cancel" (secondary)
   - "Start learning" → calls the send handler with the prompt → dismisses the card
   - "Cancel" → dismisses the card
2. In `tutor-timeline.tsx`:
   - On concept chip click: instead of putting text in the input box, show the confirm card
   - Remove the old behavior that just populates the input
3. Style the confirm card to match the existing UI.

Verification:
- `npx vitest run`
- Manual: click a concept → confirm card appears
- Manual: click "Start learning" → prompt sends and response streams
- Manual: click "Cancel" → card dismisses, nothing sent

Exit criteria:
- Concept click → confirm → auto-send (3-click reduction)
- User can cancel before sending
- Confirm card is styled appropriately

### UXT.2. Streaming status replace-mode animation

Purpose:
- Status updates during response generation should replace each other smoothly, not append

Files involved:
- `apps/web/features/tutor/components/chat-response.tsx`
- `apps/web/styles/tutor.css`

Implementation steps:
1. In `chat-response.tsx`:
   - Instead of appending status strings to a list, keep only the CURRENT status
   - Display the current status inside the "thinking" tag: `🔄 {currentStatus}...`
   - When a new status arrives, animate a crossfade/slide transition to the new text
   - Do NOT show "Thinking..." as a separate static text — the status IS the thinking display
2. CSS animation:
   - Use a CSS transition (opacity fade or translateY slide) on status text change
   - The animated ellipsis (`...`) should continue during the transition
3. Keep the status visible until the actual response content starts streaming.
4. Once response content appears, the status/thinking tag should smoothly disappear.

Verification:
- `npx vitest run`
- Manual: ask a question → see statuses replacing each other smoothly
- Manual: each status is animated (not just the last one)
- Manual: "Thinking..." is gone — status text replaces it entirely
- Manual: status disappears when response content starts

Exit criteria:
- Only one status visible at a time
- Smooth transition between statuses
- No "Thinking..." separate from status
- Animated ellipsis continues during transitions

### UXT.3. Graph-to-chat navigation

Purpose:
- From the graph detail panel, users should be able to start a new chat about a topic or jump to existing related chats

Files involved:
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/features/graph/components/concept-chat-links.tsx` (new)
- Backend: may need a query to find chats related to a concept

Implementation steps:
1. Create `concept-chat-links.tsx`:
   - "Start a new chat" button → navigates to tutor with pre-filled topic prompt
   - List of active chats that involve this concept/topic:
     - Fetch chats where the concept was discussed (keyword match on concept name in chat messages, or a backend concept-chat association)
     - Show chat title/preview with a direct link
   - If no active chats: show only the "Start new chat" button
2. Add to `graph-detail-panel.tsx`:
   - New expandable section "Chat" below Quizzes (if UXP track is done) or after existing sections
   - Contains the `ConceptChatLinks` component
3. "Start new chat" flow:
   - Navigate to `/tutor` with query param `?topic={conceptName}`
   - Tutor page detects the query param and either:
     - Creates a new chat session pre-seeded with the topic
     - Or shows the onboarding confirm with the topic pre-selected
4. Backend (if needed):
   - Add an endpoint or query param to list chats that reference a given concept
   - Alternative: do a client-side filter on existing chat list by title/topic match

Verification:
- `npx vitest run`
- Manual: select concept in graph → "Chat" section shows "Start new chat" button
- Manual: click "Start new chat" → navigates to tutor with topic pre-filled
- Manual: concept with existing chats → shows chat list with links
- Manual: click chat link → navigates to that chat

Exit criteria:
- Graph → Chat navigation works
- Active chats are discoverable from concept view
- "Start new chat" creates a chat with the right topic context

## Execution Order (Update After Each Run)

1. `UXT.1` Onboarding auto-send with confirm
2. `UXT.2` Streaming status replace-mode animation
3. `UXT.3` Graph-to-chat navigation

## Verification Matrix

```bash
npx vitest run  # from apps/web/
```

## Removal Ledger

{Append entries during implementation}

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/ux_overhaul/04_tutor_ux_plan.md now. This is the active child plan.
Also read the master plan at docs/UX_OVERHAUL_MASTER_PLAN.md for cross-track context.

You MUST implement slices in the EXACT execution order listed in this child plan.
You MUST NOT claim a slice is complete until you produce a Verification Block.

Key constraints:
- Onboarding concept click must have a confirm step (not auto-fire)
- Status updates must replace each other, not append
- "Thinking..." tag should show current status, not be separate

After every 2 slices, re-open this child plan and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.

START:

Read docs/ux_overhaul/04_tutor_ux_plan.md.
Begin with UXT.1 (onboarding auto-send with confirm).
Do not proceed beyond the current slice until verified.
```
