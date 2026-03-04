# CoLearni Landing/Auth Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-landing-auth-reset.md`

Template source:
- `docs/prompt_templates/refactor_plan.md`

## Plan Completeness Checklist

This active plan should be treated as invalid if any of the following are missing:

1. archive snapshot references
2. current verification status
3. ordered remaining slices with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` with:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps
   - Observed outcome
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk outside the scope below, STOP and update this plan before widening scope.
7. Keep this pass narrow:
   - public landing page
   - public auth shell/login polish
   - protected shell separation required to support those pages
8. This document is incomplete unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by a fenced code block containing the execution prompt

## Purpose

This document is the active execution plan for the landing page and login UI work requested on 2026-02-28.

It is intentionally separate from `docs/REFACTOR_PLAN.md`. The repo-wide refactor plan already has a completed closeout record there, so this narrower frontend/auth work should live in its own task-specific plan file.

This new plan exists because the current repo still has three focused gaps:

- `/` is only a redirect gate, not a real landing page
- `/login` is functional but not shipping-ready
- the authenticated shell wraps public routes, which makes landing/auth UX awkward and tightly coupled to auth state

## Inputs Used

This plan is based on:

- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-landing-auth-reset.md`
- `docs/prompt_templates/refactor_plan.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/FRONTEND.md`
- current repository layout and verification status as of 2026-02-28

## Executive Summary

The broader repo refactor is already in good shape. Shared CSS tokens exist, the auth API flow is already wired, and the protected app shell works once a user is signed in.

What is still materially missing is narrow and user-facing:

1. a branded public homepage that explains CoLearni and converts users into the auth flow
2. a clean separation between public pages and the authenticated sidebar shell
3. a login experience that uses the repo's real design system, keeps the current mock magic-link flow, and feels ready to ship

The remaining work should stay narrow because the backend contracts are already sufficient. This pass should only reshape the web entry surfaces and the minimum supporting layout/auth structure.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. Keep the current auth API contract unchanged:
   - `requestMagicLink(email)`
   - `verifyMagicLink(token)`
   - current mock/debug token behavior stays in place
2. Do not introduce Tailwind or a new UI dependency:
   - use the existing CSS token system and shared styles
3. Keep protected route URLs and behavior stable:
   - `/tutor`
   - `/graph`
   - `/kb`
4. Preserve current session/workspace storage keys and login redirect target:
   - `colearni_session_token`
   - `colearni_active_workspace`
   - successful auth still lands on `/tutor`
5. Add tests for each new user-visible behavior change and keep the slice size small.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `PREV-RF` Repo-wide backend/frontend refactor closeout remains in `docs/REFACTOR_PLAN.md`
- `PREV-CSS` Shared token, base, shell, sidebar, graph, KB, and tutor CSS split already landed
- `PREV-AUTH` Mock magic-link auth API client and auth context session persistence are already wired

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `LA1` Public/protected shell split
- `LA2` Landing homepage
- `LA3` Shipping-ready login screen

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. `/login` remains the single destination for both "Sign up" and "Log in" CTAs until a dedicated onboarding flow exists.
2. The current mock/debug magic-link flow remains intact; this pass is UI/UX only, not auth backend work.
3. Public routes must not render the authenticated global sidebar shell.
4. Returning authenticated users may be redirected from public pages back to `/tutor` after auth rehydration.
5. Shared/reusable public auth UI should be testable without requiring a browser-only test harness.

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion:
   - deprecate -> route through facade/shim -> migrate callers -> delete
3. For deletions larger than trivial dead code, capture:
   - previous import/call sites
   - replacement module path
   - tests or checks proving parity
4. If a public route, payload, or CSS contract is being removed, include a compatibility note and rollback path in the slice verification block.
5. Maintain a removal ledger in this file during the run.

## Removal Entry Template

Use this exact structure for every meaningful removal:

