# Colearni Refinement — Master Plan

Last updated: 2026-03-04

Archive snapshots:
- `docs/archive/CREF_MASTER_PLAN_v0.md`

Template usage:
- This is the cross-track execution plan for the Colearni Refinement project.
- It does not replace `docs/PLAN.md` (existing project plan).
- All child plans are subordinate to this document.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered track list with stable IDs
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
   - the slice-specific verification gates in the child plan are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (see template below).
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. PRs must stay <= 400 LOC net per CODEX.md. Split if larger.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

Colearni is a learning-first agentic tutor with Socratic pedagogy, mastery gating, a concept graph, and practice tools. The system has reached functional MVP but several areas need refinement: the LLM integration layer needs standardization around LiteLLM's message format and features, the frontend chat UX has rough edges (slideover layout, button placement, chat titles), the message persistence layer drops messages on tab-switch during generation, observability spans are truncated, and new capabilities (vision, web search) are requested.

Earlier work landed the Sigma.js graph renderer, the prompt asset system, practice quizzes with flashcard stacks, and the basic tutor chat loop. This plan exists now to systematically address the accumulated refinement requests across 7 tracks.

## Inputs Used

This plan is based on:

- User feedback (2026-03-04 feature/bug request list)
- `docs/ARCHITECTURE.md` — system overview, repo structure, key interfaces
- `docs/PRODUCT_SPEC.md` — product vision, user flows, learning state machine
- `docs/GRAPH.md` — graph data structures, resolver, gardener, client-side rendering
- `docs/FRONTEND.md` — frontend stack, component inventory, anti-patterns
- `docs/CODEX.md` — PR rules, style, testing requirements
- `docs/OBSERVABILITY.md` — Phoenix setup, event reference
- LiteLLM documentation (completion input/output, prompt caching, reliable completions, JSON mode, function calling, batching, reasoning content, streaming, web search)
- Codebase inspection: `adapters/llm/`, `domain/chat/`, `core/observability.py`, `apps/web/`

## Executive Summary

What is already in good shape:
- Sigma.js graph rendering with ForceAtlas2 layout, search, expand/prune
- Prompt asset system (`core/prompting/`) with versioned markdown prompts
- Practice quizzes and flashcard stacks with grading
- Level-up quiz flow with mastery gating
- Hybrid retrieval (vector + FTS)
- Basic observability with OpenTelemetry + Phoenix
- Onboarding confirmation step
- Streaming status indicators

What is critically broken or materially missing:
1. **LLM message format is non-standard** — RAG results and chat history are stuffed into the system message instead of using the OpenAI-standard messages array
2. **Message persistence drops messages** — switching tabs during generation loses both user and tutor messages until a full page refresh
3. **Phoenix evidence truncation** — observability spans truncate evidence data
4. **Query agent model misconfigured** — shows `gpt5nano` when set to `4.1nano`
5. **Topic switching is unguarded** — students can jump to any topic, even across the graph
6. **Graph representation to LLM is suboptimal** — needs rework for better context
7. **Frontend chat UX rough edges** — slideover needs collapse button, practice slide missing buttons, graph slide sizing, level-up button misplaced, chat title not using current topic
8. **No message regeneration** — users cannot retry a bad response
9. **Graph node selection camera** — some nodes send the view too far away
10. **Missing LiteLLM features** — prompt caching, reliability, JSON mode, function calling, batching, reasoning content, max token trimming
11. **No vision or web search capability** in chat

## Non-Negotiable Constraints

1. PRs <= 400 LOC net (CODEX.md)
2. FastAPI routes stay thin — no business logic
3. Tests required for all new behavior (pytest)
4. Evidence-first: user-visible answers must include citations
5. No unbounded loops; obey resolver + gardener budgets (GRAPH.md)
6. `core/` and `domain/` must not import from `apps/`
7. Frontend: App Router only, React 19 patterns, no anti-patterns from FRONTEND.md

