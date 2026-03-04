# CoLearni — Verification-Gated Fix Run (READ THIS OFTEN)

## Non-negotiable rules
1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 tasks
   - after any tool “memory compaction” / summarization / “I may lose context” moment
   - before claiming any task complete
2. Do not overclaim. A task is ONLY complete if:
   - code is changed
   - behavior is verified (manual steps + logs + tests)
   - acceptance criteria below are met
3. Work in SMALL PR-sized chunks:
   - one feature/bug at a time
   - commit with message `fix(run-verify): <short description>`
4. For each task, you MUST produce a “Verification Block”:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps + observed outcome
5. Keep an ordered list of outstanding tasks and follow it strictly. After each fix, update which tasks remain.

---

## Task sets

The tasks below are grouped into sets (A through F) for easier tracking.  Complete all items in order.  Do not start the next task until the current one has been fully implemented and verified.

### A) Graph page layout and UX (add-ons: search flicker + tutor reset)

**A1.** Padding between graph panel and description panel is uneven:

  *Observed:* Looks like 1 unit left padding (graph), 2 units gutter between panels, 1 unit right padding.  The spacing is visually unbalanced.

  *Fix:* Make spacing symmetric and reduce the gutter.  Use consistent gap/padding on both sides of the gutter.

**A2.** Adjacent/wildcard selection refreshes the graph every click:

  *Observed:* Selecting adjacent nodes or wildcard nodes causes the graph to fully re-mount or reset.  This is jarring and resets zoom/pan.

  *Fix:* Prevent unnecessary full graph re-mounts.  Only update relevant substate; preserve the viewport (zoom/pan) when possible.

**A3.** Highlight node filter returns an API error (`422`):

  *Observed:* Filtering nodes by highlight leads to a `422` validation error from the backend.

  *Fix:* Identify the backend validation error and the frontend payload mismatch.  Add client-side validation and correct the request shape.  If necessary, add backend handling for missing fields.  Create a reproducible curl or Postman example.

**A4.** “Clear focus” should reset to the whole graph:

  *Observed:* Clearing focus only removes the focus text but does not reset the graph dataset or viewport.

  *Fix:* Make the clear focus action restore the full graph dataset/viewport (zoom/pan).  Users should clearly return to the whole graph view.

**A5.** Right-side details panel width changes based on content:

  *Observed:* The right panel grows or shrinks depending on the length of the title/alias/description.

  *Fix:* Lock a stable split ratio between graph and details (e.g., 65/35).  Long titles/aliases/description should wrap or truncate inside the details panel instead of resizing the layout.

**A6.** Search concepts input causes graph flicker / refresh on every keystroke

  *Observed:*
  - Typing into the “Search concepts…” filter causes the graph to visibly flicker and/or reset.
  - Likely caused by re-fetching data or re-mounting the graph component on every character.

  *Fix requirements:*
  1) **Debounce input updates** (e.g., 200–400ms) so filtering does not trigger on every keystroke.
  2) **Do not re-mount the graph** on search changes:
     - Keep graph instance stable.
     - Update only highlight/filter state.
  3) Prefer **client-side filtering/highlighting** for already-loaded nodes.
     - Only hit the backend when absolutely needed (e.g., if dataset is too large).
  4) Ensure zoom/pan/viewport is preserved while searching.

  *Acceptance criteria:*
  - Typing does not flicker or reset the graph.
  - Filtering feels smooth and “professional”.
  - No unnecessary network requests per character.

  *Verification steps:*
  - Open graph page with a moderately large graph.
  - Type quickly into search: no flicker, no graph reset.
  - Confirm network tab/logs: no request per keystroke (or requests only after debounce).

**A7.** Highlight Node filter also causes flicker / refresh per input or selection

  *Observed:*
  - Using Highlight Node filter triggers flicker similar to Search concepts.
  - Often also linked to API calls and full graph re-render.

  *Fix requirements:*
  1) Apply the same **debounce + stable graph instance** approach as A6.
  2) If Highlight Node requires backend validation (A3), ensure the request is:
     - debounced
     - cancellable (ignore stale responses)
     - does not trigger full re-mount
  3) Persist viewport and focused state unless user explicitly resets.

  *Acceptance criteria:*
  - Highlight Node interaction does not cause flicker/reset.
  - Smooth UX; no full graph refresh loops.

  *Verification steps:*
  - Try highlight node repeatedly and type/select quickly.
  - Confirm no flicker and no repeated full re-renders.

