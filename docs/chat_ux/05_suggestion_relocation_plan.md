# CUX5 — Suggestion Relocation

Parent plan: `docs/chat_ux/CUX_MASTER_PLAN.md`
Last updated: 2026-03-05

## Purpose

Move the concept-switch banner (adjacent/wildcard topic suggestions) from the inline chat area to the sidebar panel. Per CUX1's decision, these suggestions now say "Start a new chat about X" instead of "Switch topic". The sidebar provides a less disruptive location for these suggestions.

## Dependencies

- Depends on `CUX3` (Header & Navigation Refactor) — the sidebar must exist with the single-toggle pattern before suggestions can be relocated there.
- Depends on `CUX1` (Chat-Topic Binding) — suggestion action is "Start new chat" not "Switch".

## Slices

### S5.1 — Remove ConceptSwitchBanner from chat timeline

**What:** Remove the `<ConceptSwitchBanner>` component from its current position in the chat timeline area. The suggestion data still flows through the same state — only the rendering location changes.

**Files to change:**
- `apps/web/app/(app)/tutor/page.tsx` — remove `<ConceptSwitchBanner>` from the chat area

**Exit criteria:**
- No suggestion banner appears in the chat timeline
- Suggestion state (`switchSuggestion`) still tracked in `useTutorPage`
- No dead imports or orphaned code

**Removal entry required:** Yes (moving component location)

---

### S5.2 — Add suggestions section to sidebar

**What:** Add a "Suggested Topics" section to the sidebar that displays active `ConceptSwitchSuggestion`. Shows the suggested concept name, the reason for the suggestion, and a "Start new chat" button.

**Files to change:**
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — add suggestions section (above or below tabs)
- `apps/web/hooks/use-tutor-page.ts` — expose suggestion state to slideover

**Exit criteria:**
- Suggestion appears in sidebar when available
- Shows concept name and reason
- "Start new chat" button creates new session with suggested concept_id
- Section hidden when no active suggestion

---

### S5.3 — Restyle suggestion as sidebar card

**What:** Style the suggestion as a sidebar card that fits the sidebar's visual language. Not an inline banner — a card with rounded corners, subtle background, concept name, reason text, and action button.

**Files to change:**
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — card styling
- CSS/styles for suggestion card

**Exit criteria:**
- Card visually consistent with sidebar design
- Responsive within sidebar width
- Dismissible (X button or "Dismiss" link)
- After dismiss, card removed until next suggestion arrives

---

## Removal Ledger

(Populated during implementation)

## Audit Workspace

(Initially empty — populated during audit cycles)
