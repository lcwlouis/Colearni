# CUX1 — Chat-Topic Binding

Parent plan: `docs/chat_ux/CUX_MASTER_PLAN.md`
Last updated: 2026-03-05

## Purpose

Every chat session must be bound to exactly one concept (topic or umbrella tier) at creation time. The session's `concept_id` is immutable after creation. The chat title is derived directly from the bound concept's `canonical_name`. The concept resolver is scoped to only resolve subtopics within the bound topic's subtree. When the resolver detects an unrelated topic, it suggests "Start a new chat about X" instead of switching in-place.

## Slices

### S1.1 — Schema: Add `concept_id` to `chat_sessions`

**What:** Add `concept_id` (FK → `concepts_canon.id`) column to `chat_sessions` table. Create Alembic migration. Column is nullable for backward compatibility with existing sessions.

**Files to change:**
- `adapters/db/chat.py` — add column to table DDL or ORM model
- New Alembic migration file

**Exit criteria:**
- Migration runs cleanly (upgrade + downgrade)
- Existing sessions unaffected (NULL concept_id)
- `make test` passes

---

### S1.2 — Domain: Bind concept at session creation

**What:** Update `create_chat_session()` to accept optional `concept_id`. When provided, look up concept's `canonical_name` and set as session title. Update `ChatSessionSummary` schema to include `concept_id`.

**Files to change:**
- `adapters/db/chat.py` — `create_chat_session()` accepts and stores `concept_id`, sets title
- `domain/chat/sessions.py` — `create_session()` passes through `concept_id`
- `core/schemas/chat.py` — add `concept_id: int | None` to `ChatSessionSummary`
- API route (if applicable) — accept `concept_id` in create-session request

**Exit criteria:**
- Creating session with `concept_id` sets title = concept name
- Creating session without `concept_id` works as before
- `ChatSessionSummary` includes `concept_id`
- Tests cover both paths

---

### S1.3 — Simplify title generation

**What:** When session has `concept_id`, `generate_session_title()` returns the concept's `canonical_name` directly (skip all heuristics). Keep fallback logic for legacy sessions without `concept_id`.

**Files to change:**
- `domain/chat/title_gen.py` — add early return when concept_id present
- `adapters/db/chat.py` — `set_chat_session_title_if_missing()` passes concept info

**Exit criteria:**
- Sessions with concept_id → title = concept name
- Sessions without concept_id → existing heuristic still works
- Tests cover both paths

---

### S1.4 — Scope concept resolver to bound topic subtree

**What:** When a session has a bound `concept_id`, the concept resolver should only resolve to subtopics/granular nodes that are descendants of that concept. Filter candidate concepts by checking ancestry in the graph.

**Files to change:**
- `domain/chat/concept_resolver.py` — `resolve_concept_for_turn()` accepts session's `concept_id`, filters candidates to descendants
- Possibly `adapters/db/graph.py` or similar — query to get descendant concept IDs

**Exit criteria:**
- Resolver only returns concepts within bound topic's subtree
- Resolver still works for unbound sessions (no filtering)
- Tests cover scoped resolution

---

### S1.5 — Repurpose ConceptSwitchSuggestion

**What:** When resolver detects user interest in an unrelated topic (outside bound topic's subtree), instead of suggesting in-place switch, suggest "Start a new chat about X". Update the suggestion schema and frontend handling.

**Files to change:**
- `domain/chat/concept_resolver.py` — change suggestion type/action
- `core/schemas/chat.py` — update `ConceptSwitchSuggestion` or add `action` field
- Frontend: `concept-switch-banner.tsx` — change "Switch" to "Start new chat" action

**Exit criteria:**
- Out-of-scope topic → "Start new chat" suggestion (not "Switch")
- In-scope subtopic → normal resolution (no suggestion)
- Frontend navigates to new chat creation with pre-selected topic

---

### S1.6 — Frontend: Session creation with concept_id

**What:** Update the frontend session creation flow to pass `concept_id` when creating a new chat. When user selects a topic from the graph or sidebar, create session bound to that concept.

**Files to change:**
- `apps/web/lib/tutor/chat-session-context.tsx` — pass `concept_id` in create request
- `apps/web/lib/api/types.ts` — update session creation types
- `apps/web/hooks/use-tutor-page.ts` — wire concept selection to session creation

**Exit criteria:**
- New chats created from topic selection include `concept_id`
- Session title displays correctly from bound concept
- Existing "New Chat" without topic still works

---

### S1.7 — Fix buggy topic display

**What:** Derive `currentConcept` from the session's bound `concept_id` on page load, not from first-turn resolution. Eliminate the race condition where `currentConcept` is sometimes null.

**Files to change:**
- `apps/web/hooks/use-tutor-page.ts` — initialize `currentConcept` from session's `concept_id`
- `apps/web/app/(app)/tutor/page.tsx` — ensure header always shows bound topic

**Exit criteria:**
- Topic always displays on page load for bound sessions
- No flickering or missing topic display
- Refresh always shows correct topic

---

## Removal Ledger

(Populated during implementation)

## Audit Workspace

(Initially empty — populated during audit cycles)
