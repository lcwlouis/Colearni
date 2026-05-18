# Considered Alternatives

This file records technologies and approaches that were evaluated for CoLearni but not adopted in the current implementation. Each entry explains what was considered, why it was not chosen now, and under what conditions it should be revisited.

---

## Sigma.js — Graph Rendering

**Repository:** https://github.com/jacomyal/sigma.js  
**What it is:** A WebGL/Canvas-based graph rendering library designed for large network visualisation. Uses [`graphology`](https://github.com/graphology/graphology) as its data model and supports force-directed layouts via `graphology-layout-forceatlas2`.

### Why we looked at it

Sigma.js was the original graph library in the pre-rebuild CoLearni codebase. It handles very large graphs (thousands of nodes) with smooth pan/zoom because all rendering is done on the GPU rather than in the DOM.

### Why we are not using it now

The current per-Trail graph view is built with **React Flow (`@xyflow/react`) + dagre** and is already working. At the scale of a single Trail (10–100 nodes, hard cap in `docs/GRAPH.md`), React Flow is the correct tool:

- Nodes render as React components, which makes rich per-node content (title, concept level badge, difficulty indicator, mastery colour) easy to build and maintain.
- `dagre`'s hierarchical top-down layout suits the `umbrella → topic → subtopic → granular` structure better than ForceAtlas2, which is designed for social-network clustering rather than directed learning hierarchies.
- React Flow's DOM-based rendering is perfectly comfortable at 10–100 nodes.

Replacing it with Sigma.js now would mean throwing away a working implementation and giving up React-component node rendering, for no benefit at current scale.

### Known React Flow ceiling

React Flow is DOM-based. Every node is a real React component in the document, and pan/zoom triggers layout recalculations across all rendered nodes. In practice:

- **Up to ~300 nodes:** no noticeable performance issues.
- **300–500 nodes:** interactions (pan, zoom, drag) start to feel sluggish.
- **500+ nodes:** clearly uncomfortable; not suitable for a fluid graph exploration experience.

### When to revisit

**Adopt Sigma.js if any view ever needs to display nodes from more than one Trail simultaneously.** Concrete triggers:

- A workspace-level overview graph showing all concepts across all Trails.
- A merged Trail view combining two or more Trail graphs.
- A community or public marketplace graph showing relationships between multiple Trail Packs.
- Any other surface where the expected steady-state node count exceeds ~300.

At that point the right architecture is most likely **two separate graph surfaces**:

1. **Per-Trail detail view** — keep React Flow. Rich node UI, hierarchical dagre layout, mastery interaction. 10–100 nodes.
2. **Combined/workspace overview** — adopt Sigma.js. WebGL rendering, force-directed or hierarchical layout of the full node set, click-to-drill-down into the React Flow per-Trail view.

### Integration notes (for when the time comes)

- React integration: [`@react-sigma/core`](https://sim51.github.io/react-sigma/)
- Data model: `graphology` — nodes and edges are plain objects, not React components.
- Layout: `graphology-layout-forceatlas2` for force-directed; `graphology-layout-noverlap` for overlap removal.
- Node labels and hover tooltips require either Sigma's built-in renderer settings or a separate HTML overlay layer (not React components on nodes).
- The `graphology` graph object can be built directly from the same node/edge data the backend returns, so no API changes are needed.

---

## LiteLLM — LLM Routing

**What it is:** A unified Python client that wraps multiple LLM provider APIs behind a single OpenAI-compatible interface.

### Why we looked at it

LiteLLM would simplify switching between providers (OpenAI, Anthropic, Gemini, etc.) without changing call sites.

### Why we are not using it

Per `docs/ARCHITECTURE.md`: CoLearni makes direct calls to LLM provider APIs via `backend/app/agents/llm_client.py`. LiteLLM is explicitly excluded as a dependency.

The `openai` SDK already supports any OpenAI-compatible endpoint via `base_url`, covering OpenAI, OpenRouter, DeepSeek, Gemini, and local Ollama. Anthropic is supported natively via its own SDK as an optional extra. This covers all providers we need without adding a dependency, hidden routing logic, or an additional abstraction layer to audit.

Additionally, there was safety concerns with LiteLLM.

### When to revisit

No plans for revisiting at this moment.

---

## Plain Rolling-Window Stream Preview

**Location:** `apps/web/app/trails/page.tsx` — the `streamPreview` state + the `<pre>` block inside the generating panel.

### What it is

While the LLM streams tokens, the frontend accumulates incoming delta chunks into a single string and keeps only the last 200 characters:

```tsx
(chunk) => {
  setStreamPreview((prev) => (prev + chunk).slice(-200));
},
```

The preview is rendered as a plain, slightly faded `<pre>` block below the progress log:

```tsx
{streamPreview ? (
  <pre className="mt-2 max-h-16 overflow-hidden break-all text-xs leading-4 text-blue-400">
    {streamPreview}
  </pre>
) : null}
```

### Why it has its own magic

- **Zero DOM overhead.** A single text node. No per-character spans, no animation frames, no RAF loops.
- **Authentic terminal feel.** Raw JSON fragments scrolling in feels honest — you can actually read what the LLM is writing.
- **Stateless.** One `string` state, one `.slice(-200)`. Nothing to synchronise, nothing to leak.
- **Graceful at any stream rate.** Works identically whether tokens arrive every 10 ms or every 500 ms.

### Why we moved to the animated version

The animated `StreamPreview` component (character fade-in + shimmer overlay + blinking cursor) communicates "the machine is working" more viscerally during the initial blank-screen moment before any characters arrive, and matches the overall polished feel of the graph UI.

### When to revisit

- If the animated version ever causes jank on low-end devices (many `<span>` elements + CSS animations).
- If a "raw output" debug mode is ever added for power users.
- As a fallback when `prefers-reduced-motion` is detected (pair it with the `(prefers-reduced-motion: reduce)` media query).