### B) Sources page layout and state (add-on: status rendering correctness)

**B1.** Ingested document row alignment is off:

  *Observed:* Action buttons and badges are misaligned; row height is inconsistent; there is wasted space on the right.

  *Fix:* Re-balance the table layout.  Ensure row height, baseline alignment, and column widths are consistent.  Reduce wasted space and spread items evenly.

**B2.** Queue does not clear after ingestion completes:

  *Observed:* Upload queue entries remain visible even after ingestion finishes.  The queue only clears on full page refresh.

  *Fix:* Automatically remove an entry from the queue once ingestion completes.  Ensure the UI updates without requiring a full refresh.

**B3.** Empty sources state should be helpful:

  *Observed:* If no documents exist, the user sees a static message.  This is not very helpful.

  *Fix:* Provide a more helpful empty state.  Preferably use an LLM or a dynamic message to encourage uploading documents, or provide a friendly rich empty state.

**B4.** Sources page must reflect real ingestion/extraction status (no optimistic “Extracted”)

  *Observed:*
  - Immediately after upload, UI shows Graph=Extracted and concepts=0 even when background task crashed.
  - Description shows `-` even though extraction is in progress or failed.

  *Fix requirements:*
  - Render Graph status as:
    - `Extracting…` when `graph_status=EXTRACTING`
    - `Extracted` only when `graph_status=EXTRACTED`
    - `Failed` (with tooltip/popover error) when `graph_status=FAILED`
  - Description should show:
    - extracted summary when available
    - `Extracting…` / loading skeleton while processing
    - `-` only if description is truly empty and processing is done
  - Reprocess button must:
    - set status back to QUEUED/PROCESSING
    - trigger background pipeline again
    - update UI based on backend polling
  - Refresh button must actually re-fetch backend state and update UI.

  *Acceptance criteria:*
  - UI matches backend status truthfully across upload, processing, success, failure.
  - Reprocess visibly changes state and eventually updates concepts.
  - Refresh always updates values (no no-op).

### C) Upload and ingestion (add-on: post-ingest pipeline + status truthfulness)

**C1.** Upload POST blocks until ingestion completes:

  *Observed:* Submitting an upload freezes the frontend and backend.  The POST request is held open until the entire ingestion finishes, making the UI unresponsive.

  *Fix:* Refactor the upload flow so that the POST returns quickly (accepted/queued) and ingestion runs asynchronously in the background.  The frontend should poll or listen for status updates.  Users should be able to continue using the app while ingestion happens.

**C2.** Fix post-ingest pipeline crash: `ChunkRow` has no attribute `body`

  *Observed:*
  Backend error during post-ingest:
  `AttributeError: 'ChunkRow' object has no attribute 'body'` in `core/ingestion.py` around:
  `chunk_texts = [c.body for c in chunks_rows]`

  *Root cause hypothesis (must confirm):*
  - ORM/model changed (field renamed from `body` → `text`/`content`/`chunk_text`/`chunk`)
  - Or query returns a row type with different schema than expected.

  *Fix requirements:*
  1) Inspect the `ChunkRow` model/schema and find the correct field name.
  2) Update `run_post_ingest_tasks` to use the correct attribute.
  3) Add a unit/integration test for post-ingest tasks using a real inserted document + chunks.
  4) Ensure failures are recorded as a **document status** (not silent) and surfaced to UI.

  *Acceptance criteria:*
  - Post-ingest tasks complete without crashing.
  - Concepts are actually extracted and stored.
  - If extraction fails, document shows `FAILED` with reason.

**C3.** Source ingestion state machine (backend is source of truth)

  *Observed:*
  UI shows “Ingested” + “Extracted” immediately on upload even when extraction is impossible or failed.

  *Fix requirements:*
  Implement and persist status fields per document on backend:
  - `upload_status`: QUEUED | UPLOADING | UPLOADED | FAILED
  - `ingestion_status`: QUEUED | PROCESSING | INGESTED | FAILED
  - `graph_status`: QUEUED | EXTRACTING | EXTRACTED | FAILED
  - `error_message` / `error_code` (nullable)
  - `concept_count` (int, default 0)
  - timestamps: `created_at`, `updated_at`, `ingested_at`, `extracted_at`

  *Acceptance criteria:*
  - Backend always returns truthful current statuses.
  - UI renders based on backend statuses only.
  - Any failure persists and is visible without refresh hacks.

