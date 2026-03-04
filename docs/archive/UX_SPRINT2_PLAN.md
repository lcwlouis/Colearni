# UX Sprint 2 — Graph, Gardener, & Polish Plan (READ THIS OFTEN)

Last updated: 2026-03-02

Archive snapshots:
- `none` (new plan)

Template usage:
- This is a task-specific plan for fixing gardener bugs, graph UX, sources page, onboarding, and status animation polish.
- It does not replace `docs/REFACTOR_PLAN.md` or `docs/AGENTIC_MASTER_PLAN.md`.
- All GP1–GP8 slices from `docs/GRAPH_UX_POLISH_PLAN.md` are complete; this plan addresses a new round of feedback.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

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
7. This is a polish / fix pass. Do not mix in unrelated feature or architecture work.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

This document is the active execution plan for the second UX polish sprint, addressing feedback from manual testing on 2026-03-02.

What earlier work already landed:

- GP1–GP8: All graph UX polish slices complete (see `docs/GRAPH_UX_POLISH_PLAN.md`)
- AR0–AR7: All agentic tracks complete (see `docs/AGENTIC_MASTER_PLAN.md`)

Why this plan exists:

- Manual testing revealed a critical bug: the gardener endpoint never commits its transaction, so merges and prunes are silently lost.
- Graph UX is rated 3/10 by the user — needs significant visual improvement.
- Multiple UX improvements requested across sources page, onboarding, status animation, and graph exploration.

## Inputs Used

This plan is based on:

- `docs/GRAPH_UX_POLISH_PLAN.md` (completed polish plan)
- `docs/GRAPH.md` (graph gardener and resolver design)
- `docs/PRODUCT_SPEC.md` (product behavior expectations)
- manual testing observations from the user on 2026-03-02
- code investigation of gardener transaction flow
- current repository layout as of 2026-03-02

## Executive Summary

What is already in good shape:

- Graph force simulation, focus mode, tier filtering, search highlighting all exist
- Gardener merge logic, orphan pruner logic, tier backfill — all correctly implemented
- Onboarding landing with topic suggestions, graph browse, document upload options
- Streaming status with wavy text animation and activity rail
- Document upload, concept counts per document, sources page table

What is critically broken:

1. **Gardener transaction never commits** — `get_db_session` does not auto-commit, and the gardener route handler never calls `db.commit()`. All merges, prunes, and tier backfills are silently rolled back when the session closes. The UI shows success counts but the database is unchanged.

What is materially missing or subpar:

2. Graph UX is visually noisy — too many animation effects, selected node is not clearly highlighted, overall experience is poor (user rates 3/10)
3. Sources page upload button shows `cursor: wait` on hover because the global `button:disabled` CSS applies `cursor: wait` and something may be triggering disabled state, or the cursor rule is too broad
4. Sources page shows "X concepts" but no tier breakdown — user wants to see how many umbrella/topic/subtopic/granular nodes each document produced
5. Onboarding topic click populates the textbox and requires user to press Enter — user wants a confirm button that auto-sends
6. Streaming status messages are appended as a growing activity rail — user wants ChatGPT-style replace-mode where only the current status is shown with animation
7. Graph detail panel has no way to start a new chat for a topic or see active chats related to it

## Non-Negotiable Constraints

1. Preserve `verify_assistant_draft()` as the final answer gate.
2. Keep topic lock, concept switching, and mastery gating runtime-owned.
3. Do not auto-ingest external research.
4. Keep routes thin.
5. Preserve existing public endpoints.
6. Follow docs/GRAPH.md gardener budget rules: no unbounded loops, no full-graph scans.
7. Do not modify the tutor prompt pipeline or verifier.

## Completed Work (Do Not Reopen Unless Blocked)

- `AR0–AR7` All agentic tracks complete
- `GP1–GP8` All graph UX polish slices from Sprint 1 complete

## Remaining Slice IDs

- `UX1` Fix gardener transaction commit — add db.commit() to gardener route
- `UX2` Graph UX overhaul — reduce effects, improve selected node highlighting, cleaner visual design
- `UX3` Sources page fixes — fix upload cursor bug + add per-document tier breakdown
- `UX4` Onboarding auto-send — confirm button that auto-generates on topic click
- `UX5` Streaming status replace-mode — ChatGPT-style single-line animated status
- `UX6` Graph explore chat integration — "Start new chat" button + active chats for topics
- `UX7` LLM prompt caching — enable OpenAI cached inputs for repeated system/context prefixes
- `UX8` Dev stats toggle — user-controllable toggle for generation trace visibility in production