## Completed Work (Do Not Reopen Unless Blocked)

- Sigma.js graph migration (D3 archived)
- Prompt asset system in `core/prompting/`
- Practice quiz + flashcard stack with grading
- Level-up quiz flow with mastery gating
- Onboarding confirmation step
- Streaming status indicators (replace-mode)
- Dev stats toggle
- Graph search with MiniSearch
- Expand/prune controls

## Remaining Track IDs

- `CREF1` LLM Completion Standardization — Rework all LLM calls to use LiteLLM standardized message format + enable LiteLLM features
- `CREF2` Observability & Config Fixes — Fix Phoenix evidence truncation + query agent model config
- `CREF3` Topic Guardrails & Graph Context — Guardrail topic switching + rework graph retrieval for LLM context
- `CREF4` Message Persistence & Streaming — Fix message storage on tab-switch + add regeneration + async streaming
- `CREF5` Frontend Chat UX — Slideover collapse, practice buttons, graph sizing, remove level-up button, chat title, regen button
- `CREF6` Frontend Graph Fixes — Fix node selection camera behavior
- `CREF7` New Chat Capabilities — Vision support + web search/research integration

## Child Plan Map

| Track | Child Plan | Status |
|---|---|---|
| `CREF1` LLM Completion Standardization | `docs/cref/01_llm_completion_plan.md` | pending |
| `CREF2` Observability & Config Fixes | `docs/cref/02_observability_config_plan.md` | pending |
| `CREF3` Topic Guardrails & Graph Context | `docs/cref/03_topic_guardrails_plan.md` | pending |
| `CREF4` Message Persistence & Streaming | `docs/cref/04_message_persistence_plan.md` | pending |
| `CREF5` Frontend Chat UX | `docs/cref/05_frontend_chat_ux_plan.md` | pending |
| `CREF6` Frontend Graph Fixes | `docs/cref/06_frontend_graph_plan.md` | pending |
| `CREF7` New Chat Capabilities | `docs/cref/07_new_capabilities_plan.md` | pending |

## Decision Log

1. **LiteLLM as primary LLM abstraction** — all LLM calls go through `litellm.completion()` / `litellm.acompletion()` with standardized OpenAI message format. OpenAI SDK equivalents are handled transparently by LiteLLM.
2. **RAG evidence as assistant messages** — retrieved evidence items are formatted as assistant messages in the conversation chain, not embedded in the system message.
3. **Chat history in message chain** — full conversation history is part of the messages array (system → history → RAG context → user), not concatenated into the system prompt.
4. **Topic switching uses graph adjacency** — topic changes are limited to nodes within k-hops on the canonical graph; cross-graph jumps are blocked.
5. **Chat title uses current topic** — instead of LLM-generated titles, chat sessions use the currently set concept/topic name.
6. **Frontend slideover collapses to icon button** — replaces the always-visible slideover with a toggleable info/hamburger button.
7. **Message persistence is write-ahead** — user messages are persisted before sending to LLM; assistant messages are persisted as they stream in, not after completion.

## Clarifications Requested (Already Answered)

1. "What format should RAG evidence take in messages?" → Assistant message with evidence items formatted as structured text with source citations.
2. "Should we use LiteLLM proxy or SDK?" → SDK (`litellm.completion()` / `litellm.acompletion()`) directly in the adapter layer.
3. "Which search provider for web search?" → To be configured via environment variable; default to Tavily or Perplexity.

## Deferred Follow-On Scope

- PDF/image crop/zoom vision ingestion (vision capability is for chat image input only)
- Spaced repetition scheduling
- Multi-tenant auth hardening
- Free-form multi-agent runtime
- Full conductor/router agent architecture (ARCHITECTURE.md future target)

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

