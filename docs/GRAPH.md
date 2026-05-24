# Graph Rules And Budgets

## Purpose

The concept graph is a core CoLearni product primitive. It powers Trail navigation, tutor context, mastery progression, and safe Trail Pack sharing.

Graph work must stay bounded. Do not add unbounded graph traversal, resolver loops, gardener loops, or whole-workspace retrieval by default.

## Graph Concepts

Trail graph nodes represent learning concepts at explicit hierarchy levels. This level is not the same thing as an edge.

Concept levels:

```text
umbrella
topic
subtopic
granular
```

Level meanings:

- `umbrella`: broad domains or major areas, such as Linear Algebra or Computer Networks.
- `topic`: major learnable areas within an umbrella, such as Vectors, Matrices, or Routing.
- `subtopic`: focused units inside a topic, such as Matrix Multiplication or IP Addressing.
- `granular`: atomic skills, checks, misconceptions, examples, or procedures, such as computing a dot product by hand.

Edges describe relationships between nodes:

```text
prerequisite
contains
application
related
```

Use `contains` for hierarchy edges when useful, but do not infer level purely from parent/child position. A node must carry its own `concept_level`.

For the MVP, prerequisite edges should be acyclic unless a feature explicitly allows and explains cycles.

## Required Node Fields

Every generated concept node should have at least:

- Title.
- Slug unique within the Trail.
- Node type.
- Concept level: `umbrella`, `topic`, `subtopic`, or `granular`.
- Difficulty.
- Bloom target.
- Mastery check labels.

## Validation Rules

- Reject duplicate slugs.
- Reject edges pointing to missing nodes.
- Reject unknown concept levels.
- Validate that each generated Trail has at least one `umbrella` or `topic` entry node.
- Prefer level transitions that move from umbrella -> topic -> subtopic -> granular for hierarchy views.
- Detect prerequisite cycles.
- Cap generated graphs at 10-30 nodes for first generation.
- Keep graph viewer usable at 100 nodes.
- Store source links separately from concept content.

## UI Expectations

The graph viewer should use concept levels to shape the experience:

- Level filters or grouping.
- Distinct visual treatment by level.
- Ability to collapse/expand umbrella and topic clusters.
- Side panel should show concept level alongside prerequisites, contained nodes, related nodes, mastery checks, and sources.

Status colors should still represent mastery. Level styling should not replace mastery styling.

The per-Trail graph should evolve into two modes without replacing React Flow:

- Learn Mode: approachable default, fewer visible controls, selected-node neighbourhood focus, progressive disclosure, and concept-panel-first next actions.
- Inspect Mode: current technical graph behavior with full edge types, filters, layout controls, legend, and optional edge labels.

Do not show all edge labels globally by default. In Learn Mode, relationship meaning belongs in hover/focus states, selected neighbourhoods, and the concept side panel. In Inspect Mode, edge labels should be optional. Preserve existing line styles for relationship types.

## Resolver Budget

Hard stop defaults:

```text
max 3 LLM calls per chunk
max 50 LLM calls per document
```

When the resolver hits a budget, it must emit an explicit stop reason and return partial progress safely.

## Gardener Budget

Hard stop defaults:

```text
max 30 LLM calls per run
max 50 clusters per run
```

When the gardener hits a budget, it must emit an explicit stop reason and leave the graph in a valid state.

## Tutor Retrieval Scope

Default tutor graph context should be scoped in this order:

1. Current concept.
2. Mastery state.
3. Learner state summary, when available.
4. Prerequisites, containing nodes, contained nodes, and related nodes.
5. Explicitly linked sources.
6. Recent turns or conversation summary.
7. Source chunks only when needed.

Avoid searching the entire graph or workspace by default.

## Recommended Next Concept

V1 recommendation should be deterministic before LLM-based:

- Choose a concept with status `not_started` or `needs_review`.
- Prefer concepts whose prerequisites are `mastered` or already `learning`.
- Prefer `topic` or `subtopic` over `umbrella` or `granular`.
- Prefer lower difficulty first.
- If all concepts are mastered, suggest review, adjacent exploration, or generating an extension.

The recommendation must be explainable and bounded to the current Trail or selected subgraph unless the learner explicitly asks to go broader.

## Tests

- Graph schema validation.
- Concept level validation.
- Duplicate slug detection.
- Missing endpoint detection.
- Cycle detection.
- Hierarchy/contains edge validation.
- Budget stop reasons.
- Safe partial output when budgets are hit.