### D) Sidebar and navigation (add-on: collapsed bottom controls polish)

**D1.** Collapsed sidebar shows logo and expand arrow side by side:

  *Observed:* In collapsed mode, both the logo and the expand arrow are visible simultaneously, which looks cluttered.

  *Fix:* Show only the logo when collapsed, and swap it to an expand arrow on hover.  Do not display both at once.

**D2.** Collapsed sidebar workspace/profile/logout UI is broken:

  *Observed:* The collapsed sidebar has awkward placement for the workspace selector and the profile/logout button.

  *Fix:* Simplify the collapsed UI.  Use either a single circular profile button with a popup menu or two circles for workspace picker and profile/logout.  Ensure alignment, spacing, and hover states are clean.

**D3.** Sidebar collapsed state not preserved across navigation:

  *Observed:* The collapsed/expanded state is not persistent across page changes or refresh.

  *Fix:* Persist the collapsed state in application state (e.g., local storage or global state).  Restoring the collapsed state should be consistent across navigation and refresh.

**D4.** Collapsed sidebar bottom controls look broken / misaligned (see screenshot)

  *Observed:*
  - Bottom controls (workspace selector button, theme toggle, logout) look like large floating rounded boxes.
  - Spacing and alignment are inconsistent with the main icon rail.
  - Visual hierarchy is unclear and controls feel “detached” from sidebar.
  - The bottom cluster consumes too much width/height in collapsed mode.

  *Fix requirements (collapsed mode only):*
  1) **Convert bottom controls into a compact icon stack** aligned to the same centerline as the sidebar icons above.
     - Use consistent icon button size (e.g., 40px–44px square) and consistent corner radius.
     - Remove large pill containers and nested rounded boxes.
  2) **Workspace selector**
     - Represent as a single circular icon button (e.g., user/workspace glyph or initials).
     - On click: open a small popover menu with:
       - Workspace switch list
       - Actions: Rename workspace, New workspace
     - In collapsed mode, do NOT show full workspace dropdown UI.
  3) **Profile / logout**
     - Use a single icon button (e.g., user circle / door arrow).
     - On click: popover with Logout (and optional profile/settings later).
  4) **Theme toggle**
     - Use a single icon button (moon/sun) consistent size.
     - No extra container; keep it aligned and visually quiet.
  5) **Spacing**
     - Bottom stack should have consistent vertical spacing (e.g., 10–12px gap).
     - Add a subtle divider above the bottom cluster (optional).
  6) **Hover + focus states**
     - Add consistent hover background + focus ring.
     - Ensure accessible hit targets.

  *Acceptance criteria:*
  - Bottom controls in collapsed mode are visually consistent with the main icon rail.
  - No oversized floating pill boxes.
  - All bottom controls are centered and evenly spaced.
  - Workspace/profile menus are accessible via popovers, not inline dropdown UI.

  *Verification steps:*
  - Toggle sidebar collapsed/expanded and confirm:
    - Collapsed bottom controls are compact + aligned
    - Expanded mode retains richer UI without regressions
  - Test popovers open/close and do not overflow viewport
  - Refresh page: collapsed state persists (D3)

### E) Chat state and tutor behavior (add-on: tutor graph reset)

**E1.** Chat messages disappear when navigating away:

  *Observed:* If the user sends a message and then navigates to the graph or sources page, the message disappears from the chat until the page is refreshed.

  *Fix:* Persist chat messages in local state and reconcile with backend.  The chat should not lose messages when navigating to other pages.

**E2.** Missing async state indicators and reasoning traces:

  *Observed:* There is no clear indication when the system is thinking, searching, or generating reasoning.  Users cannot tell if the system is busy or idle.

  *Fix:* Introduce a consistent message lifecycle state machine.  Show “thinking,” “searching,” “streaming,” or other statuses as appropriate.  Integrate backend events (SSE/WebSocket/poll) to update the front end when the LLM is working.

