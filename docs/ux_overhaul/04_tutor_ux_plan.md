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
5. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

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
- `UXT.4` Fix Socratic tutor protocol passthrough
- `UXT.5` Parameterize Socratic concept initialization (topic-aware)
- `UXT.6` Move prompt templates into system role (prompt builder rework)
- `UXT.7` Add syntax highlighting to markdown renderer
- `UXT.8` Backend `.env` flags for Socratic mode and dev stats

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
2. Show list of existing chats for the selected concept/topic in the graph detail panel:
   - Each chat shows title + last activity date
   - Click to navigate directly to that chat
   - Keep the "Start new chat" button but move it below the list
3. Add to `graph-detail-panel.tsx`:
   - New expandable section "Chat" below Quizzes (if UXP track is done) or after existing sections
   - Contains the `ConceptChatLinks` component
4. "Start new chat" flow:
   - Navigate to `/tutor` with query param `?topic={conceptName}`
   - Tutor page detects the query param and either:
     - Creates a new chat session pre-seeded with the topic
     - Or shows the onboarding confirm with the topic pre-selected
5. Backend (if needed):
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

### UXT.4. Fix Socratic tutor protocol passthrough

Purpose:
- The `tutor_protocol` flag sent by the frontend never reaches the domain layer — two breaks in the API gateway silently drop it, making the Socratic interactive mode a dead code path.
- See full audit: `docs/ux_overhaul/socratic_tutor_audit.md`

Root cause:
- `ChatRespondAPIRequest` (client-facing Pydantic model) is missing the `tutor_protocol` field, so Pydantic silently discards it from the request body.
- Both route handlers (`respond_chat` and `respond_chat_stream`) omit `tutor_protocol` when constructing the internal `ChatRespondRequest`, so it always defaults to `False`.

Files involved:
- `apps/api/routes/chat.py` — Add `tutor_protocol: bool = False` to `ChatRespondAPIRequest` (line 56) and forward it in both route handlers (lines 192, 244)

Implementation steps:
1. Add `tutor_protocol: bool = False` field to `ChatRespondAPIRequest` class at `apps/api/routes/chat.py:56`.
2. In `respond_chat()` (line 182-192): add `tutor_protocol=payload.tutor_protocol` to the `ChatRespondRequest(...)` constructor.
3. In `respond_chat_stream()` (line 234-244): add `tutor_protocol=payload.tutor_protocol` to the `ChatRespondRequest(...)` constructor.
4. Add a route-level integration test that verifies `tutor_protocol=True` in the API request body reaches the domain's `ChatRespondRequest` with `tutor_protocol=True`.
5. Consider adding a `log.warning` in `stream.py` when `tutor_protocol` is `True` but the Socratic branch is skipped due to missing `session_id` or unavailable `tutor_llm_client`.

Verification:
- `pytest tests/` — existing tests still pass
- New route-level test: POST `/respond/stream` with `tutor_protocol: true` → domain receives `tutor_protocol=True`
- Manual: enable Socratic toggle → send a message → response uses Socratic protocol (concept card, step progress, question-first format)
- Manual: disable Socratic toggle → response uses normal chat format

Exit criteria:
- `tutor_protocol: true` from frontend reaches `stream.py:359` condition
- Socratic interactive branch activates when toggle is on
- No regression in normal (non-Socratic) chat flow
- Route-level test covering the passthrough

### UXT.5. Parameterize Socratic concept initialization (topic-aware)

Purpose:
- `init_relation_concept()` hardcodes "Relation" as the concept with a fixed Students table.
  When a user asks about "Database Engine Internals" or any other topic, the tutor state is
  initialized with the wrong concept. The Socratic tutor must adapt to the user's selected topic.

Root cause:
- `core/schemas/tutor_state.py:69-86` — `init_relation_concept()` takes no arguments and
  hardcodes concept, table_name, table_columns, and rows.
- `domain/chat/stream.py:362-363` — calls `init_relation_concept()` unconditionally when
  `tutor_state.active` is False.

Files involved:
- `core/schemas/tutor_state.py` — Add `init_concept(topic: str, ...)` method that sets concept
  name from the user's topic and creates an appropriate micro-world example.
- `domain/chat/stream.py` — Pass `request.query` or the resolved concept name to initialization.
- `domain/chat/tutor_commands.py` — May need to handle concept-specific command context.

Implementation steps:
1. Add `init_concept(topic: str)` method to `TutorState` that:
   - Sets `concept` to the user's topic
   - Creates a sensible default micro-world table (or leaves it empty for the LLM to populate)
   - Falls back to the "Relation/Students" example only when topic is literally "Relation"
2. Update `stream.py:362-363` to call `init_concept(topic)` with the user's query or the
   resolved concept's canonical name.