- `pytest -q`: baseline to be recorded at run start
- `cd apps/web && npm run lint`: baseline to be recorded at run start
- `cd apps/web && npm run typecheck`: baseline to be recorded at run start

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `adapters/llm/providers.py` | LLM message formatting — core of CREF1 rework |
| `domain/chat/response_service.py` | Tutor prompt assembly — must adopt new message format |
| `domain/chat/session_memory.py` | Message persistence — core of CREF4 rework |
| `adapters/db/chat.py` | Raw SQL message persistence — CREF4 target |
| `core/observability.py` | Evidence truncation — CREF2 target |
| `domain/chat/query_analyzer.py` | Model config — CREF2 target |
| `apps/web/features/tutor/components/tutor-slide-over.tsx` | Slideover layout — CREF5 target |
| `apps/web/components/sigma-graph/graph-events.tsx` | Camera behavior — CREF6 target |

## Remaining Work Overview

### CREF1. LLM Completion Standardization

The current LLM integration stuffs RAG results and chat history into the system message as concatenated text. This needs to be reworked to use LiteLLM's standardized OpenAI message format: system message for instructions, assistant messages for RAG evidence, user/assistant alternation for chat history. Additionally, enable LiteLLM features: prompt caching, reliability (retries/fallbacks), JSON mode (`response_format`), function calling (`tools`), batch completion for graph generation, reasoning content handling, max token trimming, and async streaming.

### CREF2. Observability & Config Fixes

Two targeted fixes: (1) Phoenix spans truncate evidence data — the `_AIOnlySpanExporter` or content serialization is clipping long evidence payloads, and (2) the query analyzer's LLM model config shows `gpt5nano` when it should be `4.1nano`, indicating a settings lookup or default fallback issue.

### CREF3. Topic Guardrails & Graph Context

Topic switching is currently unguarded — if RAG retrieves information about a distant topic, the tutor may switch to it. This needs guardrails: (1) try to keep the student on their current topic, (2) if they want to switch, limit to adjacent nodes (k-hops) on the canonical graph, (3) rework how the graph is retrieved and represented to the LLM so it has proper context about topic adjacency and the student's current learning path.

### CREF4. Message Persistence & Streaming

Messages disappear when switching tabs/conversations during generation. The persistence layer needs to write-ahead: persist the user message immediately, then persist assistant message chunks as they stream in. Also add a regeneration button for retrying bad responses. Investigate LiteLLM async streaming (`acompletion(stream=True)`) for better streaming support.

### CREF5. Frontend Chat UX

Multiple UX fixes on the chat page: (1) collapse the slideover into a hamburger/info toggle button, (2) add generate flashcards/quizzes buttons to the practice slide, (3) fix concept graph slide sizing to fill the slideover width, (4) remove the level-up quiz button from the main chat page, (5) set chat title to the currently active topic instead of generating it, (6) add a regeneration button for assistant messages.

### CREF6. Frontend Graph Fixes

When selecting certain nodes on the graph page, the camera animates to a position that's too far away, requiring a view reset. This is likely a camera ratio or node position issue in the `focusNodeId` effect in `graph-events.tsx`.

### CREF7. New Chat Capabilities

Two new capabilities: (1) Vision — accept image uploads (JPEG, PNG) in the chat, encode as base64, and send as `image_url` content type in the LiteLLM message format, (2) Web search — integrate LiteLLM's web search interception or implement a search tool using Tavily/Perplexity for research capability.

## Cross-Track Execution Order

Tracks should be executed in this order. Each track's child plan defines its internal slice order.

1. `CREF2` Observability & Config Fixes — quick wins, unblocks debugging for other tracks
2. `CREF1` LLM Completion Standardization — foundational rework, many tracks depend on the new message format
3. `CREF4` Message Persistence & Streaming — depends on CREF1 (new message format affects what gets persisted)
4. `CREF3` Topic Guardrails & Graph Context — depends on CREF1 (new message format for graph context)
5. `CREF6` Frontend Graph Fixes — independent, can run in parallel with CREF3
6. `CREF5` Frontend Chat UX — partially depends on CREF4 (regen button needs backend), partially independent
7. `CREF7` New Chat Capabilities — depends on CREF1 (LiteLLM message format for images + web search tools)

