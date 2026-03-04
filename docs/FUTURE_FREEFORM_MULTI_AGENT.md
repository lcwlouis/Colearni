# Future Free-Form Multi-Agent Notes

Status: future-reference only, not an active execution target.

## Purpose

This document captures the longer-term direction toward a more free-form multi-agent version of CoLearni without widening the current guarded-conductor plan prematurely.

The current active plan remains:

- guarded conductor
- bounded evidence planning
- typed learner model
- approval-gated research
- recommendation-first background jobs

This future direction should only be revisited after those foundations are stable.

## What "Free-Form Multi-Agent" Would Mean

A future free-form runtime would move beyond the current tutor-centered conductor and allow multiple specialized agents to collaborate more openly around a learner goal.

Candidate future agents:

1. Topic Finder Agent
   - expands a learner goal into subtopics, routes, and points of interest
2. Knowledge Finder Agent
   - plans and executes bounded external discovery over papers, expert posts, docs, and updates
3. Knowledge Extractor Agent
   - distills candidate material into POIs, claims, contradictions, and study artifacts
4. Tutor Agent
   - teaches, checks understanding, and adapts pedagogy
5. Assessment / Review Agent
   - proposes quizzes, review packs, and promotion decisions
6. Learner Model Agent
   - maintains learner-facing summaries and study frontier proposals
7. Deep Review Agent
   - synthesizes "everything learned so far" into reviewable second-brain outputs
8. Background Update Agent
   - prepares "what changed" digests and topic-watch suggestions

## Why This Is Deferred

Pursuing this too early would create avoidable risk:

1. Hidden policy drift
   - multiple agents can weaken grounding, mastery gating, or approval rules unless the runtime is already mature
2. State explosion
   - free-form agent collaboration creates more intermediate state, more traces, and more debugging complexity
3. Cost and loop risk
   - unconstrained multi-agent planning can burn tokens and produce runaway tool loops
4. Source trust risk
   - external discovery becomes much harder to reason about if ingestion and promotion are not already disciplined
5. UX ambiguity
   - the product can feel "smart" but become difficult for users to understand or trust

## Preconditions Before Reopening This Direction

Do not promote this into active implementation until the following are true:

1. The guarded conductor is stable and observable.
2. Evidence planning is bounded and debuggable.
3. Learner snapshots exist and are productized.
4. Research planning is online-capable but still approval-gated.
5. Background summaries and digests exist in a recommendation-first form.
6. Scenario and policy regression coverage is strong enough to catch unsafe planner behavior.

## Future Design Principles

If this direction is reopened later, keep these principles:

1. Keep every agent typed, inspectable, and budget-bounded.
2. Keep final user-facing answers runtime-gated by grounding and policy checks.
3. Keep external research approval-gated until the trust model is proven.
4. Treat canonical graph, provenance, and learner snapshot state as shared runtime truth.
5. Prefer proposal objects over free-form agent-to-agent text passing.
6. Keep rollback paths and compatibility shims for each orchestration change.

## Near-Term Non-Goals

These are explicitly not part of the current plan:

1. A generic autonomous agent runtime.
2. Free-form inter-agent tool loops.
3. Silent ingestion of externally discovered content.
4. Background agents directly messaging the user without a product surface.
