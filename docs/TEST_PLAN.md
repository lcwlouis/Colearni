# CoLearni Test Plan

## Purpose

This plan defines the tests needed for the local-ready CoLearni rebuild. Tests should protect the core product loop and the public/private safety boundary.

Recommended MVP build order:

```text
1. Foundation cleanup
2. Workspace + Trail database models
3. Trail generation endpoint
4. Graph viewer
5. Phase 3.5 hardening + docs alignment
6. Tutor chat backend for one concept
7. Tutor chat frontend with assistant-ui
8. Mastery + level-up quiz
9. Source provenance + safe Trail Pack export
10. Trail Pack import + research trace/hydration MVP
11. Provider tool abstraction foundation
12. Learning dashboard + Learn/Inspect graph UX
13. Source ingestion MVP
14. Retrieval + context tooling
15. Guided graph navigation / recommended next concept
16. Conversation summaries + learner state
17. Tutor-suggested quiz cards
18. Deferred visualiser / artifact templates
19. Demo polish/user testing
20. Deployment
21. SaaS prep
```

Do not start with PDF ingestion, SaaS billing/auth, or a public marketplace. Safe Trail Pack export/import stays early and central; provider tool foundations come before source ingestion and retrieval tools expand.

## Foundation Tests

- Backend health endpoint returns ok.
- DB migration applies cleanly.
- Frontend can call backend.
- Environment variables are documented and match code.
- One command starts local infra.
- One command starts backend.
- One command starts frontend.

Suggested commands:

```bash
pytest
alembic upgrade head
cd apps/web && npm run typecheck
```

Use the commands that exist in the current repo. If a command cannot run, document why.

## Workspace + Trail Model Tests

- Create workspace.
- Create Trail.
- Add nodes.
- Add edges.
- Add research source.
- Add user-upload source.
- Public export excludes user-upload source.
- Public export includes research source metadata only.

## Graph Tests

- Create Trail.
- Generate nodes.
- Generate edges.
- Validate concept levels: umbrella, topic, subtopic, granular.
- Detect cycles.
- Reject duplicate slugs.
- Validate graph schema.
- Validate hierarchy/contains edges separately from prerequisite edges.
- Enforce graph size cap.
- Repair malformed LLM graph output once.
- Fall back or fail clearly when generated graph is too large.

Manual topics:

```text
Linear Algebra
Computer Networks
FastAPI
Operating Systems
Photography Exposure Triangle
```

## Frontend Graph Tests

- Graph renders empty state.
- Graph renders sample Trail.
- Click node opens side panel.
- Search filters or focuses node.
- Concept level filters or visual distinctions work.
- Status colors are correct.
- Graph remains usable at 10, 50, and 100 nodes.
- Learn Mode hides advanced controls by default.
- Inspect Mode preserves filters, layout controls, legend, and full edge types.
- Edge labels are not globally visible by default.
- Optional edge labels appear only in Inspect Mode.
- Concept panel CTA changes by mastery state.
- Mobile view prioritizes selected concept detail and next actions over dense controls.

## Dashboard Tests

- Dashboard renders empty, loading, populated, and error states.
- Continue Learning chooses a valid active/recent Trail or concept.
- Trail mastery summaries render correct counts/progress.
- Recommended Next uses deterministic graph/mastery heuristics.
- Recent Trails and older Trail search/list work.
- Create new Trail entry point remains visible.

## Tutor Tests

- Tutor receives current concept context.
- Tutor receives prerequisite and child-node context.
- Tutor receives concept level context.
- Tutor receives mastery state.
- Tutor asks Socratic question by default.
- Tutor can enter direct mode.
- Tutor can enter repair mode.
- Tutor can enter explore mode.
- Tutor can unlock free_explore after mastery and falls back cleanly before mastery.
- Tutor stream emits `status`, `tool_call`, and `tool_result` events when gated tool continuation is used.
- Reopened assistant history preserves ordered `reasoning_parts` instead of flattening tool/thinking traces.
- Tutor does not reference missing/private sources.
- Prompt builder excludes public-export-stripped content from public contexts.
- Hidden tool-call history does not leak into the public conversation history API.
- User-visible sourced claims cite allowed evidence or refuse in strict grounded mode.

Manual tests:

- Start learning vectors.
- Ask for direct answer.
- Answer incorrectly.
- Ask for example.
- Ask how the concept links to ML.
- Ask unrelated question.
- Ask "just give me the answer."

## Mastery Tests

- Quiz generated from mastery labels.
- Quiz supports `multiple_choice`, `short_answer`, and `long_answer` questions.
- Correct answer updates concept to mastered.
- Weak answer sets needs_review.
- Wrong answer gives specific feedback.
- Grade responses include per-question feedback.
- Quiz attempt is stored.
- Unsubmitted quiz drafts are reused unless `force_new` is requested.
- Practice grading stores an attempt but does not update mastery.
- User can retry.
- Graph UI reflects mastery status.
- First tutor turn sets concept status to learning.
- Tutor cannot mark mastery without quiz/evaluation.

## Source Safety Tests

These are critical and should be treated as regression tests for every export/import change.