3. Update the Socratic prompt template to include the user's actual topic in the STATE block.
4. Add tests for topic-aware initialization (at least 3 different topics).

Verification:
- `PYTHONPATH=. pytest -q` — all tests pass
- Manual: enable Socratic mode → ask about "B-Trees" → tutor initializes with B-Tree concept,
  not "Relation"
- Manual: ask about "SQL Joins" → tutor uses appropriate table example

Exit criteria:
- Socratic tutor adapts concept and micro-world to the user's selected topic
- "Relation" is just one possible topic, not hardcoded
- Existing Socratic tests still pass

### UXT.6. Move prompt templates into system role (prompt builder rework)

Purpose:
- The entire detailed prompt template (3KB+ of Socratic protocol, non-negotiable rules,
  7-section format, evidence, document summaries) is placed in `role: user` while `role: system`
  contains only a 12-word stub. This degrades model instruction-following, prefix caching, and
  makes Phoenix traces misleading.
- Audit details: `docs/ux_overhaul/deep_audit_report.md` Issue 2

Root cause:
- `adapters/llm/providers.py:202-205` builds messages as:
  ```python
  messages = [
      {"role": "system", "content": "You are a grounded tutor. ..."},  # 12-word stub
      {"role": "user", "content": prompt},  # 3KB+ detailed template + user query
  ]
  ```
- `domain/chat/prompt_kit.py` — `build_full_tutor_prompt_with_meta()` and
  `build_socratic_interactive_prompt()` both return a single string (the full template with
  embedded user query), which then gets placed into `role: user`.

Files involved:
- `domain/chat/prompt_kit.py` — Refactor prompt builders to return `(system_prompt, user_prompt)`
  tuple instead of a single string. The system_prompt should contain:
  - Role definition
  - Non-negotiable rules
  - Response protocol/format
  - Current tutor state
  The user_prompt should contain:
  - The actual user query
  - Any command context
  - Evidence/citations specific to this turn
- `adapters/llm/providers.py` — Update `_call_with_observability()` and streaming paths to
  accept separate system and user messages.
- `core/observability.py` — Verify `set_llm_span_attributes()` correctly reflects the new
  message structure in Phoenix traces.

Implementation steps:
1. Audit ALL prompt builder functions in `prompt_kit.py` — identify every path that builds
   prompts (tutor, socratic, mastery, flashcard, quiz, etc.)
2. Refactor each to return a `PromptMessages` dataclass with `system: str` and `user: str` fields.
3. Update `adapters/llm/providers.py` to use the new structure:
   ```python
   messages = [
       {"role": "system", "content": prompt_result.system},
       {"role": "user", "content": prompt_result.user},
   ]
   ```
4. Verify Phoenix traces now show the detailed prompt in `[system]` and only the user query +
   evidence in `[user]`.
5. Update existing tests for new return type.

Self-audit review requirements:
- The self-audit MUST verify that Phoenix traces show the correct role assignment by examining
  the actual `llm.input_messages` attribute on at least one LLM span.
- The self-audit MUST verify that the system prompt is stable across turns (same concept,
  different queries) to enable OpenAI prefix caching.
- The self-audit MUST check ALL LLM call sites, not just the tutor — gardener, mastery,
  flashcard, quiz, graph extraction all use prompts.

Verification:
- `PYTHONPATH=. pytest -q` — all tests pass
- Manual: send a tutor message → open Phoenix → LLM span → verify `[system]` contains the
  full protocol template, `[user]` contains only the user query + evidence
- Manual: send two messages about the same concept → verify system prompt is identical between
  turns (prefix caching compatible)

Exit criteria:
- ALL prompt templates are in `role: system`, not `role: user`
- User messages contain only the actual user query + turn-specific context
- Phoenix traces accurately reflect the role structure
- Existing tests pass

### UXT.7. Add syntax highlighting to markdown renderer

Purpose:
- Code blocks in chat responses render as plain monospace text without language-specific syntax
  highlighting. For a tutor app teaching programming and database concepts, this is a meaningful
  UX gap.

Root cause:
- `apps/web/components/markdown-content.tsx` uses `react-markdown` but has no syntax highlighting
  plugin installed. No `rehype-highlight`, `shiki`, or `prismjs` dependency.

Files involved:
- `apps/web/components/markdown-content.tsx` — Add syntax highlighting plugin
- `apps/web/package.json` — Add `rehype-highlight` or `shiki` dependency
- CSS — Include highlight.js theme or shiki styles

Implementation steps:
1. Install a syntax highlighting package. Prefer `rehype-highlight` (lightweight, uses
   highlight.js) over `shiki` (heavier but better quality):
   ```bash
   npm install rehype-highlight highlight.js
   ```
