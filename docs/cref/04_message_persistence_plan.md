# Colearni Refinement — Message Persistence & Streaming Plan

Last updated: 2026-03-04

Parent plan: `docs/CREF_MASTER_PLAN.md`

Archive snapshots:
- `docs/archive/cref/04_message_persistence_plan_v0.md`

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

This track addresses the critical message persistence bug and adds message regeneration capability.

The core bug: when a user switches tabs or conversations during LLM generation, the in-progress message is lost. Both the user message and the assistant response disappear. Only after the generation completes and the user refreshes does the content appear. This is because persistence happens after generation completes, not during.

The fix: implement write-ahead persistence — the user message is persisted immediately when sent, and the assistant message is persisted as chunks stream in (or at minimum, persisted in a "generating" state that gets finalized). Additionally, add a regeneration button so users can retry bad or failed responses.

## Inputs Used

- `docs/CREF_MASTER_PLAN.md` (parent plan)
- `domain/chat/session_memory.py` — current persistence logic (`persist_turn()`)
- `adapters/db/chat.py` — raw SQL message persistence
- `domain/chat/respond.py` — response orchestration
- `apps/api/` — chat endpoints

## Executive Summary

What works today:
- `persist_turn()` saves user + assistant messages after generation completes
- `append_chat_message()` inserts to `chat_messages` table
- Frontend displays streamed responses in real-time
- Message history loads correctly after refresh

What this track fixes or adds:
1. Write-ahead persistence for user messages (persisted before LLM call)
2. Progressive persistence for assistant messages (persisted during streaming)
3. Message state tracking (pending → generating → complete → failed)
4. Regeneration endpoint and logic
5. Graceful handling of interrupted generations

## Non-Negotiable Constraints

1. No data loss — every user message must be persisted before the LLM call starts
2. Assistant messages must be recoverable even if generation is interrupted
3. Persistence must not slow down streaming (async writes or batched commits)
4. Must align with CREF1 message format changes
5. Message ordering must be preserved

## Completed Work (Do Not Reopen Unless Blocked)

- `chat_messages` table schema
- `append_chat_message()` / `create_chat_session()`
- `persist_turn()` in session_memory.py
- Frontend streaming display

## Remaining Slice IDs

- `CREF4.1` Write-Ahead User Message Persistence
- `CREF4.2` Progressive Assistant Message Persistence
- `CREF4.3` Message State Tracking
- `CREF4.4` Regeneration Endpoint

## Decision Log

1. User messages are persisted synchronously before the LLM call is initiated.
2. Assistant messages are created in a "generating" state before streaming starts, then updated to "complete" when done.
3. If generation fails or is interrupted, the assistant message stays in "generating" state and can be retried.
4. Regeneration creates a new assistant message for the same user message, preserving history.
5. Frontend detects "generating" state messages and shows a spinner/status indicator.

## Current Verification Status

- `pytest -q`: baseline to be recorded

Hotspots:

| File | Why it matters |
|---|---|
| `domain/chat/session_memory.py` | Persistence orchestration — core of this track |
| `adapters/db/chat.py` | Raw SQL persistence — needs state column |
| `domain/chat/respond.py` | Response pipeline — persistence hooks go here |
| `apps/api/` chat routes | Regeneration endpoint |

## Implementation Sequencing

### CREF4.1. Slice 1: Write-Ahead User Message Persistence

Purpose:
- Persist the user message to the database before initiating the LLM call, so it survives tab switches and disconnections.

Root problem:
- `persist_turn()` saves both user and assistant messages after generation completes. If generation is interrupted, both are lost.

Files involved:
- `domain/chat/respond.py`
- `domain/chat/session_memory.py`
- `adapters/db/chat.py`

Implementation steps:
1. Split `persist_turn()` into `persist_user_message()` and `persist_assistant_message()`
2. Call `persist_user_message()` at the start of the response pipeline, before retrieval or LLM call
3. `persist_user_message()` inserts the user message with `status='complete'`
4. Ensure session creation still happens if this is the first message
5. Title generation happens at this point (using current topic name per CREF5 changes or existing logic)
6. Update tests

What stays the same:
- Message format in DB
- Session creation logic (just moved earlier)
- History loading

Verification:
- `pytest -q tests/`
- Manual check: send a message, switch tabs immediately — user message visible on return
- Verify no duplicate messages on normal flow

Exit criteria:
- User message is persisted before LLM call
- No duplicate messages
- Tab switching doesn't lose user message

### CREF4.2. Slice 2: Progressive Assistant Message Persistence