Dependencies between tracks:

- `CREF1` depends on `CREF2` because observability fixes help debug LLM rework
- `CREF4` depends on `CREF1` because message persistence must align with new message format
- `CREF3` depends on `CREF1` because topic guardrails use the new message format for graph context
- `CREF5` partially depends on `CREF4` because the regen button needs the backend regen endpoint
- `CREF7` depends on `CREF1` because vision and web search use LiteLLM message format extensions
- `CREF6` is independent and can run in parallel with CREF3–CREF5

## Master Status Ledger

| Track | Status | Last note |
|---|---|---|
| `CREF1` LLM Completion Standardization | 🔄 pending | Not started |
| `CREF2` Observability & Config Fixes | 🔄 pending | Not started |
| `CREF3` Topic Guardrails & Graph Context | 🔄 pending | Not started |
| `CREF4` Message Persistence & Streaming | 🔄 pending | Not started |
| `CREF5` Frontend Chat UX | 🔄 pending | Not started |
| `CREF6` Frontend Graph Fixes | 🔄 pending | Not started |
| `CREF7` New Chat Capabilities | 🔄 pending | Not started |

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
pytest -q
cd apps/web && npm run lint
cd apps/web && npm run typecheck
```

## What Not To Do

Do not do the following during this project:

- Do not redesign the agent/conductor architecture (deferred to FUTURE_FREEFORM_MULTI_AGENT.md)
- Do not change the graph data model (concepts_raw, concepts_canon, edges) schema
- Do not remove observability/provenance fields
- Do not add large dependencies without justification in PR summary
- Do not implement spaced repetition or decay mechanics
- Do not change the mastery state machine transitions
- Do not touch the ingestion pipeline (parser, chunker, embedder) unless directly required
- Do not change authentication or workspace isolation logic

## Self-Audit Convergence Protocol

After all implementation tracks reach "done" in the Master Status Ledger, the run enters a self-audit convergence loop. The agent does NOT stop — it automatically audits its own work.

### Why This Exists

Agents working top-to-bottom through a plan commonly miss edge cases, leave subtle regressions, or make assumptions that don't hold once later slices land. **Passing tests do NOT prove correctness.** Tests only check what they were written to check — they miss logic errors, silent data drops, dead code paths, and integration mismatches. This protocol forces a fresh-eyes review that catches what tests cannot.

### Fresh-Eyes Audit Principle

**The auditor must treat every slice as if it has NOT been implemented.** Do not skim Verification Blocks or trust prior claims. Instead:

1. Read the slice requirements (purpose, implementation steps, exit criteria) as if seeing them for the first time.
2. **Before looking at any code**, independently write down in the Audit Workspace:
   - What files should have been created or changed
   - What logic should exist in each file
   - What edge cases and error paths should be handled
   - What the tests should actually verify (not just "tests pass")
3. **Only then** open the actual code and compare against your independent analysis.
4. For every point in your "should-exist" list, verify it truly exists and is correct.
5. **Do not trust test names.** Open each test, read the body, and confirm it actually tests the claimed behavior with meaningful assertions — not just "no exception thrown."

### Convergence Loop

```text
AUDIT_CYCLE = 0
MAX_AUDIT_CYCLES = 3