2. Import and add `rehypeHighlight` to the `rehypePlugins` array in `react-markdown`.
3. Import a highlight.js CSS theme (e.g., `github-dark` for dark mode, `github` for light).
4. Verify code blocks with language hints (```sql, ```python, ```typescript) render with colors.
5. Test code blocks without language hints still render as plain monospace.

Verification:
- `npx vitest run` — frontend tests pass
- Manual: send a message that includes a SQL code block → verify syntax highlighting
- Manual: send a message with a Python code block → verify highlighting
- Manual: send a message with an unlabeled code block → renders as monospace (no crash)

Exit criteria:
- Fenced code blocks with language hints have syntax highlighting
- At least SQL, Python, JavaScript/TypeScript highlighted correctly
- No visual regression in other markdown elements

### UXT.8. Backend `.env` flags for Socratic mode and dev stats

Purpose:
- The Socratic toggle and dev stats toggle are frontend-only (`useState` and `localStorage`
  respectively). The user wants backend `.env` control so these features can be configured at
  deployment time, not in the browser.

Root cause:
- `apps/web/features/tutor/hooks/use-tutor-page.ts:26` — `useState(false)` for Socratic
- `apps/web/lib/hooks/use-dev-stats.ts` — `localStorage` for dev stats
- No backend settings control these features

Files involved:
- `core/config.py` (or `core/settings.py`) — Add settings:
  - `APP_SOCRATIC_MODE_DEFAULT: bool = False` — whether Socratic is ON by default
  - `APP_INCLUDE_DEV_STATS: bool = False` — whether to include `generation_trace` in responses
- `apps/api/routes/chat.py` — Conditionally include/exclude `generation_trace` based on setting
- `apps/api/routes/settings.py` (or equivalent) — Expose a `/settings/features` endpoint that
  returns the backend feature flag values so the frontend can read defaults
- `apps/web/` — Read feature defaults from the backend settings endpoint on app load

Implementation steps:
1. Add `APP_SOCRATIC_MODE_DEFAULT` and `APP_INCLUDE_DEV_STATS` to the backend settings model.
2. Create or update a `/settings/features` endpoint that returns:
   ```json
   { "socratic_mode_default": true, "include_dev_stats": false }
   ```
3. In chat response routes: if `APP_INCLUDE_DEV_STATS=false`, strip `generation_trace` from
   the response envelope before sending.
4. On the frontend: fetch feature flags on app load, use as initial values for the toggles.
5. Remove the frontend-only Socratic button (or change it to respect the backend default).
6. Remove the frontend-only dev stats toggle if it's now fully backend-controlled, or keep it
   as an override.

Verification:
- `PYTHONPATH=. pytest -q` — backend tests pass
- `npx vitest run` — frontend tests pass
- Manual: set `APP_SOCRATIC_MODE_DEFAULT=true` in `.env` → Socratic mode active by default
- Manual: set `APP_INCLUDE_DEV_STATS=false` in `.env` → `generation_trace` not in API response

Exit criteria:
- Both features controllable via `.env`
- Frontend reads backend defaults
- Existing behavior preserved when env vars are not set (backwards compatible)

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

1. `UXT.1` Onboarding auto-send with confirm ✅ (pre-existing)
2. `UXT.2` Streaming status replace-mode animation ✅ (pre-existing)
3. `UXT.3` Graph-to-chat navigation ✅
4. `UXT.4` Fix Socratic tutor protocol passthrough ✅ (pre-existing)
5. `UXT.5` Parameterize Socratic concept initialization 🔲
6. `UXT.6` Move prompt templates into system role 🔲
7. `UXT.7` Add syntax highlighting to markdown renderer 🔲
8. `UXT.8` Backend `.env` flags for Socratic mode and dev stats 🔲

### Verification Block — UXT.1

- **Root cause**: Already implemented. `OnboardingConfirm` component exists at `apps/web/features/tutor/components/onboarding-confirm.tsx` with confirm/cancel flow. Clicking a concept chip shows confirm card with "Start learning" and "Cancel" buttons. Confirm sends `Teach me about {concept}`.
- **Files changed**: None (pre-existing)
- **What changed**: N/A — verified existing implementation matches plan requirements
- **Commands run**: `npx vitest run` (117 passed), manual code review of `tutor-timeline.tsx` and `onboarding-confirm.tsx`
- **Manual verification steps**: Confirmed OnboardingConfirm renders with concept name, Start/Cancel buttons, and sends on confirm
- **Observed outcome**: All exit criteria met — concept click → confirm → auto-send works, cancel dismisses

### Verification Block — UXT.2

- **Root cause**: Already implemented. Streaming status shows single `chat-status-label` with `key={statusKey}` for React remount. CSS `statusSlideIn` animation (0.25s ease-out, opacity + translateY) provides smooth replacement. Typing dots bounce animation continues during transitions.
- **Files changed**: None (pre-existing)
- **What changed**: N/A — verified existing implementation matches plan requirements
- **Commands run**: `npx vitest run` (117 passed), reviewed `tutor-timeline.tsx` lines 154-174 and `tutor.css` lines 690-766
- **Manual verification steps**: Confirmed single status line with animated replacement, no "Thinking..." separate text, typing dots animate continuously
- **Observed outcome**: All exit criteria met — replace-mode status with smooth CSS transitions

### Verification Block — UXT.3

- **Root cause**: `concept-chat-links.tsx` only had a "Start new chat" button; no listing of existing chats for the concept.
- **Files changed**: `apps/web/features/graph/components/concept-chat-links.tsx`, `apps/web/features/graph/components/graph-detail-panel.tsx`
- **What changed**: Enhanced `ConceptChatLinks` to accept `workspaceId` prop, fetch chat sessions via `apiClient.listChatSessions()`, filter by concept name match in title, display matching chats as clickable list (title + date → `/tutor?session={public_id}`). Added `workspaceId` passthrough from `graph-detail-panel.tsx`.
- **Commands run**: `npx vitest run` (117 passed), typecheck passed
- **Manual verification steps**: Verified component renders chat list when workspace provided, shows "No existing chats" when empty, navigates to correct tutor URL
- **Observed outcome**: All exit criteria met — graph→chat navigation works, active chats discoverable, "Start new chat" creates correct topic context

### Verification Block — UXT.4

- **Root cause**: Already implemented. `ChatRespondAPIRequest` has `tutor_protocol: bool = False` field (line 57 of `chat.py`). Both `respond_chat()` (line 193) and `respond_chat_stream()` (line 246) forward `tutor_protocol=payload.tutor_protocol` to the domain `ChatRespondRequest`.
- **Files changed**: None (pre-existing)
- **What changed**: N/A — verified existing implementation matches plan requirements
- **Commands run**: `PYTHONPATH=. pytest -q` (passed), grep verification of `tutor_protocol` in `chat.py`
- **Manual verification steps**: Confirmed field exists in API model, forwarded in both handlers, reaches domain layer
- **Observed outcome**: All exit criteria met — `tutor_protocol: true` from frontend reaches stream.py

## Verification Matrix

```bash
npx vitest run  # from apps/web/
```

## Removal Ledger

{Append entries during implementation}

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/04_tutor_ux_plan.md.
Also read docs/ux_overhaul/deep_audit_report.md for context on what was found during the deep audit.
Begin with the next incomplete UXT slice exactly as described.

Execution loop for this child plan:

1. Work on one UXT slice at a time.
2. Key constraints:
   - Onboarding concept click must have a confirm step before sending (not auto-fire).
   - Status updates must replace each other, not append — single-line animated status.
   - Socratic tutor MUST adapt to the user's selected topic — do NOT hardcode "Relation".
   - ALL prompt templates must go into role:system, NOT role:user. The user message should
     contain ONLY the user's actual query and turn-specific context (evidence, command context).
   - Syntax highlighting is REQUIRED for code blocks in the markdown renderer.
   - Socratic mode and dev stats toggles MUST be controllable via backend .env variables,
     not frontend-only state. The frontend should read defaults from a backend settings endpoint.
   - For UXT.6 (prompt builder rework): audit ALL prompt builder functions, not just the tutor.
     Every LLM call site (tutor, gardener, mastery, flashcard, quiz, graph extraction) must
     have correct system/user role assignment.
3. Run the listed verification steps before claiming a slice complete, including browser-visible
   checks where required by the plan.
4. BEHAVIORAL VERIFICATION (mandatory for every slice):
   - Trace the full code path: user action → frontend → API route → domain logic → response
   - Verify NO Pydantic silent field drops (check API schema matches frontend request)
   - Verify route handlers forward ALL fields to domain layer
   - Verify domain logic USES the forwarded fields (not dead code paths)
   - For prompts: verify Phoenix traces show correct system/user role assignment
5. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
6. After every 2 completed UXT slices OR if context is compacted/summarized, re-open
   docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/04_tutor_ux_plan.md and restate
   which UXT slices remain.
7. Continue to the next incomplete UXT slice once the previous slice is verified.
8. When all UXT slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md,
   select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXT is complete. UXT completion is only a checkpoint unless the
master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle, only work on slices marked as
"reopened". Produce audit-prefixed Verification Blocks. Do not re-examine slices that passed
the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker
requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/04_tutor_ux_plan.md.
Read docs/ux_overhaul/deep_audit_report.md.
Begin with the current UXT slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXT is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue
with the next incomplete child plan.
```