```text
Removal Entry - <slice-id>

Removed artifact
- <file / function / route / schema / selector>

Reason for removal
- <why it was dead, duplicated, or replaced>

Replacement
- <new file/module/path or "none" if true deletion>

Reverse path
- <exact steps to restore or revert>

Compatibility impact
- <public/internal, none/minor/major>

Verification
- <tests or manual checks proving the replacement works>
```

## Current Verification Status

Current repo verification status:

- `pytest -q`: passing
- `npm --prefix apps/web test`: passing (`9` files, `58` tests)
- `npm --prefix apps/web run typecheck`: passing

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `apps/web/app/page.tsx` | `26` | Current `/` route is only a loading redirect and provides no public landing experience. |
| `apps/web/app/login/page.tsx` | `140` | Login UX is basic and relies on utility classes not backed by this repo's styling system. |
| `apps/web/app/layout.tsx` | `21` | Root layout wraps all routes in the authenticated shell, including public auth pages. |
| `apps/web/components/global-sidebar.tsx` | `118` | Sidebar currently assumes protected-route auth requirements and is mounted from the root layout. |
| `apps/web/lib/auth/auth-context.tsx` | `153` | Session restoration and login/logout redirects constrain how public pages should behave. |

## Remaining Work Overview

### 1. Public route shell separation

The app currently mounts the global sidebar shell at the root layout level. That makes `/` and `/login` inherit protected navigation concerns and blocks a clean public-facing experience.

### 2. Landing homepage

The current homepage immediately redirects, so there is no branded entry page explaining the product or guiding the user into auth.

### 3. Login UX and auth polish

The current login form works, but it is visually basic, uses classes that are not aligned with the repo's CSS system, and does not yet feel production-ready.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### LA1. Slice 1: Public/protected shell split

Purpose:

- separate public routes from the authenticated app shell without changing protected route URLs

Root problem:

- the root layout mounts `GlobalSidebar` for every route, but `GlobalSidebar` itself is protected-route behavior and should not own the public landing/auth experience

Files involved:

- `apps/web/app/layout.tsx`
- `apps/web/app/(app)/layout.tsx`
- `apps/web/app/(public)/layout.tsx`
- `apps/web/app/page.tsx` or `apps/web/app/(public)/page.tsx`
- `apps/web/app/login/page.tsx` or `apps/web/app/(public)/login/page.tsx`
- `apps/web/app/tutor/page.tsx`
- `apps/web/app/graph/page.tsx`
- `apps/web/app/kb/page.tsx`
- `apps/web/components/global-sidebar.tsx`

Implementation steps:

1. Introduce route-group layouts so public pages render without the app shell while protected pages keep the existing sidebar/content structure.
2. Move the existing protected pages under the protected layout group without changing their URLs.
3. Keep auth guarding on protected pages and remove public-route dependence on sidebar-mounted auth checks.

What stays the same:

- authenticated app URLs remain `/tutor`, `/graph`, and `/kb`
- `AuthProvider` and chat session provider stay global unless a slice proves otherwise
- sidebar behavior for signed-in users remains intact

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`

Exit criteria:

- logged-out users can reach public routes without rendering the sidebar
- logged-out users hitting `/tutor`, `/graph`, or `/kb` still get redirected to `/login`

### LA2. Slice 2: Landing homepage

Purpose:

- replace the redirect-only home route with a branded landing page that routes both sign-up and login intent into `/login`

Root problem:

- the product has no public homepage, so new users get no product framing and no conversion-focused entry surface

Files involved:

- `apps/web/app/(public)/page.tsx`
- `apps/web/components/public/landing-page.tsx`
- `apps/web/components/public/landing-page.test.tsx`
- `apps/web/styles/public-entry.css`
- `apps/web/app/globals.css`

Implementation steps:

1. Build a dedicated landing-page component using the existing token system and CoLearni brand assets.
2. Add clear "Sign up" and "Log in" CTAs that both point to `/login`.
3. Preserve a returning-user path by redirecting authenticated users from the public homepage back to `/tutor` after rehydration.

What stays the same:

- `/` remains the public root route
- backend APIs and auth contracts remain unchanged
- CTA destination is `/login` for both entry actions

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web test -- components/public/landing-page.test.tsx`

