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
- KaTeX, `remark-math`, `rehype-katex`, and `remark-gfm` for tutor message rendering.
- Vitest for frontend tests.

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
- Streaming state, auto-scroll, message grouping, and accessibility primitives.
- Markdown rendering extension points used by our owned renderer.
- A `Sources` component designed to display URL-sourced citations. We use concept-level source chips today; true per-message source parts are next.
- KaTeX-friendly markdown support for math rendering in tutor messages.
- Mermaid diagrams through our owned renderer for fenced `mermaid` code blocks.

### Why not the Vercel AI SDK

CoLearni calls its own FastAPI backend (`POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat`), not a Next.js route backed by the Vercel AI SDK. `assistant-ui` supports this via its **Custom Backend / `LocalRuntime`** pattern: we write a thin model adapter that handles the HTTP call, and the library manages all UI state.

### Custom Runtime Adapter

The adapter lives in `apps/web/lib/tutor-runtime.ts` and is the only integration glue between assistant-ui and FastAPI.

Current behavior:

- Hydrates persisted turns from `GET .../conversation` into assistant-ui `initialMessages`.
- Sends only the latest user message to `POST .../chat` with the current `conversation_id`.
- Reads SSE events from `apps/web/lib/api.ts` and maps `status`, `thinking`, `tool_call`, and `tool_result` into ordered assistant-ui data parts.
- Rehydrates persisted `reasoning_parts` as ordered assistant-ui data parts so reopened chats keep thinking/tool/result boundaries instead of flattening into one reasoning block.
- Maps streamed visible tokens to assistant-ui text parts.
- Stores the returned `conversation_id` for later turns.
- Applies `mastery_update` from the final SSE event so the graph/concept UI can update immediately after tutor turns that change state.

The page wraps the chat panel in `<AssistantRuntimeProvider runtime={runtime}>` and renders owned thread/message/composer UI using assistant-ui primitives.

### Streaming Requirement

For a responsive Socratic experience, `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat` should return a **streaming response** using SSE. The adapter above should yield tokens incrementally by reading the response body as a `ReadableStream`. The UI will start rendering as soon as the first token arrives.

### Customisation Points

The components in `apps/web/components/assistant-ui/` and `apps/web/app/trails/[id]/components/TutorPanel.tsx` are plain React/Tailwind files we fully own. CoLearni-specific customisations include:

- **Tutor mode badge**: display the active mode (`socratic`, `direct`, `repair`, `quiz_prompt`, `explore`) on assistant messages.
- `free_explore` is also a valid tutor mode, but it is mastery-gated and may be rare in the current MVP.
- **Concept context header**: show the concept title and level above the thread.
- **Markdown/math/code renderer**: `MarkdownText` uses assistant-ui markdown primitives with `remark-gfm`, `remark-math`, `rehype-katex`, fenced `mermaid` rendering, copyable code blocks, and preprocessing for both `$...$` and TeX `\(...\)`/`\[...\]` math delimiters.
- **Concept-level source chips**: render available source links in the tutor header. True per-message `Sources` parts are deferred until the backend emits answer-level citation parts.
- **Mastery signal**: surface a "Ready to level up?" prompt inside the thread when the tutor mode shifts to `quiz_prompt`.
- **Reasoning view toggle**: default to a learner-safe summary and allow an explicit full-trace toggle, persisted in `localStorage` as `colearni.reasoningView`.

Hidden internal tool turns used by the backend's gated tutor flow are not rendered in the frontend. The public conversation history endpoint only returns visible user/assistant messages.

### Tutor UI Roadmap

Near-term next:

- Adopt true assistant-ui `Sources` message parts once the backend emits per-message citation/source parts rather than only concept-level source metadata.
- Add `Quote` support alongside those sourced message parts.

Later, but important:

- Evaluate `Streamdown` when we want a broader markdown/rendering migration beyond the current owned renderer.

Later, once tutor/tool flows are more agentic:

- `Syntax Highlighting`
- `Context Display`
- `Directive Text`
- `ToolGroup`

AssistantModal evaluation:

- Keep the current concept side panel for the MVP. `AssistantModal` is a floating global popover pattern, while CoLearni's tutor is concept-scoped, shares state with the concept sheet, and needs the graph-side context header. Revisit `AssistantModal` only if a global cross-Trail assistant is added later.

Artifact roadmap:

- Start with structured artifact payloads such as JSON or CSV rendered by a frontend component registry.
- Flashcard sets and mini quizzes should arrive through that artifact path when mastery gating lands.
- Raw React or JavaScript artifacts are a much-later option, not part of the current MVP phases.

### Installation

```bash
cd apps/web
npx assistant-ui@latest init
```

The CLI will scaffold the shadcn/ui styled components into `components/assistant-ui/`. Install any add-ons needed for markdown, LaTeX, or sources as separate packages when the relevant phase is reached. Mermaid is not a built-in assistant-ui feature here; handle it in our owned markdown renderer.

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
