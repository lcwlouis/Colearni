# CoLearni Product Spec

## Product Definition

CoLearni is an AI-powered learning workspace built around Socratic tutoring, concept graphs, mastery tracking, retrieval-based reasoning, and safe sharing of learning paths called Trails.

The product should feel like a mentor or coach, not a search engine. It should guide learners through concepts, ask useful questions, track demonstrated understanding, and help learners see where they are in the larger topic graph.

Core equation:

```text
CoLearni = personal learning workspace
         + concept graph / Trail
         + Socratic tutor
         + mastery state
         + source-aware retrieval
         + safe community Trail sharing
```

## Terminology

Workspace: a private learning environment owned by a user. It contains Trails, private notes, uploaded sources, hydrated content, mastery state, and chat history.

Trail: a user-facing learning graph/path for a topic.

Concept Level: an explicit node hierarchy level. Valid values are `umbrella`, `topic`, `subtopic`, and `granular`. This is not just parent/child position in the graph.

Trail Pack: a shareable/exportable package containing the safe public structure of a Trail.

Source Manifest: a structured list of sources associated with a Trail or concept, with origin, access, and export eligibility.

Research Trace: a record of what the research agent searched and selected. It stores links and metadata, not copied source content.

Hydration: enriching an imported Trail locally using public web sources, open-licensed sources, user-uploaded sources, or model knowledge.

## MVP Goal

A user can create or import a Trail, learn through a Socratic tutor, see progress on a concept graph, and export/share the safe structure of that Trail.

The first demo should prove:

```text
Create Trail
-> Learn concept
-> Level-up quiz
-> Graph mastery update
-> Safe Trail Pack export
-> Trail Pack import/fork
-> Optional research trace/hydration
```

Trail sharing is part of the MVP product identity. Dashboard, graph UX, ingestion, retrieval, provider-native tools, and future visualisers should improve this Trail experience, not replace safe export/import as the product spine.

## User Story: Create a Trail

As a learner, I can enter a topic and goal so CoLearni creates a learning graph.

Example input:

```json
{
  "topic": "Linear Algebra",
  "goal": "Understand enough for machine learning",
  "target_depth": "apply"
}
```

Expected behavior:

- CoLearni generates a 10-30 node concept graph.
- The graph includes prerequisites and hierarchy structure.
- Every node has a title, slug, node type, concept level, Bloom target, and mastery check labels.
- The Trail can exist before any document ingestion or hydration.

## User Story: Learning Dashboard

As a learner, I can return to CoLearni and immediately understand what to continue next.

Expected behavior:

- Home shows Continue Learning for the most relevant active Trail/concept.
- Home shows mastery progress per recent Trail.
- Home shows a deterministic recommended next concept/action before any LLM recommendation is needed.
- Recent Trails and older Trail search/list remain available.
- Creating a new Trail stays easy to find.
- Heavy gamification is deferred until the core learning/share loop is stable.

## User Story: Explore a Trail

As a learner, I can view the concept graph and click nodes to understand what to learn next.

Expected behavior:

- The graph shows nodes, edges, and mastery status.
- The graph distinguishes umbrella, topic, subtopic, and granular concepts.
- The learner can search nodes.
- Clicking a node opens a side panel.
- The side panel shows title, concept level, prerequisites, contained/related concepts, mastery checks, and sources if available.
- The graph remains usable up to at least 100 nodes.
- Learn Mode is the approachable default, with fewer visible controls, selected-node neighbourhood focus, and progressive disclosure.
- Inspect Mode preserves the current technical React Flow graph with full edge types, filters, layout controls, legend, and optional edge labels.
- Edge labels are not shown globally by default; relation meaning appears through focus, hover, side panel context, or an Inspect Mode toggle.

## User Story: Concept Detail

As a learner, I can select a concept and see what it is, why it matters, what to do next, what it connects to, and what sources support it.

Expected primary CTA by mastery state:

| Mastery state | Primary CTA |
|---|---|
| `not_started` | Start Learning |
| `learning` | Continue Tutor |
| `needs_review` | Review Weak Points |
| `mastered` | Practice / Explore Further |

## User Story: Learn a Concept

As a learner, I can open a concept and talk to a Socratic tutor.