- User-upload source is never included in public export.
- Private notes are never included.
- Raw chunks are never included.
- Embeddings are never included.
- Chat history is never included.
- Mastery records are not included by default.
- Generated summaries from private/user-uploaded sources are never included.
- Generated quizzes from private/user-uploaded sources are never included.
- Public research source URL is included.
- Research trace is included.
- Export report lists excluded items.

## Trail Pack Tests

- Valid pack imports.
- Malformed pack rejected.
- Pack with raw chunks rejected.
- Pack with embeddings rejected.
- Pack with uploaded files rejected.
- Pack with private notes rejected.
- Duplicate slugs handled.
- Missing sources shown clearly.
- Imported graph displays correctly.
- Imported pack can be hydrated.
- Imported pack forks into the current workspace.
- Imported pack can be learned from without hydration.

## Research and Hydration Tests

- Research trace created.
- Public URL stored.
- Search query stored.
- Source selection reason stored.
- Excluded source note stored.
- Hydration creates private evidence records.
- Hydrated chunks are not included in public export.
- Hydrated embeddings are not included in public export.
- Unknown-license source marked no-redistribution.
- User can skip hydration and still learn.

## Provider Tool Tests

- OpenAI Responses tool calls normalize to the internal tool call/result shape.
- OpenAI-compatible Chat Completions/OpenRouter tool calls normalize to the same shape.
- Anthropic tool use normalizes to the same shape.
- Fake provider streams text, reasoning, tool calls, tool results, and final text without live LLM calls.
- Tutor instruction tool compatibility adapter preserves SSE event order and public `tool_call` / `tool_result` previews.
- Hidden tool turns are persisted for replay but excluded from public conversation history.
- Invalid tool arguments fail safely without unbounded retries.

## Source Ingestion Tests

- Current foundation: uploads create private source records and immutable source revision records.
- Content hash, parser version, object key, file size/content type, and source revision status are stored internally.
- Upload/source metadata API responses expose sanitized revision summaries, not storage object keys or content hashes.
- Invalid uploads or storage failures do not create partial public content.
- Workspace-scoped source metadata reads cannot access another workspace's upload.
- Source metadata reads do not expose raw private uploaded bytes/text.
- Chunks and embeddings are excluded from export.
- Concept-source links can be created and read.
- No endpoint exposes raw private source text without workspace scope.
- Deferred parser expansion: PDF/DOCX/PPTX parsing should add format-specific tests when real parser support lands.

## Retrieval and Context Tests

- Retrieval scopes to current concept and linked sources first.
- Whole-workspace retrieval does not run unless explicitly requested and budgeted.
- Tool result sizes are capped.
- Private sources from other workspaces cannot be read.
- `open_source_chunk` requires a valid chunk id in scope.
- Sourced tutor answers cite allowed evidence or refuse in strict mode.
- Tool failures degrade without crashing tutor streaming.

## Recommended Next Tests

- Mixed mastery states produce expected recommendations.
- Prerequisites are respected.
- `needs_review` concepts can be prioritized for repair.
- Topic/subtopic preference wins over umbrella/granular when otherwise tied.
- All-mastered Trails return review/explore/extension guidance.
- Dashboard and concept panel render recommendation reasons.

## Learner State Tests

- Conversation summaries cover the intended turn range and record `turns_covered_to`.
- Summary generation is idempotent.
- Quiz attempts remain immutable.
- Learner state updates after pass/review events.
- Improved learner state can supersede old failed-quiz bias.
- Tutor prompt uses learner state summary within context budget.

## Tutor-Suggested Quiz Tests

- `suggest_quiz` creates a frontend-visible CTA without grading.
- Clicking the CTA reuses an existing backend draft when present.
- Tutor cannot update mastery through the suggestion event.
- Duplicate suggestion events dedupe safely.
- Suggestion reason is learner-visible.

## Artifact Template Tests

- Valid artifact payload renders through the expected trusted component.
- Unknown artifact type falls back safely.
- Source-derived private artifacts are excluded from public export.
- Raw script execution is not allowed.

## Integration Tests

- Create Trail -> generate graph -> chat -> quiz -> mastery.
- Export Trail Pack -> import Trail Pack.
- Research trace -> hydrate -> export excludes hydrated content.
- Import Trail Pack -> hydrate -> tutor uses local private evidence.

## Manual Red-Team Tests

- Upload private PDF then export.
- Try to force export of private notes.
- Ask tutor to reveal private source text.
- Ask tutor to cite sources that are not present.
- Import malicious or malformed pack.
- Generate huge graph.
- Generate graph with cycles.
- Generate duplicate concepts.
- Ask unrelated questions during tutoring.
- Ask tutor to mark mastery without quiz.

## Demo Acceptance Tests

The first demo should prove:

```text
1. Create Trail: "Learn Linear Algebra for ML"
2. See generated graph
3. Click "Vectors"
4. Learn through Socratic chat
5. Take level-up quiz
6. Node turns mastered
7. Click "Eigenvectors"
8. Export safe Trail Pack
9. Import/fork that Trail Pack into a new workspace
10. Optionally run research trace/hydration for the imported Trail
```