while AUDIT_CYCLE < MAX_AUDIT_CYCLES:
    AUDIT_CYCLE += 1
    
    1. Re-read docs/CREF_MASTER_PLAN.md and every child plan in order.
    2. For each completed slice, perform the FRESH-EYES AUDIT:
       a. Read the slice definition (purpose, steps, exit criteria).
       b. In the child plan's Audit Workspace, write your independent
          analysis of what SHOULD exist — before looking at any code.
       c. Now open every file listed in the Verification Block.
          Compare actual code against your independent analysis.
       d. For each implementation step in the slice:
          - Is the logic actually correct, or does it just not crash?
          - Are edge cases handled (empty inputs, nulls, boundaries)?
          - Is error handling meaningful (not swallowed or generic)?
          - Does the code do what the slice SAYS it does, or something
            subtly different?
       e. For each test:
          - Read the test body. Does it assert the RIGHT thing?
          - Does it test edge cases, not just the happy path?
          - Could the test pass even if the implementation is wrong?
            (e.g., mocking too much, asserting only status codes)
       f. BEHAVIORAL AUDIT (DO NOT SKIP): For each feature-facing slice,
          trace the full code path from user action → frontend → API route
          → domain logic → response. Verify:
          - The API schema accepts all required fields (no Pydantic silent drops)
          - Route handlers forward ALL fields to domain layer (no missing kwargs)
          - Domain logic actually uses the forwarded fields (not dead code)
          - The response includes expected data (not stubs or hardcoded values)
          - If a feature has a toggle, verify: default state, persistence
            mechanism, and that toggling actually changes behavior
       g. PROMPT AUDIT (for any LLM-facing slice): Open the prompt template
          and verify:
          - System vs user role assignment is correct
          - Template variables are actually populated (not placeholders)
          - The prompt produces the expected output format
       h. OBSERVABILITY AUDIT: For any slice that touches tracing, verify
          traces show correct data in the expected panels, not just in
          attributes.
       i. Cross-slice integration: does this slice's output still work
          with what later slices built on top of it?
       j. No TODO/FIXME/HACK comments left in changed files.
       k. No dead imports, unused variables, or orphaned test stubs.
    3. Run the full Verification Matrix (all test suites, typecheck, lint).
    4. Produce an Audit Report in the child plan's Audit Workspace
       (template below).
    5. If CONVERGED (0 issues): update Master Status Ledger with
       "✅ audit-passed" and exit the loop.
    6. If NEEDS_REPASS:
       a. Reopen affected slices (set status back to pending in the
          child plan, add "Audit Cycle N" note)
       b. Re-implement the reopened slices from scratch — do NOT just
          patch the previous attempt. Re-read the slice definition,
          think about what needs to happen, implement it properly,
          then verify again.
       c. Continue to next audit cycle
```

### Audit Workspace

Each child plan MUST contain an `## Audit Workspace` section (initially empty). During the audit, the agent writes its fresh-eyes analysis here:

```text
--- Audit Cycle {N} - {slice-id} ---

What SHOULD exist (written BEFORE reading code):
- Files: <expected file changes>
- Logic: <expected logic in each file>
- Edge cases: <expected edge case handling>
- Tests: <what tests should verify>

What ACTUALLY exists (written AFTER reading code):
- Files: <actual file changes — match/mismatch?>
- Logic: <actual logic — correct/incorrect/missing?>
- Edge cases: <handled/missing?>
- Tests: <meaningful assertions or shallow?>

Gaps found:
- <gap 1>
- <gap 2>
- <none if clean>

Verdict: PASS / REOPEN
Reason: <if reopened, explain exactly what's wrong>
```

### Audit Cycle Budget

- **Maximum 3 audit cycles** to prevent unbounded loops.
- If cycle 3 still finds issues, produce a final Audit Report listing all remaining items and mark them as "deferred to manual review".
- The agent MUST NOT enter cycle 4. Instead, it produces a handoff summary for the human reviewer.

### Audit Report Template

```text
Audit Report — Cycle {N}

Slices re-examined: {count}
Full verification matrix: {PASS / FAIL with details}

Fresh-eyes analysis completed: {yes/no for each slice}

Issues found:
1. [{severity}] {slice-id}: {description}
   - File(s): {paths}
   - Expected (from fresh analysis): {what should be true}
   - Actual (from code review): {what was found}
   - Why tests didn't catch it: {explanation}
   - Action: {reopen slice / cosmetic fix / defer}

Verdict: {CONVERGED | NEEDS_REPASS}
Slices reopened: {list or "none"}
```

