# Frontend Guidelines

## Purpose

This file is required reading when touching `apps/web/`. The current project was reset for the new MVP, so old frontend component inventories and old Sigma-specific assumptions should not be treated as current implementation.

## Product Surface

The first frontend should support the core demo loop:

```text
create Trail
-> view graph
-> click concept
-> chat with tutor
-> take level-up quiz
-> see mastery status update
-> export/import safe Trail Pack
```

Do not build a marketing landing page as the main experience. The first screen should help the learner create or open a Trail.

## Planned Stack

- Next.js with TypeScript.
- Tailwind and a small component system.
- React Flow for the MVP graph unless Sigma.js is reintroduced intentionally.
- KaTeX for math rendering when needed.
- Vitest or the repo-standard frontend test runner once scaffolded.

## Graph UI Requirements

Concept graph nodes have both mastery status and concept level.

Mastery statuses:

```text
not_started
learning
needs_review
mastered
```

Concept levels:

```text
umbrella
topic
subtopic
granular
```

The graph UI should:

- Visually distinguish concept levels without hiding mastery status.
- Support search.
- Support click-to-open side panel.
- Show prerequisites, containing nodes, contained nodes, related nodes, mastery checks, and sources.
- Stay usable at 100 nodes.
- Avoid layout shifts in graph controls and side panels.

## Interaction Guidelines

- Prefer dense, useful learning surfaces over decorative hero sections.
- Keep controls predictable: buttons for commands, tabs for views, toggles for binary settings, inputs/sliders for values.
- Use icons where they clarify common actions.
- Do not put cards inside cards.
- Ensure text does not overflow buttons, side panels, or graph overlays.
- Keep mobile layouts usable for Trail creation, concept details, chat, and quiz cards.

## API Access

The frontend should read `NEXT_PUBLIC_API_BASE_URL` and call the backend API documented in `docs/API.md`.

For the local-ready MVP, store the active `workspace_id` locally and include it in workspace-scoped API paths.

## Verification

When frontend code exists, run the available equivalents of:

```bash
cd apps/web
npm run typecheck
npm run test
```

If a visual graph or chat flow is changed, also run a browser check before claiming completion.
