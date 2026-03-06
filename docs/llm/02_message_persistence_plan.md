# L2 — Message Persistence & Status Tracking

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Track ID: `L2`
Status: 🔄 in-progress

## Purpose

Fix message persistence so in-progress generations survive tab switches. Add lifecycle
status tracking (`generating` | `complete` | `failed` | `superseded`) to chat messages.

## Current State

- Messages are only persisted after stream completion in `persist_turn()`
- No `status` column on `chat_messages` table
- No write-ahead placeholder pattern
- If user switches tabs mid-stream, the response is lost
- No `persist_user_message()`, `finalize_assistant_message()`, or `fail_assistant_message()`
- `chat_messages` columns: `id`, `session_id`, `workspace_id`, `user_id`, `type`, `payload`, `created_at`

## Target State

- `chat_messages` has a `status` column (`complete` | `generating` | `failed` | `superseded`)
- User messages persisted immediately (write-ahead) before LLM call
- Assistant placeholder inserted with `status=generating` before streaming
- Placeholder finalized to `status=complete` (with full response) after stream completes
- On error: placeholder updated to `status=failed` with partial text
- History loading excludes `generating`, `failed`, `superseded` messages from LLM context
- Stale `generating` messages marked `failed` on startup

## Slice Status

| Slice | Description | Status |
|-------|-------------|--------|
| L2.1 | Add `status` column to `chat_messages` (migration + schema) | ✅ done |
| L2.2 | Implement write-ahead `persist_user_message()` + assistant placeholder | ✅ done |
| L2.3 | Add `finalize_assistant_message()` and `fail_assistant_message()` helpers | ✅ done |
| L2.4 | Update `generate_chat_response_stream()` to use write-ahead + finalize | ✅ done |
| L2.5 | Update message loading to handle statuses | ✅ done |
| L2.6 | Add stale message cleanup on startup | ✅ done |

## Slice Definitions

### L2.1 — Add `status` column to `chat_messages`

**Purpose**: Add the `status` column and `MessageStatus` enum to support lifecycle tracking.

**Implementation Steps**:
1. Add `MessageStatus` to `core/schemas/chat.py`:
   ```python
   MessageStatus = Literal["complete", "generating", "failed", "superseded"]
   ```
2. Create Alembic migration adding `status` column (TEXT, NOT NULL, default `'complete'`):
   - Default `'complete'` ensures existing messages are valid
   - Add index on `(session_id, status)` for filtered loading
3. Update `ChatMessageRecord` or equivalent Pydantic model to include `status`
4. Update `append_chat_message()` in `adapters/db/chat.py` to accept optional `status` param

**Exit Criteria**:
- Migration runs successfully (`alembic upgrade head`)
- `ChatMessageRecord` has `status` field
- `append_chat_message()` accepts `status` parameter with default `'complete'`
- All existing tests pass

### L2.2 — Write-ahead persistence

**Purpose**: Persist user message immediately and create an assistant placeholder before streaming.

**Implementation Steps**:
1. Add `persist_user_message(session_id, text, ...)` to `session_memory.py`:
   - Inserts user message with `status='complete'`
   - Returns the message ID
2. Add `create_assistant_placeholder(session_id, ...)` to `session_memory.py`:
   - Inserts assistant message with `status='generating'`, empty payload
   - Returns the message ID (needed for finalize/fail)
3. Update `persist_turn()` to use these new functions internally (backward compat)

**Exit Criteria**:
- `persist_user_message()` and `create_assistant_placeholder()` exist
- Both insert messages with correct status
- `persist_turn()` still works for non-streaming paths
- Tests cover both new functions

### L2.3 — Finalize and fail helpers

**Purpose**: Add DB helpers to update assistant message status after streaming completes or fails.

**Implementation Steps**:
1. Add `finalize_assistant_message(message_id, *, payload)` to `adapters/db/chat.py`:
   - UPDATE `chat_messages` SET `status='complete'`, `payload=<full envelope>`
   - WHERE `id=message_id` AND `status='generating'`
2. Add `fail_assistant_message(message_id, *, partial_text="")` to `adapters/db/chat.py`:
   - UPDATE `chat_messages` SET `status='failed'`, `payload=<error info + partial>`
   - WHERE `id=message_id` AND `status='generating'`
3. Add corresponding functions in `session_memory.py` that call the DB helpers

**Exit Criteria**:
- Both functions exist and update status correctly
- Idempotent: calling on already-finalized message is a no-op
- Tests cover success, failure, and idempotent cases

### L2.4 — Update streaming to use write-ahead + finalize

**Purpose**: Wire the write-ahead pattern into `generate_chat_response_stream()`.

**Implementation Steps**:
1. At stream start: call `persist_user_message()` + `create_assistant_placeholder()`
2. On successful completion: call `finalize_assistant_message()` with full envelope
3. On error: call `fail_assistant_message()` with partial text
4. Remove the old `persist_turn()` call at the end of streaming
5. Keep social fast-path using the simpler `persist_turn()` (no streaming involved)

**Exit Criteria**:
- Streaming uses write-ahead pattern
- User message is in DB before LLM call starts
- Assistant message transitions: generating → complete or generating → failed
- Social fast-path still works
- All streaming tests pass

### L2.5 — Update message loading

**Purpose**: Filter out non-displayable messages when loading for LLM context.

**Implementation Steps**:
1. Update history loading queries in `adapters/db/chat.py` to exclude `status IN ('generating', 'failed', 'superseded')` from LLM context
2. Update message loading for frontend display to include `generating` (show with indicator) and `failed` (show with error state), but exclude `superseded`
3. Add `status` to the message payload returned to frontend

**Exit Criteria**:
- LLM context loading excludes generating/failed/superseded
- Frontend message loading includes generating and failed with status field
- Tests cover filtered loading

### L2.6 — Stale message cleanup

**Purpose**: On app startup, mark orphaned `generating` messages as `failed`.

**Implementation Steps**:
1. Add `cleanup_stale_generating_messages()` to `adapters/db/chat.py`:
   - UPDATE `chat_messages` SET `status='failed'` WHERE `status='generating'`
   - Log count of cleaned up messages
2. Wire into app startup in `apps/api/main.py` (lifespan event)

**Exit Criteria**:
- Stale generating messages are cleaned up on startup
- Cleanup is logged
- Test covers the cleanup function

## Verification Blocks

(Populated as slices are completed)

## Removal Ledger

(Populated as code is removed/replaced)

## Audit Workspace

(Populated during self-audit phase)

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/llm/02_message_persistence_plan.md. Begin with the current incomplete slice.
Follow the execution loop in docs/llm/LLM_MASTER_PLAN.md.
```