Expected behavior:

- The tutor defaults to Socratic mode.
- The tutor asks one useful question at a time.
- The tutor can switch to direct explanation when the learner explicitly asks, but direct explanation is mastery-gated until the concept is `mastered` in the current MVP.
- The tutor repairs confusion when the learner is stuck or incorrect.
- The tutor can explore applications in a bounded way before mastery and can unlock broader free exploration after mastery.
- The tutor uses only safe scoped context: current concept, nearby graph nodes, mastery state, learning goal, and allowed sources.
- In strict grounded mode, user-visible sourced claims include citations or the tutor refuses.
- If reasoning traces are shown, the learner UI defaults to a compact summary and only shows the full trace when explicitly requested.

## User Story: Level Up

As a learner, I can complete a short mastery check to mark a concept as mastered.

Expected behavior:

- The level-up card is generated from mastery check labels.
- A typical check uses 2-4 mixed-format questions (`multiple_choice`, `short_answer`, `long_answer`) chosen from mastery labels, usually keeping only one or two longer explanation/application prompts.
- Passing updates the concept to `mastered`.
- Failing sets the concept to `needs_review` and gives specific feedback.
- The learner can retry.
- An unfinished quiz card reopens from a backend-owned draft until it is graded or explicitly refreshed.

## User Story: Export a Trail Pack

As a learner or creator, I can export the safe structure of my Trail.

Expected behavior:

- Export includes graph structure, learning objectives, abstract mastery check labels, public source metadata, and research trace.
- Export excludes uploaded files, private notes, chat history, user mastery, chunks, embeddings, and private/source-derived generated content.
- Export shows a report explaining what was included and excluded.

## User Story: Import a Trail Pack

As a learner, I can import a shared Trail and hydrate it locally.

Expected behavior:

- Import validates the manifest and graph.
- The Trail is forked into the workspace.
- Missing sources and hydration status are shown clearly.
- The learner can hydrate with public links, open-license sources, user uploads, or model knowledge.
- Hydrated content is private by default.

## User Story: Source Ingestion Foundation

As a learner, I can upload study material into my private workspace so CoLearni records provenance for later retrieval work.

Current foundation behavior:

- Uploaded files are private workspace objects stored under the configured local source storage root.
- Uploaded files create private `SourceRecord` rows and immutable `SourceRevision` rows with object key, content hash, parser metadata, and status.
- Learner-facing source metadata shows sanitized ingestion status, not storage object keys or content hashes.
- Parser/chunk/index work is not yet implemented, so uploaded content is not used by tutor retrieval.
- Uploaded/private/source-derived content never enters public Trail Pack export by default.

Future expected behavior:

- Priority formats are PDF, DOCX, and PPTX.
- Parsed text becomes markdown-like canonical text, then chunks and indexes behind scoped retrieval tools.
- Raw filesystem browsing is not the primary retrieval architecture.

## Future User Story: Tutor-Suggested Quiz

As a learner, I can accept a tutor's suggestion to practice or level up without the tutor bypassing the quiz system.

Expected behavior:

- The tutor emits a `suggest_quiz(concept_id, quiz_type, reason)` event/tool result.
- The frontend shows a quiz CTA/card.
- The backend-owned quiz draft system generates or reuses the card.
- The tutor cannot mark mastery directly.

## MVP Non-Goals

- No full SaaS marketplace yet.
- No billing yet.
- No school admin dashboard yet.
- No complex multi-agent framework yet.
- No PDF ingestion as the first milestone.
- No public sharing of uploaded/source-derived content.
- No raw filesystem-browsing agent as the primary retrieval architecture.
- No arbitrary LLM-generated JavaScript visualisers in the MVP.
- No LiteLLM or large provider abstraction rewrite.
- No public pack moderation workflow until SaaS prep.
- No multi-organization permissions model in the local-ready MVP.

## Acceptance Criteria

The rebuild is ready to show users when:

- A new user can create a Trail from a topic in under one minute.
- They can click a concept and start learning immediately.
- The tutor asks useful Socratic questions.
- The graph updates progress after a level-up quiz.
- The user can export a safe Trail Pack.
- The export does not leak private/uploaded/source-derived content.
- Another user can import that Trail Pack and learn from it.
