# CoLearni Test Plan

## Purpose

This plan defines the tests needed for the local-ready CoLearni rebuild. Tests should protect the core product loop and the public/private safety boundary.

Recommended MVP build order:

```text
1. Foundation cleanup
2. Workspace + Trail database models
3. Trail generation endpoint
4. Graph viewer
5. Tutor chat for one concept
6. Mastery + level-up quiz
7. Source provenance + export sanitizer
8. Trail Pack export
9. Research trace
10. Hydration
11. Trail Pack import
12. Demo polish
13. SaaS prep
```

Do not start with PDF ingestion, SaaS billing/auth, or a public marketplace.

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

## Tutor Tests

- Tutor receives current concept context.
- Tutor receives prerequisite and child-node context.
- Tutor receives concept level context.
- Tutor receives mastery state.
- Tutor asks Socratic question by default.
- Tutor can enter direct mode.
- Tutor can enter repair mode.
- Tutor can enter explore mode.
- Tutor does not reference missing/private sources.
- Prompt builder excludes public-export-stripped content from public contexts.
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
- Correct answer updates concept to mastered.
- Weak answer sets needs_review.
- Wrong answer gives specific feedback.
- Quiz attempt is stored.
- User can retry.
- Graph UI reflects mastery status.
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
8. Research public sources
9. Export safe Trail Pack
10. Import that Trail Pack into a new workspace
```
