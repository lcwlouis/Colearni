# CoLearni — Project Context for Claude Chat

## What is CoLearni?

CoLearni is a **local-ready, graph-first personal learning system**. The product shape:

```
personal learning workspace
+ concept graph / Trail
+ Socratic tutor
+ mastery state
+ source-aware retrieval
+ safe community Trail sharing
```

It is NOT a generic RAG chatbot. The graph, mastery model, and source provenance are first-class product primitives.

**Product spine:**
```
Create Trail → Learn concept → Level-up quiz → Graph mastery update
→ Safe Trail Pack export → Trail Pack import/fork → Optional research trace
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLAlchemy (async) + Alembic + PostgreSQL/pgvector |
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui |
| Chat UI | `@assistant-ui/react` with custom `LocalRuntime` adapter |
| Graph | `@xyflow/react` + `dagre` for per-Trail concept graph |
| LLM | Direct provider calls via `openai` SDK (OpenAI, OpenRouter, DeepSeek, Gemini, Ollama) or Anthropic SDK |
| Tests | pytest (backend), Jest (frontend) |
| Infra | Docker Compose (local dev) |

**Key constraint:** No LiteLLM. Direct provider calls only.

---

## Repository Structure

```
backend/
  app/
    api/        # Thin FastAPI routes
    services/   # Business logic
    agents/     # LLM orchestration
      prompts/  # Versioned Markdown prompt files
    models/     # SQLAlchemy ORM
    schemas/    # Pydantic schemas
  alembic/
  tests/

apps/
  web/          # Next.js frontend

docs/           # Architecture, API contract, plan docs
```

---

## Current Build State (as of 2026-05-29)

### What's fully implemented:

- **Workspace + Trail CRUD** — workspace-scoped API, trail list/detail/delete
- **Trail generation** — graph JSON via LLM with validation, SSE progress stream
- **Graph viewer** — React Flow + dagre, Learn/Inspect mode split, search/filter, concept side panel
- **Tutor backend** — Socratic/direct/repair/quiz_prompt/explore/free_explore modes, SSE streaming, conversation persistence, mastery-gated tools, reasoning traces, provider thinking events
- **Tutor frontend** — assistant-ui LocalRuntime adapter, Markdown/KaTeX/Mermaid/code blocks, reasoning toggle, message edit/regenerate
- **Mastery + Quiz** — mastery records, level-up and practice quizzes, mixed question types (multiple_choice/short_answer/long_answer/code), per-question grading feedback, backend quiz drafts with dedup/advisory lock, quiz answer guard (deterministic + LLM semantic)
- **Source provenance + Trail Pack export/import** — sanitizer, safe JSON export, import/fork with validation
- **Provider tool abstraction** — normalized tool calls/results across OpenAI/Anthropic/OpenRouter
- **Learning dashboard** — Continue Learning, per-Trail progress, recommended next concept
- **Source ingestion** — private upload storage, PDF/markdown/plaintext parser, heading-aware chunking, pgvector embeddings (optional), auto-linking
- **Retrieval tooling** — `search_sources`, `read_document_section`, `get_concept_sources`, `get_graph_neighbourhood` — multi-turn LLM tool loop with budget/dedup/parallel execution
- **Conversation summaries + learner state** — LLM summarizer, quiz attempt summaries, mutable learner state, prior-attempt context in quiz generation
- **Concept primers (Phase 13.5a)** — per-concept orientation overview + key terms + sample questions, cached in `metadata_json`, resilient background generation, single-flight dedup, streaming SSE endpoint
- **Marketing site** — marketing routes, fake login (localStorage workspace), Terms/Privacy pages

### Not yet implemented:
- True per-message citation/source parts and quotes
- Automatic conversation summarization (the LLM summarizer exists but isn't auto-triggered yet)
- Dark mode
- Trail generation background jobs (refresh-resilient)
- Safety + content guardrails (Phase 17.5)
- Deployment/SaaS features

---

## Key Architectural Decisions

### Tutor Two-Phase Call
1. **Classifier call** (max 48 tokens, temp 0): emits exactly one control line `<mode .../>` or `<tool .../>`
2. **Answer call** (up to `LLM_TUTOR_MAX_TOKENS`): streams the learner-visible response

Weak models that emit prose instead of a tag fall back to keyword-based mode inference (`_infer_mode_from_message`).

### Mastery Gating
- `not_started` / `learning` / `needs_review` → Socratic, repair, bounded explore
- `mastered` → unlocks `direct` (crisp answers) and `free_explore`
- Gated `direct` teaches (guided walkthrough + gentle check question) instead of refusing

### Quiz Answer Guard
Two layers protect against quiz answer extraction in chat:
1. Deterministic exact-match of quiz prompts
2. LLM semantic guard (`quiz_answer_guard.v1.md`) for paraphrased attempts

### Source Provenance Layers
```
Public: graph structure, learning objectives, research source links/metadata
Private: uploaded files, chunks, embeddings, chat history, mastery records, quiz attempts
```
Export sanitizer is a hard backend boundary, not a UI convenience.

### Retrieval (Dual-Tier)
- Tier 1: `search_sources` → chunk search returning `line_start`/`line_end` navigation metadata
- Tier 2: `read_document_section` → reads N lines from `SourceRevision.raw_text` (markdown)
- Budget: 3 tool calls per turn, parallel execution, per-turn dedup cache

---

## Active Branch: `rebuild`

### Currently modified files (uncommitted):
- `apps/web/__tests__/QuizPanel.test.tsx` — quiz panel tests
- `apps/web/app/trails/[id]/components/ConceptPanel.tsx` — concept side panel
- `apps/web/app/trails/[id]/components/QuizPanel.tsx` — quiz UI
- `apps/web/components/assistant-ui/markdown-text.tsx` — markdown renderer
- `apps/web/lib/api.ts` — API client
- `apps/web/lib/types.ts` — shared types
- `backend/app/agents/prompts/quiz_grader.v1.md` — quiz grading prompt
- `backend/app/agents/prompts/tutor_base.v1.md` — tutor classifier prompt
- `backend/app/api/concepts.py` — concept routes
- `backend/app/models/` — ORM models (conversation, learner_state new)
- `backend/app/schemas/mastery.py` — mastery schemas
- `backend/app/services/conversations.py` / `quizzes.py` / `tutor.py` — core services
- New files: `QuizMarkdown.tsx`, `markdown.ts`, learner_state migration, conversation_summaries, learner_state, quiz_guard services and tests

---

## Key Docs in the Repo

- `docs/REBUILD_PLAN.md` — phased build plan with current snapshot
- `docs/ARCHITECTURE.md` — system architecture and data model
- `docs/API.md` — full API contract
- `docs/CURRENT_VARIANT.md` — tutor/quiz implementation details (read before changing tutor/quiz)
- `docs/PROMPTS.md` — prompt registry format
- `docs/FRONTEND.md` — frontend conventions and component guidance
- `docs/MASTERY_MODEL.md` — mastery statuses, transitions, scoring
- `docs/TUTOR_BEHAVIOUR.md` — tutor modes and context management
- `docs/TEST_PLAN.md` — required test coverage by phase

---

## Local Dev Commands

```bash
# Backend
pytest
alembic upgrade head
uvicorn backend.app.main:app --reload

# Frontend
cd apps/web
npm run dev
npm run typecheck
npm run test

# Infrastructure
docker compose up -d
```

---

## Product North Star

> CoLearni should feel like a mentor or coach, not a search engine.

The tutor teaches through Socratic questioning, not answer-dumping. Mastery gating is motivating, not punitive. Trail sharing is safe by default — graph structure and learning objectives, never private content.
