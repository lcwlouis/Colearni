# CUX3 — Header & Navigation Refactor

Parent plan: `docs/chat_ux/CUX_MASTER_PLAN.md`
Last updated: 2026-03-05

## Purpose

Clean up the tutor chat top bar: show the chat title (derived from bound topic per CUX1) instead of the static "Tutor Chat" text, remove the level-up quiz button from the header, and collapse the multiple slideover trigger buttons into a single hamburger/info toggle.

## Dependencies

- Depends on `CUX1` (Chat-Topic Binding) — the header title comes from the session's bound topic.

## Slices

### S3.1 — Replace "Tutor Chat" with session title

**What:** The header currently shows a hardcoded "Tutor Chat" string. Replace it with the session's title (which is the bound concept's name per CUX1). Fall back to "New Chat" if no title is set.

**Files to change:**
- `apps/web/app/(app)/tutor/page.tsx` — replace `<span>Tutor Chat</span>` with dynamic title
- `apps/web/hooks/use-tutor-page.ts` — expose session title for header consumption

**Exit criteria:**
- Header shows concept name for bound sessions
- Header shows "New Chat" for unbound/new sessions
- Title updates when switching between sessions in sidebar

---

### S3.2 — Remove level-up quiz button from header

**What:** Remove the "Level-up quiz" / "Hide quiz" toggle button from the top bar. Level-up quizzes are accessible from the sidebar practice tab instead.

**Files to change:**
- `apps/web/app/(app)/tutor/page.tsx` — remove the quiz button from header actions

**Exit criteria:**
- No "Level-up quiz" button in header
- Quiz functionality still accessible from sidebar practice tab
- No dead code left behind (remove associated click handlers if orphaned)

**Removal entry required:** Yes (removing header button)

---

### S3.3 — Collapse slideover triggers into single toggle

**What:** Replace the separate "Show graph", "Level-up quiz", and "Practice" buttons in the header with a single hamburger or info icon button that toggles the sidebar open/closed.

**Files to change:**
- `apps/web/app/(app)/tutor/page.tsx` — replace multiple buttons with single toggle
- `apps/web/hooks/use-tutor-page.ts` — simplify to single `toggleSidebar()` instead of `openDrawer(tab)`

**Exit criteria:**
- Single icon button in header toggles sidebar
- Sidebar opens to last-used tab or default
- No "Show graph" / "Practice" individual buttons in header
- Icon visually indicates open/closed state (e.g., hamburger ↔ X)

---

### S3.4 — Sidebar tab persistence

**What:** When the sidebar is opened via the toggle, it should open to the last-used tab. Persist the last active tab in component state (not localStorage — just session-level).

**Files to change:**
- `apps/web/hooks/use-tutor-page.ts` — track `lastActiveTab` state, use it as default when opening
- `apps/web/features/tutor/components/tutor-slide-over.tsx` — respect default tab on open

**Exit criteria:**
- Sidebar opens to previously viewed tab
- Default is "graph" tab for first open
- Tab state doesn't persist across page refreshes (session-level only)

---

## Removal Ledger

(Populated during implementation)

## Audit Workspace

(Initially empty — populated during audit cycles)