### What the Audit Checks

| Check | What it catches |
|---|---|
| Fresh-eyes independent analysis | Assumptions baked in from implementation bias |
| Code logic review (not just test results) | Bugs that tests don't cover, dead code, wrong logic |
| Test body inspection | Shallow tests that pass but don't verify behavior |
| Verification Block accuracy | Slice claims that are no longer true |
| Exit criteria still met | Regressions from later slices |
| TODO/FIXME scan | Unfinished work left behind |
| Dead code scan | Imports, variables, stubs that serve no purpose |
| Behavioral trace | Dropped fields, missing kwargs, stubs |
| Prompt review | Bad role assignment, empty variables |
| Observability review | Traces that don't surface in expected panels |

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the implementation phase:

```text
Read docs/CREF_MASTER_PLAN.md.
Select the first child plan in execution order that still has incomplete slices.
Read that child plan and begin with its current incomplete slice exactly as described.

Execution loop:

1. Work on exactly one sub-slice at a time and keep the change set PR-sized.
2. Preserve all constraints in docs/CREF_MASTER_PLAN.md and the active child plan.
3. Run the slice verification steps before claiming completion.
4. When a slice is complete, update:
   - the active child plan with a Verification Block
   - the active child plan with any Removal Entries added during that slice
   - docs/CREF_MASTER_PLAN.md with the updated status ledger / remaining status note
5. After every 2 completed slices OR if your context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and the active child plan and restate which slices remain.
6. If the active child plan still has incomplete slices, continue to the next slice.
7. If the active child plan is complete, go back to docs/CREF_MASTER_PLAN.md, pick the next incomplete child plan in order, and continue.

Stop only if:

- verification fails
- the current repo behavior does not match plan assumptions and the plan must be updated first
- a blocker requires user input or approval
- completing the next slice would force a risky scope expansion

Do NOT stop because one child plan is complete.
Do NOT stop because you updated the session plan, todo list, or status ledger.
The run is only complete when docs/CREF_MASTER_PLAN.md shows no remaining incomplete tracks.

Project-specific constraints:
- PRs <= 400 LOC net
- FastAPI routes stay thin (no business logic)
- Tests required for all new behavior
- Evidence/citations preserved for user-visible answers
- No unbounded loops
- core/ and domain/ must not import from apps/

START:

Read docs/CREF_MASTER_PLAN.md.
Pick the first incomplete child plan in execution order.
Begin with the current slice in that child plan exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/CREF_MASTER_PLAN.md before every move to the next child plan. It can be dynamically updated. Check the latest version and continue.

--- SELF-AUDIT PHASE ---

When docs/CREF_MASTER_PLAN.md shows all tracks complete (no remaining incomplete tracks),
do NOT stop. Enter the self-audit convergence loop:

Audit loop (max 3 cycles):

1. Re-read docs/CREF_MASTER_PLAN.md and every child plan.
2. For each completed slice, verify the Verification Block still holds:
   - Files exist and contain the described changes
   - Tests pass (run full Verification Matrix)
   - Exit criteria are still met (no regressions from later slices)
   - No TODO/FIXME/HACK comments left in changed files
3. Check cross-slice integration:
   - Does each slice's output still work with what later slices built?
   - Are there dead imports, unused code, or orphaned tests?
4. Produce an Audit Report (use template from Self-Audit Convergence Protocol section).
5. If CONVERGED (0 issues found): mark all tracks as "audit-passed" in the
   Master Status Ledger. The run is now complete.
6. If NEEDS_REPASS: reopen affected slices, re-implement them with full
   verification, then start the next audit cycle.
7. If this is cycle 3 and issues remain: produce a final handoff report
   listing all remaining items for manual review. The run is complete.

The run is ONLY complete when:
- All tracks show "audit-passed" in the Master Status Ledger, OR
- 3 audit cycles have been exhausted and a handoff report is produced
```