Purpose:
- Persist assistant messages progressively during streaming, not just after completion.

Root problem:
- Assistant message is only persisted after generation completes. If interrupted, the response is lost.

Files involved:
- `domain/chat/session_memory.py`
- `domain/chat/respond.py`
- `adapters/db/chat.py`

Implementation steps:
1. Before streaming starts, insert a placeholder assistant message with `status='generating'` and empty content
2. As chunks stream in, periodically update the message content (every N chunks or every K seconds, not every chunk)
3. On stream completion, finalize the message with `status='complete'` and full content
4. On stream error, mark the message as `status='failed'` with partial content
5. Add a `status` column to `chat_messages` if not present (migration)
6. Update tests

What stays the same:
- Streaming format to frontend
- Frontend streaming consumption
- Message format

Verification:
- `pytest -q tests/`
- Manual check: start generation, switch tabs, come back — partial assistant message visible
- Verify complete messages have `status='complete'`
- Verify failed generations have `status='failed'`

Exit criteria:
- Assistant message is recoverable after interruption
- Progressive updates don't significantly slow streaming
- Message status accurately reflects generation state

### CREF4.3. Slice 3: Message State Tracking

Purpose:
- Add message state tracking so the frontend can properly display in-progress, complete, and failed messages.

Root problem:
- Messages currently have no state — they're either in the DB or not. The frontend needs to know if a message is still generating, complete, or failed.

Files involved:
- `adapters/db/chat.py` (query filtering)
- `apps/api/` chat routes (include status in response)
- API schemas/response models

Implementation steps:
1. Add `status` to the message API response schema
2. Update message list endpoint to include `status` field
3. Handle `generating` status in the frontend — show a loading indicator
4. Handle `failed` status — show error state with retry option
5. Filter out `generating` messages from history loading for LLM context (they're incomplete)
6. Update tests

What stays the same:
- Message content format
- Chat session management
- History compaction logic

Verification:
- `pytest -q tests/`
- API test: message list includes `status` field
- Manual check: generating messages show indicator, failed messages show error

Exit criteria:
- Message status is part of the API response
- Frontend handles all status states
- History loading excludes incomplete messages

### CREF4.4. Slice 4: Regeneration Endpoint

Purpose:
- Add a backend endpoint to regenerate an assistant response for a given message.

Root problem:
- Users cannot retry a bad or failed response. They must start a new conversation or rephrase.

Files involved:
- `apps/api/` chat routes (new endpoint)
- `domain/chat/respond.py` (regeneration logic)
- `domain/chat/session_memory.py` (message management)

Implementation steps:
1. Add `POST /chat/sessions/{session_id}/messages/{message_id}/regenerate` endpoint
2. The endpoint:
   - Validates the message exists and is an assistant message
   - Marks the old assistant message as `status='superseded'`
   - Finds the preceding user message
   - Re-runs the response pipeline with the same user message
   - Returns a new streaming response
3. The new assistant message is persisted with write-ahead (CREF4.2 pattern)
4. Keep the old message in DB for history but exclude from LLM context
5. Add tests

What stays the same:
- Response pipeline logic (reused, not duplicated)
- Retrieval logic
- Mastery tracking

Verification:
- `pytest -q tests/`
- API test: regenerate endpoint returns new streaming response
- Manual check: regenerated message replaces old one in UI
- Verify old message is preserved in DB with `superseded` status

Exit criteria:
- Regeneration endpoint works
- Old messages are preserved but not shown
- Streaming works for regenerated responses

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

1. `CREF4.1` Write-Ahead User Message Persistence
2. `CREF4.2` Progressive Assistant Message Persistence
3. `CREF4.3` Message State Tracking
4. `CREF4.4` Regeneration Endpoint

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
ruff check .
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read docs/CREF_MASTER_PLAN.md, then read docs/cref/04_message_persistence_plan.md.
Begin with the next incomplete CREF4 slice exactly as described.

Execution loop for this child plan:

1. Work on one CREF4 slice at a time.
2. No data loss allowed. Persistence must not slow streaming. Message ordering preserved. Tests required.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed CREF4 slices OR if context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and docs/cref/04_message_persistence_plan.md and restate which CREF4 slices remain.
6. Continue to the next incomplete CREF4 slice once the previous slice is verified.
7. When all CREF4 slices are complete, immediately re-open docs/CREF_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because CREF4 is complete. CREF4 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

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
Read docs/cref/04_message_persistence_plan.md.
Begin with the current CREF4 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When CREF4 is complete, immediately return to docs/CREF_MASTER_PLAN.md and continue with the next incomplete child plan.
```