Exit criteria:

- `/` renders a real landing page for logged-out users
- both primary CTAs route to `/login`
- returning signed-in users are not stranded on the landing page

### LA3. Slice 3: Shipping-ready login screen

Purpose:

- rebuild `/login` into a polished two-step auth surface while keeping the current mock magic-link flow

Root problem:

- the current login screen is functional but visually minimal, not aligned with the repo's CSS system, and not structured for stable UI verification

Files involved:

- `apps/web/app/(public)/login/page.tsx`
- `apps/web/components/public/auth-shell.tsx`
- `apps/web/components/public/auth-shell.test.tsx`
- `apps/web/components/public/login-card.tsx`
- `apps/web/components/public/login-card.test.tsx`
- `apps/web/styles/public-entry.css`
- `apps/web/lib/auth/auth-context.tsx`

Implementation steps:

1. Extract presentational public auth components that can be render-tested with the current Vitest setup.
2. Rebuild the login screen with production-ready layout, copy, step guidance, error handling, and explicit dev-token messaging.
3. Preserve the existing request/verify calls and make sure both already-authenticated visitors and newly-verified users land on `/tutor`.

What stays the same:

- auth requests still call `apiClient.requestMagicLink` and `apiClient.verifyMagicLink`
- session persistence keys remain unchanged
- successful verification still logs the user in and routes to `/tutor`

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web test -- components/public/auth-shell.test.tsx components/public/login-card.test.tsx`

Exit criteria:

- `/login` feels visually complete on desktop and mobile
- current mock/debug token flow still works
- error, busy, and alternate entry copy states are covered by tests or manual smoke checks

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `LA1` Public/protected shell split
2. `LA2` Landing homepage
3. `LA3` Shipping-ready login screen

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Block Template

For every completed slice, include this exact structure in the working report or PR note:

```text
Verification Block - <slice-id>

Root cause
- <what made this area hard to maintain?>

Files changed
- <file list>

What changed
- <short description of the refactor moves>

Commands run
- <tests / typecheck / lint commands>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
```

Run these additionally when relevant:

```bash
ruff check .
```

Slice-specific emphasis:

- `LA1`
  - verify public pages render without `GlobalSidebar`
  - verify protected pages still redirect anonymous users to `/login`
- `LA2`
  - verify both landing-page CTAs point to `/login`
  - verify authenticated-home redirect logic does not break the logged-out render path
- `LA3`
  - verify request/verify loading and error states
  - verify debug-token messaging remains visible only when returned by the API

Manual smoke checklist:

1. Open `/` while logged out and confirm the landing page renders without the sidebar.
2. Use either landing CTA and confirm it opens `/login`.
3. Complete the mock login flow and confirm the app lands on `/tutor` with the protected shell.

## What Not To Do

Do not do the following during the remaining refactor:

- do not change backend auth endpoints, payload shapes, or mock-token semantics
- do not introduce Tailwind, a component library, or another styling dependency
- do not redesign protected tutor/graph/kb screens beyond the layout extraction needed for public-route separation

## Removal Ledger

None yet.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If a generated plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the remaining implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/LANDING_AUTH_PLAN.md now. This file is the source of truth.
You MUST implement refactor slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/LANDING_AUTH_PLAN.md using the Removal Entry Template.
For every removal, include:
Removed artifact
Reason for removal
Replacement
Reverse path
Compatibility impact
Verification

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade/shim instead of deleting immediately.
- Do not delete public contracts without a compatibility note and rollback path.
- Do not claim the removal is complete until the replacement behavior is verified.

After every 2 slices OR if your context is compacted/summarized, re-open docs/LANDING_AUTH_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/LANDING_AUTH_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/LANDING_AUTH_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/LANDING_AUTH_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