**E3.** Concept switch rejection flow is awkward:

  *Observed:* The current flow says: "System: Concept switch rejected. Send your next message and the tutor will ask a clarifying question."  This requires the user to manually send another message.

  *Fix:* When a concept switch is rejected, automatically trigger a clarifying question or embed the rejection within the next LLM turn.  Do not rely on the user to re-prompt the system.

**E4.** Tutor chat graph needs a reset to return to the locked concept/topic

  *Observed:*
  - In Tutor chat, users can pan/zoom/focus to other nodes.
  - There is no quick “Reset” action to return to the original locked concept for the conversation.

  *Fix requirements:*
  1) Add a **Reset view** (or “Back to topic”) action in the tutor graph UI.
  2) Reset should:
     - re-center the graph on the **locked concept node**
     - restore default zoom/pan
     - clear transient highlights/search/focus for the tutor graph only
  3) Must not change the locked concept itself (topic remains the same).

  *Acceptance criteria:*
  - Clicking reset always returns to the locked concept view.
  - No concept switching occurs from reset.
  - Works reliably after multiple pans/zooms/highlights.

  *Verification steps:*
  - In Tutor chat, move around graph, click nodes, zoom/pan.
  - Press Reset: view returns to locked topic node and original framing.

### F) Observability, ingestion accuracy, and improved logging (add-on: backend as source of truth)
New addition: Before starting this review all the changes in A again. I noted that the changes didn't seem to fix the things I had requested. I noted that in A Graph and description changed to top and bottom instead of left and right. Please go back to left and right. 

**F1.** Improve observability to include the entire chat history:

  *Observed:* Current logging mechanisms only capture the immediate message sent to the LLM.  It is difficult to see how previous chat context influences responses.

  *Fix:* Enhance logging and observability so that each LLM request includes the full chat history (or enough context) and is captured in logs.  Consider adding a debug view that lists the assembled prompts and messages sent to the LLM.  This will allow developers to verify that the LLM is seeing all required context.

**F2.** Evaluate switching to LangChain for better LLM request logging:

  *Observed:* The current system uses custom LLM calls and lacks introspection into prompt assembly and request payloads.  Tools like LangChain provide logging hooks and debugging utilities.

  *Fix:* Investigate whether using LangChain or a similar library would simplify prompt assembly, tool usage, and logging.  Verify in the Phoenix interface (open in your browser) how requests are currently being logged.  Add suggestions on how to improve the logging of LLM requests if staying with the current implementation.  If switching to LangChain, outline the steps required.

**F3.** Uploaded sources appear instantly ingested but are never processed:

  *Observed:* The front end shows a new document as “ingested” immediately after upload, but no concepts are extracted even after a long wait.  This indicates that ingestion is not actually happening or the ingestion state is incorrectly displayed.

  *Fix:* Thoroughly debug the ingestion pipeline.  Ensure the backend processes uploaded documents asynchronously after the POST returns.  Update the front end to show realistic ingestion status (queued, processing, failed, ingested) instead of marking it complete instantly.  Confirm that extracted concepts appear once ingestion finishes.

**F4.** Add robust backend logging for ingestion and LLM processes:

  *Observed:* There is minimal logging on the backend, making it hard to know what is happening during upload, ingestion, retrieval, or LLM calls.

  *Fix:* Introduce structured logging throughout the backend services, including: upload acceptance, ingestion queueing, ingestion start/completion, concept extraction success/failure, LLM invocation (with prompt and context), and tool usage.  Provide log levels (info, debug, error) and ensure logs are accessible for debugging.  This will greatly aid in diagnosing issues and monitoring the system.

**F5.** Frontend state must reconcile with backend (documents + jobs + chat)

  *Observed:*
  Frontend seems to hold state that drifts from backend reality (e.g., extracted/ingested badges, queues).

  *Fix requirements:*
  - For documents: FE should poll `/documents` (or `/documents/{id}`) and render status from backend.
  - Backend must store per-user/workspace document list and return complete set every fetch.
  - Any “job queue” should be persisted on backend (job table) or derivable from document statuses.

  *Acceptance criteria:*
  - After refresh, UI remains consistent (no phantom jobs, no missing docs).
  - All documents for the current user/workspace appear reliably.
---

## Add-on: Post-fix refactor audit (no functional changes)

After completing **all tasks A–F** above (and only after they are verified), do a **non-functional refactor pass** focused on maintainability.

