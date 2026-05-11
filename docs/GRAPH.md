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
2. Prerequisites.
3. Containing nodes and contained nodes.
4. Current Trail.
5. Explicitly linked sources.
6. Broader workspace only when needed.

Avoid searching the entire graph by default.

## Tests

- Graph schema validation.
- Concept level validation.
- Duplicate slug detection.
- Missing endpoint detection.
- Cycle detection.
- Hierarchy/contains edge validation.
- Budget stop reasons.
- Safe partial output when budgets are hit.
