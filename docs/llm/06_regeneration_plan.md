# L6 — Message Regeneration

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Dependencies: L2 ✅ (message status tracking)

## Goal

Allow users to re-generate an unsatisfactory assistant response. Marks the old
message as `superseded` (status already defined in L2), re-runs generation with
the same user query, and persists a new assistant message.

## Slice Status

| Slice | Description | Status |
|-------|-------------|--------|
| L6.1 | Add `mark_message_superseded()` in adapters/db/chat.py | 🔄 pending |
| L6.2 | Implement `regenerate_response()` in domain/chat/ | 🔄 pending |
| L6.3 | Add regenerate endpoint in apps/api/routes/chat.py | 🔄 pending |

Note: L6.4 (frontend) is out of scope for this backend-focused LLM refactoring.
The `superseded` status and history-loading exclusion already exist from L2.

---

## L6.1 — mark_message_superseded DB function

**File**: `adapters/db/chat.py`

Add `mark_message_superseded(session, message_id) -> bool` that sets
`status = 'superseded'` on a chat message. Returns True if updated.

**Tests**: `tests/adapters/test_chat_persistence.py` or inline unit tests.

**Exit criteria**: Function exists and is tested.

---

## L6.2 — regenerate_response domain function

**File**: `domain/chat/session_memory.py`

Add `supersede_and_prepare_regeneration(session, message_id, session_id) -> str`
that:
1. Validates the message exists and is an assistant message with status=complete
2. Marks it as superseded
3. Returns the preceding user query text for re-generation

**Tests**: `tests/domain/test_regeneration.py`

**Exit criteria**: Domain function tested with mock DB.

---

## L6.3 — Regenerate API endpoint

**File**: `apps/api/routes/chat.py`

Add `POST /workspaces/{ws_id}/chat/sessions/{session_id}/messages/{msg_id}/regenerate`
that:
1. Calls domain function to supersede old message
2. Triggers a new streaming response with the same user query
3. Returns the new stream

**Tests**: `tests/api/test_chat_regenerate.py`

**Exit criteria**: Endpoint returns streaming response after superseding.

---

## Removal Entries

(To be filled as slices complete)

## Verification Blocks

(To be filled as slices complete)
