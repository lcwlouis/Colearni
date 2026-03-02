# Socratic Tutor End-to-End Audit

**Date:** 2026-03-02
**Scope:** Trace the full `tutor_protocol` flag from frontend toggle → API → route → domain → LLM

## Chain Status Summary

| # | Layer | File | Status |
|---|-------|------|--------|
| 1 | Frontend type | `apps/web/lib/api/types.ts:81` | ✅ `tutor_protocol?: boolean` present |
| 2 | Frontend send | `apps/web/features/tutor/hooks/use-tutor-messages.ts:148,261` | ✅ Sent in both streaming & blocking paths |
| 3 | API gateway schema | `apps/api/routes/chat.py:47-56` (`ChatRespondAPIRequest`) | ❌ **`tutor_protocol` field MISSING** |
| 4 | Route handler (blocking) | `apps/api/routes/chat.py:182-192` | ❌ **`tutor_protocol` NOT passed** to internal request |
| 5 | Route handler (streaming) | `apps/api/routes/chat.py:234-244` | ❌ **`tutor_protocol` NOT passed** to internal request |
| 6 | Internal schema | `core/schemas/chat.py:42` (`ChatRespondRequest`) | ✅ `tutor_protocol: bool = False` present |
| 7 | Stream branching | `domain/chat/stream.py:359` | ✅ Logic correct but **never reached** (flag always `False`) |
| 8 | Prompt builder | `domain/chat/prompt_kit.py:318-344` | ✅ `build_socratic_interactive_prompt()` implemented |
| 9 | Asset registry mapping | `domain/chat/prompt_kit.py:93` | ✅ `"socratic_interactive": "tutor_socratic_interactive_v1"` |
| 10 | Prompt loader resolution | `core/prompting/loader.py:70-77` | ✅ `tutor_socratic_interactive_v1` → `tutor/socratic_interactive_v1.md` |
| 11 | Prompt template | `core/prompting/assets/tutor/socratic_interactive_v1.md` | ✅ Exists, 3384 bytes, well-formed |
| 12 | Tutor state schema | `core/schemas/tutor_state.py` | ✅ Full state model with `init_relation_concept()` |
| 13 | Tutor state store | `domain/chat/tutor_state_store.py` | ✅ Thread-safe in-memory store with deep copies |
| 14 | Command parser | `domain/chat/tutor_commands.py` | ✅ 11 command types parsed and applied |
| 15 | LLM client factory | `domain/chat/response_service.py:116-121` | ✅ `build_tutor_llm_client()` returns `GraphLLMClient` or `None` |
| 16 | LLM method | `adapters/llm/providers.py:185` / `core/contracts.py:113` | ✅ `generate_tutor_text_stream()` exists on protocol & impl |
| 17 | State update from response | `domain/chat/stream.py:621+` | ✅ `_update_tutor_state_from_response()` parses STATE block |

## Root Cause Analysis

The Socratic tutor has **two breaks** in the API layer that prevent the flag from ever reaching the domain:

### Break 1: `ChatRespondAPIRequest` missing `tutor_protocol` field

**File:** `apps/api/routes/chat.py`, lines 47-56

```python
class ChatRespondAPIRequest(BaseModel):
    """Client-facing respond request (no workspace_id / user_id)."""

    query: str = Field(min_length=1)
    session_id: str | None = Field(default=None, description="Session UUID public_id")
    concept_id: int | None = Field(default=None, gt=0)
    suggested_concept_id: int | None = Field(default=None, gt=0)
    concept_switch_decision: str | None = None
    top_k: int = Field(default=5, ge=1)
    grounding_mode: str | None = None
    # ← tutor_protocol: bool = False  ← MISSING
```

**Impact:** When the frontend sends `{ "tutor_protocol": true, ... }`, Pydantic silently discards the unknown field. The `payload` object never has a `.tutor_protocol` attribute. By default Pydantic v2 ignores extra fields.

### Break 2: Route handlers don't forward `tutor_protocol`

**File:** `apps/api/routes/chat.py`, lines 182-192 (blocking) and 234-244 (streaming)

Both route handlers construct the internal `ChatRespondRequest` identically:

```python
internal = ChatRespondRequest(
    workspace_id=ws.workspace_id,
    user_id=ws.user.id,
    query=payload.query,
    session_id=resolved_session_id,
    concept_id=payload.concept_id,
    suggested_concept_id=payload.suggested_concept_id,
    concept_switch_decision=payload.concept_switch_decision,
    top_k=payload.top_k,
    grounding_mode=payload.grounding_mode,
    # ← tutor_protocol=payload.tutor_protocol,  ← MISSING
)
```

