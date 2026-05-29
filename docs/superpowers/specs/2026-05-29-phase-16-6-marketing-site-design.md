# Phase 16.6 — Product / Marketing Site (Design)

Status: approved (2026-05-29)
Scope: `apps/web/` (Next.js frontend). No backend changes.

## Goal

A public-facing product/marketing site alongside the app so prospective users
understand what CoLearni is before entering the workspace. Per
`docs/REBUILD_PLAN.md` Phase 16.6.

## Decisions (locked)

1. **Routing:** Marketing owns `/` with a workspace-aware redirect. Returning
   users (those with a `colearni_workspace_id` in localStorage) are redirected
   from `/` to `/dashboard`.
2. **Relocation:** The current learning dashboard (`app/page.tsx`) moves to
   `app/dashboard/page.tsx`. `/trails/*` routes are unchanged.
3. **Aesthetic:** Elevated, same family — stay in the app's slate + blue/emerald
   palette but push the marketing pages further (distinctive display font,
   graph-motif hero, editorial whitespace, scroll-reveal motion).
4. **Theme:** Light + dark, following `prefers-color-scheme` (no manual toggle).
   Scoped to the marketing surface only; the app's global dark mode is not yet
   built and must not be disturbed.
5. **Contact:** Info card only — email + community links, no form, no backend.

## Architecture & Routing

Next.js App Router with a `(marketing)` route group (parentheses = no URL
segment):

```
app/
  layout.tsx                  # root: fonts only (add Fraunces), body unchanged
  (marketing)/
    layout.tsx                # marketing nav + footer + themed wrapper
    page.tsx                  # "/"  Home (workspace-aware redirect gate)
    how-it-works/page.tsx     # "/how-it-works"
    pedagogy/page.tsx         # "/pedagogy"
    pricing/page.tsx          # "/pricing"  (TBC)
    contact/page.tsx          # "/contact"  (info card)
  dashboard/page.tsx          # MOVED verbatim from app/page.tsx
  trails/...                  # unchanged
components/marketing/         # Nav, Footer, GraphHero, SectionReveal, ProductPreview, etc.
lib/enter-app.ts              # fake-login helper
```

### Relocation details (minimal)

- `app/page.tsx` → `app/dashboard/page.tsx` (content unchanged).
- Internal "home/dashboard" links change `/` → `/dashboard`:
  - `app/trails/page.tsx:220`
  - `app/trails/[id]/page.tsx:137`, `:154`
- `__tests__/dashboard.test.tsx` dynamic `import("@/app/page")` →
  `import("@/app/dashboard/page")`.
- Nothing else in the product tree moves.

## Aesthetic System ("elevated, same family")

- **Type:** Keep **Geist Sans** (body/UI) and **Geist Mono** (eyebrows/labels).
  Add **Fraunces** (next/font/google) as the display face for headlines,
  exposed as `--font-fraunces`. Distinctive, editorial, mentor-like;
  deliberately not Space Grotesk.
- **Color:** Slate base, `blue-600` primary. Reuse **emerald/amber** as a
  decorative "mastery spectrum" (mastered → learning → review). Light mode uses
  a faintly warm paper off-white; dark mode uses `slate-950`.
- **Signature motif:** the **concept graph**. Hero is an animated SVG
  constellation of concept nodes joined by prerequisite edges that light up
  emerald → blue → amber along a path, echoing the real product. This is the
  memorable element.
- **Motion (CSS-first, no new deps):** one orchestrated page-load with staggered
  reveals (`animation-delay`); scroll-reveal via a small `IntersectionObserver`
  hook; node pulse on the hero graph; subtle hover-lift on cards. No Motion
  library (not in the stack).
- **Texture:** soft layered gradients, faint grain/noise overlay, hairline
  borders. Restrained, not maximalist.

## Theming (light + dark, follow system)

- Tailwind v4's `dark:` variant keys off `prefers-color-scheme` by default —
  use `dark:` utilities throughout the marketing pages.
- Apply a full-bleed themed background wrapper in the **marketing layout only**
  so the root body (`bg-slate-50`) never shows through in dark mode.
- Add light/dark CSS variables for the marketing surface in `globals.css`,
  scoped to a marketing class so the product UI is untouched.
- No theme toggle.

## Pages

- **Home:** graph hero + one-line value prop; centered primary CTA
  **"Start learning free"**; a stylized in-CSS **product preview** (graph + a
  faux tutor exchange — built, not a screenshot); a 3–4 step "how it works"
  strip; a pedagogy teaser; footer CTA.
- **How it works:** the demo loop as numbered steps — create a Trail → graph
  builds → click a concept → Socratic tutor → level-up quiz → mastery updates.
  Placeholder media frames styled as product shots.
- **Pedagogy:** the real teaching story, each as its own explained section —
  **Bloom's Taxonomy as the target-depth dial**, Socratic questioning, Bloom
  mastery learning, active recall / retrieval practice, scaffolding along the
  prerequisite graph.
- **Pricing:** three anticipated tiers — **self-host / open-source**,
  **free hosted**, **paid hosted** — every card stamped **"TBC"**, no numbers.
  License note: source-available, commercial starter advantage, intentionally
  **not MIT**, exact license to be chosen (no specific license named).
- **Contact:** info card only — email address, a short "we'd love to hear from
  you" message, GitHub/community links. No form, no backend, no secrets.

## Fake Login + Redirect

- `lib/enter-app.ts → enterApp(router)`: `await ensureWorkspaceId()` (reuses the
  existing localStorage `colearni_workspace_id`, creating one via the API on
  first click — the "sign up" moment), then `router.push("/dashboard")`. Used by
  the header **"Log in"** button and the Home CTA, with a pending state.
- **Redirect gate** on `/` only: a small client component checks `localStorage`
  on mount; if a workspace id exists, `router.replace("/dashboard")` so
  returning visitors skip the landing. Other marketing pages stay readable by
  everyone.

## Tests (Vitest + Testing Library, matching `__tests__/`)

- Each marketing route renders its key heading with **no workspace** in
  localStorage (public, workspace-free).
- `enterApp` / "Log in" calls `ensureWorkspaceId` and routes to `/dashboard`
  (mocked router + api).
- Home redirects to `/dashboard` when a workspace id is already present
  (mocked `router.replace`).
- Pages render without crashing under a **dark** `matchMedia` mock, asserting
  the theme-aware wrapper is present.
- Updated `dashboard.test.tsx` passes against the moved page.

## Non-goals (per plan)

- No real authentication, accounts, or billing (Phase 18).
- No public pack marketplace.
- No committed pricing numbers or final license text.
- No real screenshots/GIFs yet (built-in-CSS previews stand in; GIFs can come
  later).

## Notes / assumptions

- Display font: **Fraunces** (designer's call, approved).
- Product preview is built in CSS/SVG rather than captured screenshots for this
  phase.
