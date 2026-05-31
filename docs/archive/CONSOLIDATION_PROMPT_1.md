# Agent Prompt: Consolidation Item 1 — Phase 12 UI

## Context

Read `docs/CONSOLIDATION_PLAN.md` Item 1 before proceeding.

The backend recommendation endpoint `GET /api/workspaces/{workspace_id}/trails/{trail_id}/next`
was built in Phase 12 and returns `NextConceptResponse`:

```json
{
  "concept_id": "uuid | null",
  "concept_title": "string | null",
  "reason": "string",
  "all_mastered": "bool"
}
```

It is currently called by nothing in the frontend. The dashboard and Trail detail page compute
recommendations entirely client-side using `apps/web/lib/recommendation.ts:pickRecommendedConcept`,
which duplicates the backend heuristic and can silently diverge.

Your job is to wire the frontend to use the backend endpoint and remove the duplicate client-side
heuristic.

---

## Mandatory reads before writing any code

- `docs/AGENTS.md` — repo rules, git policy, and constraints.
- `docs/CODEX.md` — code standards.
- `docs/FRONTEND.md` — frontend guidelines and stack.
- `apps/web/AGENTS.md` — Next.js version note (read the relevant Next.js guide in
  `node_modules/next/dist/docs/` before touching Next.js APIs).
- `apps/web/lib/recommendation.ts` — the client-side heuristic being replaced.
- `apps/web/lib/api.ts` — where to add the new API call.
- `apps/web/lib/types.ts` — where to add `NextConceptResponse`.
- `apps/web/app/page.tsx` — the dashboard that renders "Recommended next concept".
- `apps/web/app/trails/[id]/page.tsx` — the Trail detail page.
- `apps/web/app/trails/[id]/components/ConceptPanel.tsx` — concept panel CTAs.
- `backend/app/schemas/trail.py` — `NextConceptResponse` source of truth.

---

## Exact changes required

### 1. Add `NextConceptResponse` type to `apps/web/lib/types.ts`

Add the following type (mirror of `backend/app/schemas/trail.py:NextConceptResponse`):

```typescript
export interface NextConceptResponse {
  concept_id: string | null;
  concept_title: string | null;
  reason: string;
  all_mastered: boolean;
}
```

### 2. Add `getTrailNext()` to `apps/web/lib/api.ts`

Add a function that calls the backend endpoint:

```typescript
export async function getTrailNext(
  workspaceId: string,
  trailId: string,
): Promise<NextConceptResponse>
```

It should follow the same pattern as other GET calls in the file (JSON fetch, throw on non-ok,
return typed response). Import `NextConceptResponse` from `@/lib/types`.

### 3. Update `apps/web/app/page.tsx` — dashboard

The dashboard currently calls `getTrail()` for each trail in a `Promise.all` and then runs
`summarizeTrail()` client-side. `summarizeTrail` internally calls `pickRecommendedConcept`.

Change:

- In the parallel fetch, call `getTrailNext(workspaceId, trail.id)` alongside each `getTrail()`
  call. The workspace id is already available on each trail object.
- Replace the `progress.recommended` value used at lines ~252–274 (the "Recommended next
  concept" label, title, level badge, reason, and CTA href) with data from the
  `NextConceptResponse`. Map:
  - `concept_id` → use as the deep-link id (the `?concept=<id>` href)
  - `concept_title` → display as the recommended concept name
  - `reason` → display as the recommendation reason
  - `all_mastered` → if true, show an "All concepts mastered" state instead of a concept link
- The `TrailCard` secondary CTA (in the Recent Trails grid, currently also deep-linking to the
  client-side recommended concept) should use the same `NextConceptResponse` data.

Do **not** remove `summarizeTrail` — it is still used for the progress percentage bar, mastery
counts (not_started, learning, needs_review, mastered total), and `lastActivity`. Only the
`recommended` field inside `TrailProgress` (returned by `summarizeTrail`) is being replaced.
You may either remove the `recommended` field from `TrailProgress` entirely and use the backend
response separately, or keep it as a nullable field and stop populating it from the client side.
Choose the cleanest approach.

### 4. Update `apps/web/app/trails/[id]/page.tsx` — Trail detail page

The Trail detail page loads `TrailDetail` via `getTrail()` but does not currently surface any
recommendation. Add:

- A call to `getTrailNext()` on this page (or fetch it inside the graph/panel component if
  that is cleaner).
- Render the recommendation visibly somewhere in the Trail detail view. A simple banner or card
  above or below the graph showing "Recommended next: [concept title] — [reason]" with a
  deep-link button (`?concept=<id>`) is sufficient. If `all_mastered` is true, show "All
  concepts mastered — well done." instead.
- Do not show the banner if the API call fails or returns no result; degrade silently.

### 5. Remove `pickRecommendedConcept` from `apps/web/lib/recommendation.ts`

After the dashboard and Trail detail page use the backend endpoint:

- Delete `pickRecommendedConcept` and its supporting helpers (`statusPriority`, `levelPriority`,
  `difficultyPriority`, `prereqsSatisfied`, `RecommendedConcept` type, `buildReason`).
- Delete the `recommended` field from the `TrailProgress` type (or mark it removed).
- Keep `summarizeTrail`, `pickContinueTrail`, and `TrailProgress` — they are still used for
  progress percentages, mastery counts, Continue Learning trail selection, and last activity.

If removing `pickRecommendedConcept` causes TypeScript errors elsewhere, fix those too.

### 6. Update docs

- `docs/CURRENT_VARIANT.md`: remove "Guided graph focus controls and frontend recommendation
  consumption (Phase 12 UI half)" from the Deferred Work section, and add a note that frontend
  recommendation consumption is now live.
- `docs/REBUILD_PLAN.md`: update the Phase 12 status line to reflect that the UI half is
  complete.
- `docs/CONSOLIDATION_PLAN.md`: update Item 1 status from `pending` to `complete`.

---

## Tests

Run the full backend test suite and confirm it still passes:

```bash
cd backend && python -m pytest tests/ -q
```

Run the frontend typecheck:

```bash
cd apps/web && npx tsc --noEmit
```

If frontend unit tests exist for `recommendation.ts` or `page.tsx`, update them to cover the
new API call and the removal of `pickRecommendedConcept`. Add a test if none covers this area
and it is straightforward to do so.

---

## Constraints

- Do not commit or push. Stop after implementing and verifying. The user will review the diff.
- FastAPI routes must stay thin; no business logic changes on the backend side.
- Do not change `backend/app/services/recommendation.py`, `backend/app/api/trails.py`, or
  any backend file — this is a frontend-only change with doc updates.
- Keep changes under ~400 net LOC. If the work is larger than expected, stop and report why.
- No new npm dependencies without flagging to the user first.
- Follow the code style already in `apps/web/lib/api.ts` and `apps/web/app/page.tsx`.

---

## Deliverable

When done, report:

1. Which files were changed and a one-line summary of each change.
2. Backend test count (should be 349+).
3. Frontend typecheck result.
4. Any edge cases or decisions you made (e.g., how you handled the `all_mastered` state).
5. Any issues or partial scope that was not completed, with a reason.

The user will review before any commit is made.