**Impact:** Even if Break 1 were fixed, `tutor_protocol` would still default to `False` in the internal request because it is never assigned from the payload.

### What happens at runtime

1. Frontend sends `tutor_protocol: true` in JSON body
2. Pydantic drops it (field not in `ChatRespondAPIRequest`)
3. Route handler constructs internal request without it → defaults to `False`
4. `stream.py:359` condition: `request.tutor_protocol and ...` → `False and ...` → skipped
5. Falls through to generic tutor path at `stream.py:406` (plain `tutor_llm_client is not None`)
6. User gets a generic tutor response, not the Socratic interactive protocol

The user sees a normal chat response — **no Socratic questioning, no state tracking, no micro-world table, no commands**. The toggle has zero observable effect.

## Classification

**"Wired but never activates"** — The entire domain-layer implementation is complete and appears correct (state management, command parsing, prompt template, LLM streaming). But the API gateway layer has a two-link break that silently prevents the flag from reaching the domain. The feature is a dead code path in production.

## Required Fixes

### Fix 1: Add `tutor_protocol` to `ChatRespondAPIRequest`

**File:** `apps/api/routes/chat.py`, after line 56

```python
class ChatRespondAPIRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = Field(default=None, description="Session UUID public_id")
    concept_id: int | None = Field(default=None, gt=0)
    suggested_concept_id: int | None = Field(default=None, gt=0)
    concept_switch_decision: str | None = None
    top_k: int = Field(default=5, ge=1)
    grounding_mode: str | None = None
    tutor_protocol: bool = False          # ← ADD THIS
```

### Fix 2: Forward `tutor_protocol` in both route handlers

**File:** `apps/api/routes/chat.py`

In `respond_chat()` (line 182-192) — add `tutor_protocol=payload.tutor_protocol`:

```python
internal = ChatRespondRequest(
    workspace_id=ws.workspace_id,
    user_id=ws.user.id,
    query=payload.query,
    session_id=resolved_session_id,
    concept_id=payload.concept_id,
    suggested_concept_id=payload.suggested_concept_id,
    concept_switch_decision=payload.concept_switch_decision,
    top_k=payload.top_k,
    grounding_mode=payload.grounding_mode,
    tutor_protocol=payload.tutor_protocol,  # ← ADD THIS
)
```

In `respond_chat_stream()` (line 234-244) — same addition:

```python
internal = ChatRespondRequest(
    workspace_id=ws.workspace_id,
    user_id=ws.user.id,
    query=payload.query,
    session_id=resolved_session_id,
    concept_id=payload.concept_id,
    suggested_concept_id=payload.suggested_concept_id,
    concept_switch_decision=payload.concept_switch_decision,
    top_k=payload.top_k,
    grounding_mode=payload.grounding_mode,
    tutor_protocol=payload.tutor_protocol,  # ← ADD THIS
)
```

### Fix 3 (potential): Verify the Socratic path end-to-end with an integration test

After applying Fixes 1 & 2, the existing test infrastructure in `tests/domain/test_s1_phase_semantics.py` already exercises the streaming path with `tutor_protocol=True`. However, there is no route-level test that verifies `tutor_protocol` is forwarded from `ChatRespondAPIRequest` → `ChatRespondRequest`. A thin route-level test should be added.

## Secondary Observations

1. **In-memory state store is volatile.** `tutor_state_store.py` uses a `dict[int, TutorState]` — state is lost on server restart. This is acceptable for prototyping but should be noted for production readiness.

2. **`init_relation_concept()` is hardcoded.** The Socratic session always initializes with the "Relation" concept demo (hardcoded "Students" table). This is fine for an MVP but should eventually be driven by the user's selected concept.

3. **Silent fallthrough is a design risk.** When `tutor_protocol` is `True` but any other condition fails (no `session_id`, no `tutor_llm_client`), the code silently falls through to the generic path at line 406 with no logging. Adding a `log.warning` for partial condition matches would aid debugging.

4. **`_update_tutor_state_from_response` regex is greedy.** The regex `r"^STATE\s*\n(.*?)$"` with `re.DOTALL` captures from STATE to end-of-string. If the LLM puts STATE in the middle of the response, it will capture trailing content. This is likely fine given the prompt instructs STATE as the last section, but worth noting.
