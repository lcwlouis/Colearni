# CoLearni

> A local-ready Socratic learning workspace built around Trails, concept graphs, mastery checks, source-aware retrieval, and safe Trail Pack sharing.

## What CoLearni Is

CoLearni is being rebuilt from scratch for the actual MVP.

The product is not a generic RAG chatbot and it should not start with PDF ingestion. The first useful version should prove the core learning loop:

```text
Create a Trail
-> explore the concept graph
-> learn one concept with a Socratic tutor
-> pass a level-up quiz
-> see mastery progress update
-> export/import a safe Trail Pack
```

The product should feel like a mentor or coach. It should ask useful questions, help repair misconceptions, track demonstrated understanding, and make the learner's path through a topic visible.

## Core Terms

Workspace: a private learning environment. It contains Trails, private notes, uploaded sources, hydrated content, mastery state, and chat history.

Trail: a user-facing concept graph or learning path for a topic, such as "Linear Algebra for Machine Learning."

Concept Level: an explicit node hierarchy level. Valid values are `umbrella`, `topic`, `subtopic`, and `granular`; this is not just inferred from parent/child edges.

Trail Pack: a shareable/exportable package containing the safe public structure of a Trail.

Source Manifest: structured source metadata with provenance, access level, and export eligibility.

Research Trace: a record of public-source searches and selected links. It stores links and metadata, not copied source content.

Hydration: enriching an imported Trail locally with public links, open-license sources, user uploads, manual notes, or model knowledge. Hydrated content is private by default.

## MVP Direction

Build local-ready first and keep SaaS compatibility in the architecture.

Local-ready first means:

- Single-user or simple-user workspace.
- Docker Compose for local infrastructure.
- Local PostgreSQL + pgvector.
- Local workspace storage.
- Local Trail Pack import/export.
- LLM provider configured by environment variables.

SaaS later means:

- Auth.
- Multi-user workspaces.
- Object storage.
- Billing.
- Rate limits.
- Public Trail registry.
- Moderation.
- Organization/school accounts.

The main MVP risk is learning experience quality, not SaaS infrastructure.

## Planned MVP Features

- Trail creation from topic, goal, and target depth.
- Concept graph viewer with statuses and concept levels.
- Concept-aware Socratic tutor.
- Mastery and level-up quiz flow.
- Source provenance rules.
- Safe public Trail Pack export.
- Trail Pack import into a workspace.
- Research trace and local hydration after the core loop works.

## Non-Goals For The First Milestone

- No PDF ingestion as the first milestone.
- No hosted SaaS marketplace.
- No billing.
- No school admin dashboard.
- No complex multi-agent framework.
- No public sharing of uploaded/source-derived content.

## Safety Model

Public Trail Packs share learning structure, not private content.

Public export may include:

- Graph structure.
- Concept titles.
- Learning objectives.
- Abstract mastery check labels.
- Public source links and metadata.
- Research trace.

Public export must exclude:

- Uploaded files.
- Raw source text.
- Chunks.
- Embeddings.
- Private notes.
- Chat history.
- Mastery records by default.
- Generated summaries from private/user-uploaded sources.
- Generated quizzes from private/user-uploaded sources.

## Intended Stack

The docs describe the intended rebuild stack:

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector |
| ORM / migrations | SQLAlchemy 2 + Alembic |
| Frontend | Next.js, TypeScript |
| Graph UI | React Flow for MVP or Sigma.js if already working |
| LLM routing | LiteLLM |
| Tests | pytest, frontend typecheck/test tooling |
| Tracing | Phoenix/OpenTelemetry later, optional on day one |

This repository was reset before implementation. Treat the docs as the current source of truth until the new app scaffold exists.

## Documentation

Start here:

- [docs/REBUILD_PLAN.md](docs/REBUILD_PLAN.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)
- [docs/TRAIL_PACK_SPEC.md](docs/TRAIL_PACK_SPEC.md)
- [docs/SOURCE_PROVENANCE.md](docs/SOURCE_PROVENANCE.md)
- [docs/MASTERY_MODEL.md](docs/MASTERY_MODEL.md)
- [docs/TUTOR_BEHAVIOUR.md](docs/TUTOR_BEHAVIOUR.md)
- [docs/HYDRATION.md](docs/HYDRATION.md)
- [docs/TEST_PLAN.md](docs/TEST_PLAN.md)
- [docs/CODEX.md](docs/CODEX.md)

## Planned Local Commands

These commands should exist after the foundation scaffold is implemented:

```bash
# local infra
docker compose up -d

# backend
pytest
alembic upgrade head
uvicorn backend.app.main:app --reload

# frontend
cd apps/web
npm run dev
npm run typecheck
```

If the scaffold changes these commands, update this README and `docs/CODEX.md` in the same PR.
