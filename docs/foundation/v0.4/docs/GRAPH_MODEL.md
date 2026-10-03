# Graph model and hierarchy — carry forward the useful rebuild semantics

**Accepted direction:** retain explicit concept levels. **Proposed baseline:** retain the rebuild's four edge types and validation approach. This is not an instruction to restore its old graph-first UI or mastery gates.

## What the rebuild actually defines

`docs/GRAPH.md` on branch `rebuild` explicitly separates levels (`umbrella`, `topic`, `subtopic`, `granular`) from edges (`prerequisite`, `contains`, `application`, `related`). It calls for bounded traversal, cycle checks, focused Learn Mode and an optional technical Inspect Mode. Source inspected for this handoff: blob `299996d48c61252ad7f67bfdff7eb02b899e15e2`. [G1]

## Distinct dimensions

| Dimension | Meaning | Example |
|---|---|---|
| Concept level | Granularity in a stated learning scope | `subtopic` |
| Node kind | What the node represents | concept, skill, misconception, example |
| Edge relation | How two nodes connect | contains or prerequisite |
| Bloom target | Capability intended for a particular goal | explain, apply, analyse |
| Difficulty | Proposed challenge relative to a context | beginner/intermediate/advanced, reviewed rather than universal |
| Learning evidence | What this person actually demonstrated | independent attempt on a dated task, or unknown |

Do not introduce “related” as a fifth hierarchy level. Do not use topic-completion counts, exposure or node colour as proof of understanding. A graph level is not the learner's ability level.

## Level meanings and a synthetic example

- `umbrella`: broad domain, e.g. Mathematics.
- `topic`: substantial learnable area, e.g. Linear functions.
- `subtopic`: focused part, e.g. Slope.
- `granular`: atomic concept/skill/example, e.g. Calculate slope from two points.

These labels are required attributes, not inferred from graph position or count of parents. Their interpretation has a stated graph/curriculum scope. Do not automatically merge concepts across scopes merely because titles match. The same idea may be described at different granularity in another curriculum; use explicit reviewed equivalence/mapping instead of silently rewriting all desks.

Do not force a four-step chain everywhere. A small desk may begin at topic/subtopic and omit irrelevant layers. Approved hierarchy edges may skip levels. Changes to an established level are explicit revisions, not visual relayout side effects.

## Initial edge vocabulary — proposed implementation semantics

| Type | Source → target | Validation/behaviour |
|---|---|---|
| `contains` | Broader concept → included concept | Source has broader level than target; no containment cycles. Multiple parents allowed where meaningful. |
| `prerequisite` | Supporting concept → concept it supports | Directed dependency; acyclic prerequisite subgraph. It suggests a route, not a locked-access rule. |
| `application` | Concept → application context | Explain the relation with evidence; not an automatic hierarchy or prerequisite. |
| `related` | Association between concepts | Symmetric; normalise endpoint order for deduplication, preserve original assertion provenance. |

The direction for `application` is an explicit new contract choice: verify imports against the old producer rather than assuming all historical uses match. Preserve imported records when a semantic mapping is uncertain and request review; do not silently reverse edges.

Relationship types are not set in stone, but are not free-form model inventions either. Begin with the four built-ins. Add a new type only through a versioned registry defining directionality, inverse/display label, validation, rendering and retrieval behaviour. Unknown types stay uncommitted or render as unsupported until reviewed. A readable explanation can accompany an edge without becoming a new type.

## Provenance and review

Every proposed relationship needs identity, scope, typed endpoints, rationale/evidence pointers, origin, version and proposed/confirmed/rejected state. A proposed link does not become an established fact because an LLM or decision model is confident. Avoid exposing private-note titles or excerpts through cross-desk edges. Authorisation checks apply to both endpoints and evidence pointers.

## Graph versus route

The knowledge graph stores conceptual structure. A route is a goal-relative suggested sequence. Current work, shelf objects and reusable notes link to the graph without being the same entities. Graph links neither grant tutor access nor transfer mastery. A learner may inspect an advanced node, ask for an explanation, or explore out of sequence.

## Display contract

Use one consistent semantic/visual node family across desktop, mobile, expanded/collapsed sidebar, and themes. Candidate geometry is a rounded rectangular node with title, explicit level label and a separate evidence/status indicator. The exact shape, spacing and icons still require one-view review.

Containment can group/collapse umbrella/topic branches. Prerequisites and other connections have distinct line treatment and accessible labels. No global cloud of edge labels by default. Learn Mode shows a selected neighbourhood and a readable relationship list; Inspect Mode exposes technical detail. A list/tree equivalent is required on mobile and for non-spatial navigation; shrinking nodes to unlabeled circles is not an acceptable mobile adaptation.

Represent unknown understanding honestly. Evidence detail shows assistance, recency and scope. Do not copy unsupported “50% mastered” rings from retired images.

## Bounds and tests

Initial generated route proposal: a small bounded selection, with expandable further research. The rebuild's 10–30 initial nodes and 100-node interactive view are useful starting budgets, not performance measurements or required minimum curriculum size. Load a neighbourhood; never retrieve an entire large workspace by default. Record partial progress and a stop reason when any operation hits a budget. [G1]

Test explicit levels, supported node kinds/edges, missing endpoints, duplicate IDs/slugs, scope isolation, containment ordering/cycles, prerequisite cycles, related deduplication, provenance, unknown-type handling and safe partial results. Graph-cycle checks apply to the appropriate relation subgraph, not indiscriminately to symmetric associations.

`contracts/graph-contracts.ts` and `fixtures/graph.synthetic.json` are independent draft vocabulary/examples. They are not a migration or production validator.
