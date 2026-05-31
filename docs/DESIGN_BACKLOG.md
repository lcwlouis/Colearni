# CoLearni Design Backlog

This file tracks UI surfaces that need intentional design work. Items are ordered by dependency — things that share the same data or layout context are grouped together.

---

## 1. Trail Detail Header

**Current state:** The trail detail page has a top header row showing "Colearni" (as a back-link), the trail title below it, and "Delete Trail / N concepts" on the right. With the persistent sidebar now present, the "Colearni" back-link is redundant and the overall header layout needs rethinking.

**Needs design:**
- Breadcrumb: `Home > Trails > {trail title}` or just `Trails > {trail title}`
- Trail title as the page h1 (large, left-aligned)
- Learn / Inspect mode toggle — where it lives relative to the title
- Trail actions (Delete, concept count badge) — deemphasised, right-aligned or in a `…` menu
- How this header interacts with the graph canvas below it (does it scroll away? stay fixed?)

---

## 2. Node Hover Card — Add Primer Overview

**Current state:** Hovering a node shows a tooltip card with: Title, Level, Type, Bloom, Difficulty, Status.

**Needs design:**
- If the concept has a cached primer (`metadata_json.primer.overview`), show the overview paragraph below the metadata row
- If no primer is cached, hover card stays as-is — no generation trigger on hover
- The primer text can be long (2–4 sentences) so the card needs a max-height or truncation strategy
- Visual weight: the overview text should feel secondary to the title, not equal

**Constraint:** Primer data is already present on each `ConceptNode` loaded with the trail — no extra API call needed.

---

## 3. Concept Panel — Tabs + Next Actions

**Current state:** The concept panel shows flat metadata badges, then an Overview section (primer overview + key terms), then related nodes (prerequisites, contains, related), then sources, then action buttons at the bottom (Continue Tutor / Practice / Level Up / View past attempts).

**Needs design:**

### Tab structure
Three tabs: **Overview** · **Details** · **Sources**

- **Overview tab** (default): primer overview paragraph + key terms + sample questions (current primer section). Keep related graph links (prerequisites, contains, related) here or move to Details.
- **Details tab**: full metadata (Bloom level, difficulty, node type, concept level), mastery check labels, raw prerequisite/contains/related node lists with links.
- **Sources tab**: list of linked source documents with file type badge (PDF, PPTX, etc.), upload CTA if no sources yet.

### Mastery display
Replace the flat "Learning" badge with a more visual mastery indicator:
- Percentage completion ring or progress arc (e.g. 65%)
- Status label ("Learning", "Needs Review", "Mastered") alongside it
- Short encouraging copy below ("Keep it up! You're making progress.")

### Next Actions list
Replace the current 3-button toolbar (Open Tutor / Practice / Level Up) with a structured list:

| Mastery state | Actions shown |
|---|---|
| `not_started` | Start Learning (primary) |
| `learning` | Continue with tutor · Take level-up quiz |
| `needs_review` | Review weak points (tutor) · Retry quiz |
| `mastered` | Practice · Explore further |

Each action has an icon, a label, and a short description line (e.g. "Keep learning with Socratic questions").

> **Update (post-Phase 15):** the concept action row now also includes **Artifacts** (worked example / comparison / timeline / mini-graph / simulation slider) and **Flashcards** (recall-first review deck), plus tutor-suggested `suggest_quiz` / `suggest_artifact` CTAs that switch into those panels. The redesigned Next-Actions list must incorporate Artifacts + Flashcards (and the "View past attempts" history entry) — not just Tutor/Practice/Level Up — so this redesign should happen *after* Phase 15 (now shipped), which is why it was intentionally not folded into the Phase 15 implementation pass (it edits the same `ConceptPanel.tsx` surface).

---

## 4. Graph Stats Bar — Always Visible

**Current state:** The concept breakdown (Total / New / Learning / Needs review / Mastered) is only visible inside the **Inspect mode → Tools** panel.

**Needs design:**
- A persistent stats bar at the bottom of the graph canvas, visible in both Learn and Inspect modes
- Compact: 5 metrics in a single row (Total · New · Learning · Needs review · Mastered) with counts
- Should not overlap the graph zoom controls (bottom-left) — position bottom-center or bottom-right
- Updates reactively when mastery changes (already the case for the data; just needs a persistent render location)

---

## 5. Dashboard Redesign

**Current state:** Dashboard has a "Learning Dashboard" h1 with a subtitle, then Continue Learning, then Recent Trails grid, then Older Trails search/list. The sidebar now handles all navigation, so the page should feel more like a home screen and less like a nav page.

**Needs design:**

### Welcome header
- Personalised: "Welcome back, Louis! 👋" (name from localStorage or workspace name)
- Optional: day streak + XP bar pulled from `UserProfileChip` state — gives the page life without a full gamification backend

### Quick actions row
Four action chips below the welcome message:
- **Review weak areas** — concepts with `needs_review` status (show count)
- **Level up quiz** — concepts with `learning` status that have no pending quiz
- **Explore adjacent** — links to the graph of the in-progress trail
- **Ask anything** — opens tutor on the recommended next concept

### Trail cards
Replace the current mixed Recent + Older layout with a tabbed card grid:
- Tabs: **All · In Progress · Completed · Pinned**
- Each card: trail title, progress bar (3-colour mastery), `X / Y concepts`, last-active timestamp
- "Create New Trail" card at the end of the grid (dashed border, + icon)
- Pinning is a future feature — tab can exist but be non-functional for now

---

## Implementation Order (suggested)

These are design-only recommendations — implementation order may differ based on what's actively being worked on.

1. **Trail header** — unblocks the rest; every trail page visit sees this
2. **Stats bar** — small, self-contained, high visibility
3. **Hover card primer** — small change, high value for returning learners
4. **Concept panel tabs** — medium scope, high learner impact
5. **Dashboard** — last, since it depends on the sidebar feeling settled first