### G) Refactor and maintainability (NO behavior change)
**G0.** Create `docs/REFACTOR.md`
- Purpose: record refactor findings + plan.
- This file must be created/updated as the agent works through the refactor audit.

**G1.** Codebase audit (read-only first)
- Identify files that are too large / hard to maintain (examples: `global.css` ~2.2k lines, oversized components, large route handlers, huge “utils” modules).
- For each large file:
  - explain why it grew (duplication? mixed concerns? missing componentization?)
  - propose a safe split strategy (folders, naming, ownership boundaries)
  - list quick wins vs deeper changes

**G2.** Refactor plan (preserve functionality)
- Define a step-by-step plan with small PR-sized refactors.
- Each step must include:
  - files involved
  - what moves where (exact modules/classes/components)
  - what stays the same (public interfaces, APIs, CSS classnames)
  - safety checks (tests, visual checks)

**G3.** CSS strategy proposal (critical)
For CSS (especially `global.css`):
- propose how to reduce bloat without changing styles:
  - split by domain (sidebar, graph, chat, sources, shared tokens)
  - consolidate duplicates
  - extract reusable utility classes if appropriate
  - consider adopting a stricter convention (CSS modules, Tailwind utilities, component-scoped styles, or layered CSS)
- include a migration plan that does not break UI

**G4.** Mobile readiness audit (do not implement yet)
- Produce a checklist of what must change to support mobile properly:
  - responsive layout breakpoints
  - sidebar behavior
  - graph panel layout
  - chat layout constraints
  - tables (Sources) responsiveness
- Do NOT implement mobile changes in this run—just document.

### G Acceptance criteria
- `docs/REFACTOR.md` exists and contains:
  1) oversized file inventory (top 10 worst offenders)
  2) proposed module/component/CSS splits
  3) a refactor roadmap (small steps, no behavior change)
  4) a mobile-readiness checklist

### G Verification requirements
Even though this is “no functional change”:
- run tests/build/lint
- confirm no behavior changes intended
- commit message: `chore(refactor-plan): document refactor roadmap` (for docs-only changes)

---

## Execution order (update after each run)

Start with the highest priority tasks and work sequentially. After finishing a task, cross it off and proceed to the next. The recommended order is:

1. **C1** (Upload and ingestion asynchronous refactor)

2. **C2 + C3 + B4** (Fix post-ingest crash `ChunkRow.body` + implement backend ingestion/graph status machine + make Sources UI reflect real states: Extracting/Extracted/Failed, concepts count, error display, reprocess + refresh actually update)

3. **E1/E2** (Chat state persistence and async status indicators)

4. **A3/A2/A1/A5/A4 + A6 + A7** (Graph page: 422 validation error, refresh behavior, layout spacing, panel width, reset view, search flicker debounce, highlight flicker debounce)

5. **D1/D2/D3**

6. **D4** (Collapsed bottom controls polish) + re-verify **D1–D3** together  
   *(You are currently here.)*

7. **B1** (Sources row alignment) and **B3** (Helpful empty state)

8. **E3 + E4** (Concept switch rejection flow, Tutor graph reset-to-locked-topic)

9. **F1** through **F5** (Observability + ingestion accuracy debugging + logging, LangChain evaluation, FE↔BE state reconciliation)

10. Revisit from excecution 1 to 9 to make sure the fixes are in place, document this in a docs/CUR_SESSION_REPORTING.md, once complete move on to no.11

11. **G0–G4** (Create `docs/REFACTOR.md` + refactor audit/roadmap — NO functional changes)

Notes:
- **Refactor (G)** is intentionally last, only after all functional/UI fixes are verified.
- If any item is discovered to depend on another, document the dependency explicitly and continue in this order unless truly blocked.
- C2/C3/B4 must happen before “polish” work because without it, Sources/Graph state and debugging are untrustworthy.

---

## Verification checklist (for each task)

For every task you complete, include the following in your verification block:

1. **Root cause** — what caused the issue?
2. **Files changed** — list the files you modified.
3. **What changed** — describe your changes in a few sentences.
4. **Commands run** — mention any build/test commands or server runs.
5. **Manual verification steps** — explain exactly what you did in the UI or API to verify the fix.
6. **Observed outcome** — describe what you saw (e.g., logs, UI changes, absence of errors).

Use this information to prove that the task is fully complete.  If the task is only partially complete, explain what remains.