## Decision Log

1. The gardener route must explicitly commit the session after `run_graph_gardener()` returns. The `get_db_session` dependency yields a session with `autocommit=False` and only closes (no commit) on success. Every route that mutates data needs explicit `db.commit()`.
2. Graph selected node should use a prominent glow/ring effect (not just a blue stroke which blends with the graph).
3. Graph animations should be toned down: reduce force simulation energy, remove bouncy effects, make transitions subtle and fast.
4. The upload button cursor bug is caused by the global CSS rule `button:disabled { cursor: wait }`. Fix by ensuring the button is not accidentally disabled or by using `cursor: not-allowed` for disabled state (which is the standard UX convention).
5. Tier breakdown per document requires a backend change to return counts by tier from the documents list endpoint, or a frontend aggregation from graph data.
6. Onboarding confirm button should show a small modal/card with the suggested prompt and a "Start learning" button that immediately sends the message.
7. Streaming status should show only the latest step label with wavy animation; previous steps should be invisible (not accumulated as a rail). The phase label ("Thinking...", "Searching...") replaces itself on each status event.
8. Graph detail panel should show: (a) a "Start new chat" button if no active chat exists for that concept, and (b) a list of active chats that mention the concept with direct links.
9. Gardener reconnection (discovering missing edges between concepts from different documents/chunks) is out of scope for this sprint — it's a new feature, not a polish fix. Tracked as a future enhancement.
10. LLM prompt caching should focus on structuring messages for OpenAI's automatic prefix caching (≥1024 token prefixes are cached server-side). Move static instructions before dynamic context in all prompts. Log `cached_tokens` from response usage for observability.
11. Application-level extraction caching is optional but valuable — hash(prompt_template + chunk_text) as key, extracted JSON as value, bounded LRU with TTL. Only for deterministic calls (temperature=0).
12. Dev stats toggle should be frontend-only via localStorage, not a backend setting. The backend always includes `generation_trace` in responses (it's tiny overhead). Frontend reads `localStorage('colearni_show_dev_stats')` to decide visibility.

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in this file during the run.

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

- `pytest -q`: 922 passed (with `PYTHONPATH=.`, as of 2026-03-02)
- `npx vitest run` (from `apps/web/`): 106 passed
- `npm --prefix apps/web run typecheck`: not re-run during this planning pass

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `apps/api/routes/graph.py` | Gardener route never commits DB transaction — merges/prunes silently lost |
| `apps/api/dependencies.py` | `get_db_session` yields session with autocommit=False and only closes, never commits |
| `apps/web/components/concept-graph.tsx` | Graph UX rated 3/10 — excessive effects, unclear node selection |
| `apps/web/styles/base.css` | `button:disabled { cursor: wait }` causes spinning wheel on upload hover |
| `apps/web/features/kb/components/kb-document-table.tsx` | Shows "X concepts" but no tier breakdown |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | Onboarding click populates textbox instead of auto-sending; status appends instead of replaces |
| `apps/web/features/graph/components/graph-detail-panel.tsx` | No chat integration — no "start chat" or "active chats" for concepts |

## Remaining Work Overview

### 1. Gardener transaction commit (CRITICAL BUG)

The gardener endpoint at `POST /workspaces/{ws_id}/graph/gardener/run` calls `run_graph_gardener()` which performs merges, prunes orphans, and backfills tiers. All of this work happens within an uncommitted transaction. The `get_db_session` dependency creates a session with `autocommit=False`, and on cleanup it only calls `session.close()` — never `session.commit()`. This means every gardener run silently discards all changes.

The fix is simple: add `db.commit()` in the route handler after the gardener function returns. Additionally, audit all other graph routes that mutate data for the same bug.

### 2. Graph UX overhaul

The graph visualization has too many visual effects that create a noisy, confusing experience:
- Force simulation restarts cause jitter
- Node selection highlight (blue stroke) is too subtle — not obvious which node is selected
- Zoom transitions are too aggressive
- Overall visual design feels rough

The overhaul should:
- Add a prominent selected-node indicator (bright glow ring, larger radius, pulsing outline)
- Reduce force simulation energy (less bouncing)
- Shorten animation durations (300ms → 150ms for snappier feel)
- Tone down focus-mode dimming (0.2 → 0.35 for better readability)
- Improve edge rendering (lighter, thinner, less visual noise)
- Make the graph feel calm and stable rather than jittery and busy

### 3. Sources page fixes

Two issues:
- **Cursor bug**: Hovering over the upload document button shows a spinning wheel cursor. The global CSS `button:disabled { cursor: wait }` is too aggressive. Fix by using `cursor: not-allowed` for disabled buttons (standard convention) and ensuring the upload button is not accidentally disabled.
- **Tier breakdown**: Instead of showing "X concepts", show a tier breakdown per document. E.g., "2 topics · 5 subtopics · 8 granular" or a compact badge layout. This requires the backend documents list endpoint to return per-tier counts, or querying the graph API.

### 4. Onboarding auto-send

Currently clicking a suggested topic in the onboarding card populates the chat textbox with "Teach me about {topic}" and the user must press Enter to send. The user wants:
- Clicking a topic shows a confirm card/button with the suggested prompt
- The confirm button immediately sends the message (auto-generates)
- No need for the user to interact with the textbox at all

### 5. Streaming status replace-mode

Currently streaming status events are appended to a growing "activity rail" showing all steps with checkmarks for completed ones and wavy animation for the current one. The user wants ChatGPT-style behavior:
- Only the current status is shown (single line)
- Each new status replaces the previous one with a smooth transition
- The current status uses wavy text animation
- No accumulated list of previous steps
- The "thinking" label should show the actual current step, not generic "Thinking..."

### 6. Graph explore chat integration

When viewing a topic/umbrella concept in the graph detail panel:
- If no active chat exists for that topic, show a "Start new chat" button that creates a new chat session with the topic pre-set
- Show a list of active chats that are associated with the concept, with direct links to navigate to them
- This requires querying chat sessions by active concept

## Implementation Sequencing

Each slice should end with green tests before the next slice starts.

### UX1. Slice 1: Fix gardener transaction commit

Purpose:
- Make the gardener endpoint actually persist its changes to the database

Root problem:
- `get_db_session` yields a session with `autocommit=False` and never commits
- The gardener route handler never calls `db.commit()`
- All gardener work (merges, prunes, tier backfills) is silently rolled back

Files involved:
- `apps/api/routes/graph.py`
- Possibly other graph routes that mutate data

Implementation steps:
1. In `apps/api/routes/graph.py`, add `db.commit()` after `run_graph_gardener()` returns, before building the response.
2. Audit all other routes in `apps/api/routes/graph.py` that perform mutations (e.g., concept updates) and add `db.commit()` if missing.
3. Audit `apps/api/routes/` broadly — check that all mutation endpoints (POST, PUT, PATCH, DELETE) call `db.commit()`. Document findings.
4. Add or update a test that verifies gardener changes persist after the endpoint returns.

What stays the same:
- Gardener logic, orphan pruner logic, tier backfill — all unchanged
- Session management dependency — unchanged (explicit commit is the intended pattern)

Verification:
- `PYTHONPATH=. pytest tests/domain/test_gardener.py -q`
- `PYTHONPATH=. pytest tests/api/ -q`
- Manual check: delete a document → run gardener → refresh page → orphan nodes should be GONE
- Manual check: run gardener on dirty graph → verify merges persist after page refresh

Exit criteria:
- Gardener changes (merges, prunes, tier backfills) persist in the database after endpoint returns
- No regression in other endpoints

### UX2. Slice 2: Graph UX overhaul — reduce effects, improve node selection

Purpose:
- Make the graph visualization feel polished and usable (target: 7/10+)
- Make the selected node unmistakably obvious

Root problem:
- Too many animation effects create visual noise
- Selected node highlight is too subtle (thin blue stroke blends with graph)
- Transitions are too long and feel sluggish

Files involved:
- `apps/web/components/concept-graph.tsx`
- `apps/web/styles/` (graph-related CSS if any)

Implementation steps:
1. **Selected node highlight**: Replace the subtle blue stroke with a prominent visual:
   - Add a pulsing glow ring (CSS animation on the SVG circle with `filter: drop-shadow`)
   - Increase stroke width from 3 to 4
   - Use a bright accent color (e.g., `#3b82f6` with glow `rgba(59, 130, 246, 0.6)`)
   - Scale the selected node up slightly (1.15x transform)
   - Make the node label bold and slightly larger for the selected node
2. **Reduce force simulation energy**:
   - Lower alpha target during drag
   - Reduce initial alpha for graph settling
   - Increase velocity decay for faster stabilization (less bouncing)
3. **Shorten transitions**:
   - Zoom transitions: 500ms → 250ms
   - Focus transitions: 500ms → 300ms
   - Auto-fit transition: 600ms → 300ms
4. **Tone down focus dimming**:
   - Non-focused opacity: 0.2 → 0.3 (still visually distinct but more readable)
5. **Improve edge rendering**:
   - Make edges thinner and lighter (less visual clutter)
   - Reduce edge opacity slightly
6. **Stabilize layout**:
   - Don't restart simulation when it's already settled
   - Reduce simulation restart alpha for smoother re-layouts

What stays the same:
- Graph data fetching, API, tier filtering, search all unchanged
- Drag behavior preserved
- Zoom/pan interaction preserved

Verification:
- `npx vitest run` from `apps/web/`
- Manual check: select a node → node has prominent glow ring, immediately obvious
- Manual check: graph settles quickly without bouncing
- Manual check: transitions feel snappy not sluggish
- Manual check: overall visual impression is clean and calm

Exit criteria:
- Selected node is immediately visually obvious with glow effect
- Graph feels stable and calm, not jittery
- Transitions are fast and subtle
- User experience is significantly improved

### UX3. Slice 3: Sources page fixes — cursor + tier breakdown

Purpose:
- Fix the spinning wheel cursor on the upload button
- Show per-document tier breakdown instead of just concept count

Root problem:
- Global CSS `button:disabled { cursor: wait }` causes spinning wheel cursor
- Documents list only shows total concept count, not breakdown by tier

Files involved:
- `apps/web/styles/base.css`
- `apps/web/features/kb/components/kb-document-table.tsx`
- `core/schemas/knowledge_base.py`
- `domain/knowledge_base/service.py`
- `adapters/db/knowledge_base.py`
- `apps/web/lib/api/types.ts`

Implementation steps:
1. **Fix cursor**: In `base.css`, change `button:disabled { cursor: wait }` to `cursor: not-allowed` (standard disabled UX convention).
2. **Backend tier counts**: Update the document list query to join with `concepts_canon` and return counts per tier. Add fields to `KBDocumentSummary`: `graph_tier_counts: dict[str, int] | None` (e.g., `{"umbrella": 1, "topic": 3, "subtopic": 5, "granular": 12}`).
3. **Frontend tier display**: In `kb-document-table.tsx`, replace the "X concepts" span with compact tier badges:
   - Show each tier that has > 0 count with a small colored badge
   - E.g., `🟣2 🔵5 🟢8` with tooltips for tier names
   - Or text form: `2 topics · 5 subtopics · 8 granular`
4. **TypeScript types**: Update `KBDocumentSummary` type to include `graph_tier_counts`.

What stays the same:
- Document upload, deletion, list endpoint contract (additive change)
- Graph extraction pipeline unchanged

Verification:
- `PYTHONPATH=. pytest tests/api/ -q`
- `npx vitest run` from `apps/web/`
- Manual check: hover upload button → normal pointer cursor (not spinning wheel)
- Manual check: documents list shows tier breakdown per document

Exit criteria:
- Upload button cursor is normal pointer on hover, `not-allowed` when disabled
- Each document shows concept count broken down by tier
- No regression in document listing

### UX4. Slice 4: Onboarding auto-send — confirm button for topic selection

Purpose:
- Clicking a suggested topic immediately starts generating a response after one-click confirmation

Root problem:
- Currently clicking a topic populates the textbox with "Teach me about {topic}" requiring the user to press Enter
- This creates unnecessary friction — the user already expressed intent by clicking

Files involved:
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts` (if submit logic needs changes)
- `apps/web/styles/tutor.css`

Implementation steps:
1. When user clicks a suggested topic chip:
   - Show a brief confirmation card inline replacing the chips: "Ready to learn about **{topic}**?" with a prominent "Start learning →" button and a "← Back" link
   - The confirmation card appears where the topic chips were (not a modal)
2. When user clicks "Start learning →":
   - Programmatically submit "Teach me about {topic}" as a chat message
   - Call the same submit handler that Enter/Send button uses
   - Transition to the chat loading state immediately
3. If user clicks "← Back", return to the topic chips view.
4. Style the confirmation card to feel intentional and polished.

What stays the same:
- Topic suggestion fetching unchanged
- Chat submit logic unchanged
- Textbox remains available for free-form input

Verification:
- `npx vitest run` from `apps/web/`
- Manual check: click topic → see confirm card → click "Start learning" → chat starts generating
- Manual check: click "Back" → returns to topic chips

Exit criteria:
- One-click topic selection with confirmation auto-sends the message
- No need to interact with the textbox
- Smooth, polished transition between states

### UX5. Slice 5: Streaming status replace-mode

Purpose:
- Show only the current processing step with animation, replacing previous steps (ChatGPT-style)

Root problem:
- Status events are appended to a growing activity rail with checkmarks
- Only the last step is animated; all previous steps remain visible
- This looks cluttered and "weird" per user feedback

Files involved:
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/features/tutor/hooks/use-tutor-messages.ts`
- `apps/web/styles/tutor.css`

Implementation steps:
1. **Replace the activity rail** with a single-line status display:
   - Show typing dots + the current step label with wavy animation
   - When a new status arrives, the old label fades/slides out and the new one fades/slides in
   - Only ONE step visible at a time (no checkmarked history)
2. **Update the status state**:
   - Instead of accumulating `activitySteps` array, keep only `currentActivity: { activity: string, label: string } | null`
   - When a new status event arrives, replace `currentActivity` entirely
3. **Replace the phase label**: Instead of showing generic "Thinking..." or "Searching...", show the actual step label from the status event (e.g., "Analysing question", "Checking mastery level", "Searching knowledge base")
4. **CSS transition**: Add a smooth crossfade or slide animation when the status label changes:
   - Outgoing label: fade out (opacity 1→0, translateY 0→-8px) over 200ms
   - Incoming label: fade in (opacity 0→1, translateY 8px→0) over 200ms
5. **Keep the typing dots** as a constant visual anchor (they should always show during loading)

What stays the same:
- Status event protocol from backend unchanged
- WaveLabel component can be reused for the current step
- Chat phase tracking logic preserved
- Stream connection and event parsing unchanged

Verification:
- `npx vitest run` from `apps/web/`
- Manual check: send a message → see single-line status that replaces itself as steps progress
- Manual check: each step animates with wavy text
- Manual check: no accumulated rail of previous steps

Exit criteria:
- Only current status step shown (no activity rail accumulation)
- Smooth transition between status steps
- Wavy animation on current step
- Clean, ChatGPT-like feel

### UX6. Slice 6: Graph explore chat integration

Purpose:
- Let users start a chat from the graph detail panel and see related active chats

Root problem:
- Graph detail panel shows concept info, practice tools, and activity but has no connection to the chat/tutor system
- Users discovering a topic in the graph have no way to start learning about it without manually navigating to the tutor

Files involved:
- `apps/web/features/graph/components/graph-detail-panel.tsx`
- `apps/web/features/graph/hooks/use-graph-page.ts`
- `apps/web/lib/api/client.ts`
- `apps/web/lib/api/types.ts`
- `apps/api/routes/chat.py` (if new endpoint needed for chat-by-concept query)
- `adapters/db/chat.py` (if query needed)

Implementation steps:
1. **"Start new chat" button**: In the graph detail panel, add a "Start new chat about {concept}" button for topic/umbrella tier concepts.
   - Clicking navigates to the tutor page and pre-populates with "Teach me about {concept}"
   - Use Next.js router to navigate: `/chat?topic={concept_name}&concept_id={id}`
   - The tutor page should detect the query param and auto-submit (reuse UX4 pattern)
2. **Active chats section**: Below the concept info, show a "Related chats" section:
   - Query chat sessions where `active_concept_id` matches the selected concept
   - Show chat titles as clickable links that navigate to `/chat/{chat_id}`
   - Show "No active chats for this topic" if none exist
3. **Backend query**: Add a lightweight endpoint or query parameter to list chats by concept:
   - `GET /workspaces/{ws_id}/chat/sessions?concept_id={id}` or add `concept_id` filter to existing sessions list
4. **Style**: Keep the section compact within the detail panel scroll area.

What stays the same:
- Graph detail panel layout (additive)
- Chat session creation flow unchanged
- Practice features in detail panel unchanged

Verification:
- `PYTHONPATH=. pytest tests/api/ -q`
- `npx vitest run` from `apps/web/`
- Manual check: select topic in graph → see "Start new chat" button → click → navigates to tutor with topic
- Manual check: select topic with existing chats → see chat links → click → navigates to chat

Exit criteria:
- "Start new chat" button available for topic/umbrella concepts
- Active chats listed with direct links
- Smooth navigation between graph and tutor

### UX7. Slice 7: LLM prompt caching — enable cached inputs

Purpose:
- Reduce LLM API costs and latency by enabling prompt prefix caching for repeated system prompts and static context

Root problem:
- Every LLM call sends the full system prompt + context from scratch
- OpenAI automatically caches prompt prefixes ≥1024 tokens on their server side, but the codebase currently uses `no-cache` headers on streaming responses and does not structure messages to maximize cache hits
- System prompts, persona definitions, and instruction blocks are identical across calls for the same session — these are prime candidates for prefix caching
- No LLM response caching exists at the application level either

Files involved:
- `adapters/llm/providers.py` (LLM call wrapper)
- `domain/chat/respond.py` (chat response builder)
- `domain/chat/prompt_kit.py` (prompt assembly)
- `core/settings.py` (cache TTL settings)

Implementation steps:
1. **Structure messages for prefix caching**: OpenAI automatically caches identical prefixes ≥1024 tokens. Ensure system prompt + static instructions are always the FIRST messages and identical across calls. Do not interleave dynamic content into the system prompt prefix.
   - Move any per-turn dynamic context (evidence, conversation history) AFTER the static system prompt
   - Keep the system message deterministic: same persona + same instructions = same prefix = cache hit
2. **Track cache usage**: OpenAI returns `usage.prompt_tokens_details.cached_tokens` in responses. Log this via observability so we can monitor cache hit rates in Phoenix.
   - In `providers.py`, extract and log `cached_tokens` from the response usage object
   - Add to generation trace: `cached_input_tokens` field
3. **Application-level semantic cache** (optional, bounded):
   - Add a lightweight in-process LRU cache for graph extraction calls where the same chunk text produces identical concepts
   - Key: hash of (prompt_template + chunk_text), Value: extracted concepts JSON
   - TTL: 1 hour, max entries: 500
   - Only for deterministic extraction calls (temperature=0), NOT for chat responses
4. **Settings**: Add `APP_LLM_EXTRACTION_CACHE_ENABLED: bool = True` and `APP_LLM_EXTRACTION_CACHE_TTL_SECONDS: int = 3600` to settings.

What stays the same:
- Chat responses are never cached (non-deterministic by nature)
- LLM provider selection unchanged
- Prompt template loading (already cached via PromptRegistry)

Verification:
- `PYTHONPATH=. pytest tests/domain/ -q`
- `PYTHONPATH=. pytest tests/adapters/ -q`
- Check Phoenix traces: look for `cached_tokens` in generation trace
- Manual check: send two similar messages → observe cache hit in Phoenix traces

Exit criteria:
- System prompts structured for maximum prefix cache hits
- `cached_tokens` tracked and logged in generation traces
- Extraction calls cached at application level (configurable)

### UX8. Slice 8: Dev stats toggle — user-controllable generation trace visibility

Purpose:
- Allow users to toggle generation trace visibility in production, not just in dev builds

Root problem:
- `generation_trace` (model, token counts, latency, evidence plan stats) is always sent from the backend but only displayed when `NODE_ENV === "development"`
- No way for a user or admin to see this data in production
- No backend-side control over whether trace data is included in responses
- Users/developers want to optionally inspect LLM performance in production without rebuilding

Files involved:
- `apps/web/components/chat-response.tsx` (frontend toggle)
- `apps/web/features/sidebar/` (settings UI for toggle)
- `core/settings.py` (backend setting)
- `apps/api/routes/chat.py` (conditional trace inclusion)
- `apps/web/lib/api/types.ts` (type updates)

Implementation steps:
1. **Frontend toggle**: Add a "Show dev stats" toggle in the sidebar settings or workspace settings panel:
   - Store preference in `localStorage` (key: `colearni_show_dev_stats`)
   - Default: off in production, on in development
2. **Frontend rendering**: Replace the `process.env.NODE_ENV === "development"` check with the localStorage toggle value:
   - `const showDevStats = localStorage.getItem('colearni_show_dev_stats') === 'true'`
   - The generation trace collapsible panel shows when toggle is on
3. **Backend control** (optional): Add `APP_INCLUDE_GENERATION_TRACE: bool = True` to settings. When False, strip `generation_trace` from responses before serialization. Default True (always include — let frontend decide visibility).
4. **Enhanced trace display**: When visible, show a cleaner summary:
   - Model name + provider
   - Token breakdown: prompt / completion / cached / reasoning
   - Latency: total time, LLM time
   - Evidence sources used
   - Collapsible raw JSON for full details

What stays the same:
- Generation trace data structure unchanged
- Backend always computes traces (just optionally strips from response)
- Chat response rendering unchanged

Verification:
- `npx vitest run` from `apps/web/`
- Manual check: toggle on → see stats panel in chat response
- Manual check: toggle off → stats panel hidden

Exit criteria:
- Users can toggle dev stats visibility in any environment
- Stats panel shows clean, useful information when enabled
- Default is off in production

## Execution Order (Update After Each Run)

1. `UX1` Fix gardener transaction commit (CRITICAL BUG)
2. `UX2` Graph UX overhaul
3. `UX3` Sources page fixes
4. `UX4` Onboarding auto-send
5. `UX5` Streaming status replace-mode
6. `UX6` Graph explore chat integration
7. `UX7` LLM prompt caching
8. `UX8` Dev stats toggle

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Block Template

For every completed slice, include this exact structure in the working report or PR note:

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

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
PYTHONPATH=. pytest -q
npx vitest run  # from apps/web/
npm --prefix apps/web run typecheck
```

Slice-specific emphasis:

- `UX1`
  - `PYTHONPATH=. pytest tests/api/ -q`
  - Manual: run gardener → refresh page → verify changes persisted
- `UX2`
  - `npx vitest run` from `apps/web/`
  - Manual: click node → prominent glow ring visible
- `UX3`
  - Manual: hover upload button → normal cursor
  - Manual: documents show tier breakdown
- `UX4`
  - `npx vitest run` from `apps/web/`
  - Manual: click topic → confirm → auto-generates
- `UX5`
  - `npx vitest run` from `apps/web/`
  - Manual: send message → single-line status replaces itself
- `UX6`
  - `PYTHONPATH=. pytest tests/api/ -q`
  - Manual: graph detail → "Start new chat" → navigates to tutor
- `UX7`
  - `PYTHONPATH=. pytest tests/domain/ -q`
  - `PYTHONPATH=. pytest tests/adapters/ -q`
  - Manual: check Phoenix traces for cached_tokens
- `UX8`
  - `npx vitest run` from `apps/web/`
  - Manual: toggle on → see stats panel; toggle off → hidden

Manual smoke checklist:

1. Run Gardener → refresh → pruned nodes actually gone
2. Click graph node → obvious glow highlight, no jitter
3. Hover upload button → normal cursor
4. Sources show tier breakdown per document
5. Click onboarding topic → confirm → auto-generates
6. Streaming status replaces itself (no growing rail)
7. Graph topic detail → start new chat / see active chats
8. Phoenix traces show cached_tokens for repeated prompts
9. Dev stats toggle shows/hides generation trace panel

## What Not To Do

Do not do the following during this pass:

- do not restructure the agentic conductor or evidence planner
- do not modify the tutor prompt pipeline or verifier
- do not add new graph tiers or change the tier hierarchy
- do not add gardener edge reconnection (future feature, not polish)
- do not change the quiz creation or grading logic
- do not modify session management / dependency injection (just add commit calls where needed)

## Deferred Work (Future Sprints)

These items were considered but are out of scope for this sprint:

1. **Gardener edge reconnection**: The user wants the gardener to discover missing edges between concepts from different documents/chunks. This is a new feature requiring significant LLM prompt work and graph traversal logic. Track as a future enhancement.
2. **Auto-commit middleware**: Rather than adding `db.commit()` to each route, consider a middleware that auto-commits on 2xx responses. Deferred to avoid touching infrastructure during a polish sprint.
3. **Graph layout algorithms**: Consider switching from D3 force simulation to a deterministic layout (e.g., dagre, elk) for more stable positioning. Deferred as a larger refactor.

## Removal Ledger

Append removal entries here during implementation.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/UX_SPRINT2_PLAN.md now. This file is the source of truth.
You MUST implement slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/UX_SPRINT2_PLAN.md using the Removal Entry Template.
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

After every 2 slices OR if your context is compacted/summarized, re-open docs/UX_SPRINT2_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/UX_SPRINT2_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/UX_SPRINT2_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/UX_SPRINT2_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
