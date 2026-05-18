# Frontend Guidelines

## Purpose

This file is required reading when touching `apps/web/`. The current project was reset for the new MVP, so old frontend component inventories should not be treated as current implementation.

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
- **React Flow (`@xyflow/react`)** for the per-Trail graph viewer (see Graph Library section below).
- **`@assistant-ui/react`** for the tutor chat UI (see section below).
- KaTeX for math rendering when needed (available as an assistant-ui add-on).
- Vitest or the repo-standard frontend test runner once scaffolded.

## Graph Library: React Flow

The per-Trail concept graph is built with [`@xyflow/react`](https://github.com/xyflow/xyflow) and [`dagre`](https://github.com/dagrejs/dagre) for layout. This is the correct choice for the current use case and is already implemented.

### Why React Flow for per-Trail graphs

- Nodes render as React components, which makes rich per-node content (title, level badge, difficulty, mastery colour) straightforward.
- `dagre`'s hierarchical top-down layout suits the `umbrella → topic → subtopic → granular` structure better than force-directed physics.
- At 10–100 nodes (the per-Trail cap defined in `docs/GRAPH.md`), DOM-based rendering is completely comfortable.

### Known ceiling

React Flow is DOM-based. Pan and zoom trigger style recalculations across all rendered nodes. In practice, interactions become noticeably sluggish somewhere in the **300–500 node range**, and the experience degrades further beyond that. This is not a problem for per-Trail graphs, but it becomes relevant if a combined or workspace-level graph view is ever introduced.

### The Sigma.js trigger

If any view ever needs to display nodes from **more than one Trail simultaneously** — a workspace overview, a merged Trail, or a community graph — React Flow is the wrong tool for that surface. At that point, **Sigma.js should be adopted for that view** (WebGL-based, handles thousands of nodes with smooth pan/zoom). See `docs/CONSIDERED.md` for the full comparison and integration notes.

Do not pre-emptively switch the per-Trail graph to Sigma.js. The React Flow implementation is working and is the right fit at current scale.

## Tutor Chat UI: assistant-ui

The tutor chat panel is built on [`@assistant-ui/react`](https://github.com/assistant-ui/assistant-ui), an open-source MIT-licensed React/TypeScript library for production chat UIs. It provides:

- Composable `Thread`, `Message`, and `Composer` primitives (Radix-style, unstyled).
- A polished shadcn/ui themed starter installed directly into `apps/web/components/assistant-ui/` via the CLI — we own those files entirely.
- Streaming tokens, auto-scroll, markdown rendering, code highlighting, and accessibility out of the box.
- A `Sources` component designed to display URL-sourced citations, which maps directly to our source provenance model.
- Optional KaTeX add-on for math rendering in tutor messages.

### Why not the Vercel AI SDK

CoLearni calls its own FastAPI backend (`POST /api/tutor/chat`), not a Next.js route backed by the Vercel AI SDK. `assistant-ui` supports this via its **Custom Backend / `LocalRuntime`** pattern: we write a thin model adapter that handles the HTTP call, and the library manages all UI state.

### Custom Runtime Adapter

The adapter lives in `apps/web/lib/tutor-runtime.ts` and is the only integration glue we write:

```ts
import { useLocalRuntime, type ChatModelAdapter } from "@assistant-ui/react";

const CoLearniTutorAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/tutor/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages,
          concept_id: "...",   // injected from page context
          workspace_id: "...", // injected from localStorage
        }),
        signal: abortSignal,
      }
    );
    // For streaming: yield chunks as they arrive via SSE or chunked transfer.
    // For non-streaming: yield the full response in one shot.
    const text = await res.text();
    yield { content: [{ type: "text", text }] };
  },
};

export function useTutorRuntime() {
  return useLocalRuntime(CoLearniTutorAdapter);
}
```

The page wraps the chat panel in `<AssistantRuntimeProvider runtime={runtime}>` and renders the installed `<Thread />` component.

### Streaming Requirement

For a responsive Socratic experience, `POST /api/tutor/chat` should return a **streaming response** (SSE or chunked transfer). The adapter above can be upgraded to yield tokens incrementally by reading the response body as a `ReadableStream`. The UI will start rendering as soon as the first token arrives. If the endpoint is non-streaming initially, the adapter works without changes — the whole reply just appears at once.

### Customisation Points

The components copied into `apps/web/components/assistant-ui/` by the CLI are plain React/Tailwind files we fully own. CoLearni-specific customisations include:

- **Tutor mode badge**: display the active mode (`socratic`, `direct`, `repair`, `quiz_prompt`, `explore`) on assistant messages.
- **Concept context header**: show the concept title and level above the thread.
- **Citation chips**: render source links inline in assistant messages using the `Sources` add-on component.
- **Mastery signal**: surface a "Ready to level up?" prompt inside the thread when the tutor mode shifts to `quiz_prompt`.

### Installation

```bash
cd apps/web
npx assistant-ui@latest init
```

The CLI will scaffold the shadcn/ui styled components into `components/assistant-ui/`. Install any add-ons (markdown, LaTeX, sources) as separate packages when the relevant phase is reached.

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

## Dark Mode

CoLearni should support a system-respecting dark mode. The implementation uses Tailwind's `dark:` variant together with [`next-themes`](https://github.com/pacocoursey/next-themes).

### Setup

```bash
npm install next-themes
```

Wrap the root layout in a `ThemeProvider`:

```tsx
// apps/web/app/layout.tsx
import { ThemeProvider } from "next-themes";

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

Enable class-based dark mode in Tailwind:

```js
// tailwind.config.ts
export default {
  darkMode: "class",
  // ...
};
```

### Scope

- All page backgrounds, card surfaces, borders, and text must have `dark:` counterparts.
- The graph canvas background and node styles must adapt (React Flow's default white canvas needs a dark variant).
- The tutor chat panel (assistant-ui components) must be themed — the installed shadcn/ui components in `components/assistant-ui/` should have `dark:` variants added when this work is done.
- The reasoning/thinking stream preview block (`bg-slate-800`) already works well in both modes.
- A theme toggle button (sun/moon icon) should be placed in the main header.

### When to implement

Dark mode is a Phase 9 (Demo Polish) requirement. It should be implemented before the product is shown to external users.

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
