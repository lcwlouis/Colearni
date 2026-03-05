# CUX2 — Topic Hierarchy Awareness

Parent plan: `docs/chat_ux/CUX_MASTER_PLAN.md`
Last updated: 2026-03-05

## Purpose

The agent must know the full hierarchy path (umbrella → topic → subtopic) when the user is exploring a subtopic. The `retrieval_context.py` already has `build_ancestor_context()` — this needs to be reliably included in every turn's context. The frontend must display the hierarchy breadcrumb showing where the current conversation sits in the concept tree.

## Dependencies

- Depends on `CUX1` (Chat-Topic Binding) — the bound concept determines the hierarchy root.

## Slices

### S2.1 — Ensure ancestor context always included in prompt

**What:** `build_ancestor_context()` in `retrieval_context.py` is currently only called for subtopic/granular tiers. Ensure it is always called for the active concept (the per-turn resolved concept) and the result is injected into the system prompt. Also ensure the bound session topic is always referenced.

**Files to change:**
- `domain/chat/retrieval_context.py` — ensure `build_ancestor_context()` is called unconditionally for the active concept
- `domain/chat/stream.py` or prompt assembly code — inject hierarchy context into system prompt

**Exit criteria:**
- Every turn's system prompt includes hierarchy context
- For topic-tier concepts, context shows "Topic: X (under Umbrella: Y)"
- For subtopic-tier, shows full chain
- Tests verify prompt includes hierarchy

---

### S2.2 — Add hierarchy_path to response metadata

**What:** Add `hierarchy_path` field to the chat response stream metadata. This is a list of `{concept_id, name, tier}` objects representing the path from the umbrella root down to the currently active concept.

**Files to change:**
- `core/schemas/chat.py` — add `HierarchyNode` schema and `hierarchy_path` to response metadata
- `domain/chat/stream.py` — compute and include hierarchy path in final response
- `adapters/db/graph.py` or equivalent — query to get ancestor chain for a concept

**Exit criteria:**
- Response metadata includes `hierarchy_path` array
- Path is ordered root → leaf (umbrella → topic → subtopic → granular)
- Empty/single-node path for top-level concepts
- Tests verify hierarchy path construction

---

### S2.3 — Frontend: Display hierarchy breadcrumb

**What:** Display the hierarchy path as a breadcrumb in the sidebar info panel. Format: "Machine Learning › Neural Networks › Backpropagation". Each segment shows the concept name.

**Files to change:**
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — add breadcrumb component to info section
- `apps/web/lib/api/types.ts` — add `HierarchyNode` type and `hierarchy_path` to response types
- New component: `apps/web/components/hierarchy-breadcrumb.tsx` (if warranted)

**Exit criteria:**
- Breadcrumb displays in sidebar when hierarchy data available
- Updates on each turn as active concept may change
- Graceful fallback when no hierarchy (single topic)

---

### S2.4 — Agent prompt: Inject hierarchy awareness

**What:** Update the system prompt template to explicitly state: "Current session topic: {topic}. The user is currently exploring: {active_concept} (hierarchy: {umbrella} → {topic} → {subtopic})". This gives the agent context about where in the topic tree the conversation is.

**Files to change:**
- Prompt template files (system prompt for tutor agent)
- `domain/chat/retrieval_context.py` — format hierarchy string for prompt injection

**Exit criteria:**
- Agent system prompt includes explicit hierarchy context
- Agent responses acknowledge subtopic context when relevant
- Tests verify prompt formatting

---

## Removal Ledger

(Populated during implementation)

## Audit Workspace

(Initially empty — populated during audit cycles)
