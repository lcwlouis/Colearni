# Colearni

> A Socratic AI tutor that grounds every answer in your own study materials — quizzing you to mastery, not just answering your questions.

## What is Colearni?

Most AI assistants give you the answer. Colearni makes you earn it. Upload your lecture notes, textbooks, or any study material, and Colearni builds a personal knowledge graph from them. When you ask a question, the tutor uses Socratic dialogue — guiding questions, hints, partial explanations — until you demonstrate understanding. Only then does it switch to direct answers.

This matters because passive reading doesn't build retention. Colearni forces active recall: you explain your thinking, attempt quiz questions, and get graded on short-form answers before the system credits you with mastery of a concept. The knowledge graph lets you browse the conceptual landscape of your own documents, identify gaps, and drill the topics you haven't yet mastered.

The system is designed for students and self-learners who want something more rigorous than a chatbot — a tutor that tracks what you know and holds you to it.

---

## Key Innovations

### Hybrid Retrieval with Reciprocal Rank Fusion
When you ask a question, the system runs two independent searches simultaneously: pgvector cosine similarity over chunk embeddings, and PostgreSQL full-text search (`tsvector`) over the same documents. The results are merged using Reciprocal Rank Fusion (RRF, from the IR literature) with a weighted score: `0.6 × 1/(k + vector_rank) + 0.4 × 1/(k + fts_rank)`. This gets you keyword precision (FTS finds exact terminology) and semantic flexibility (vector search finds paraphrased concepts) in a single query, without needing a separate reranker service.

### Mastery-Gated Teaching Mode
Every response is shaped by what the system knows you've already proven. Concepts start in an unlearned state. The tutor defaults to Socratic mode — asking questions rather than lecturing. After you pass a level-up quiz on a concept, the mastery flag flips and the tutor switches to direct explanations for that concept. This isn't just a UI toggle: mastery state is loaded at the start of every chat turn and wired into the prompt context, so the LLM's behavior changes deterministically based on what you've demonstrated, not just what you've asked.

### Three-Pass Concept Resolution with Hard Budget Caps
When new documents are ingested, raw concepts and edges are extracted per chunk. The online resolver then disambiguates each extracted concept against the canonical graph using a three-pass cascade: (1) lexical similarity against existing concept names and aliases, (2) vector similarity search, (3) LLM disambiguation — but only if the first two passes are inconclusive. Thresholds and margin checks at each pass avoid unnecessary LLM calls. Hard budget caps (max 3 LLM calls per chunk, 50 per document) prevent runaway API costs on large uploads.

### Offline Graph Gardener with Cost-Controlled Clustering
After ingestion marks nodes as "dirty," a background `GraphGardener` job periodically consolidates the canonical concept graph: clustering similar nodes, merging duplicates, and pruning stale aliases. The gardener is hard-limited to 30 LLM calls and 50 clusters per run, with explicit stop-reason emission when budgets are hit. This keeps the knowledge graph clean without unbounded LLM usage, and the explicit stop reasons make cost behavior auditable in traces.

### Evidence-First Citation Policy with Post-Generation Verification
Every user-visible tutor response must be built from `EvidenceItem[]` + `Citation[]` — there's no code path that lets the LLM respond without a grounding evidence set. After generation, a verifier checks that every citation references a known evidence item, has the correct source label, and contains no duplicates. In strict grounded mode, the system refuses to answer if the evidence is insufficient rather than hallucinating. This makes hallucination structurally harder, not just prompting-harder.

### Versioned Prompt Assets via a File-Based Registry
Prompts live as Markdown files in `core/prompting/assets/` with YAML front-matter specifying task type and version. A `PromptRegistry` singleton loads and caches them at runtime. This means prompt changes are tracked in git like code, can be versioned independently of application logic, and can be A/B tested by swapping the version loaded — without touching the orchestration layer.

### Learner Profile Snapshots for Personalized Context
Every chat turn assembles a live learner snapshot: weak topics (low mastery), strong topics (high mastery), the current learning frontier (adjacent concepts the learner hasn't touched), and a review queue (concepts due for spaced repetition). This snapshot is serialized as a summary string and injected into the tutor prompt, so the LLM's pedagogical choices — whether to push you forward or reinforce gaps — are informed by your actual learning state across the full workspace, not just the current conversation.

---

## Architecture

```mermaid
flowchart TB
  subgraph Frontend ["Next.js Frontend"]
    UI[Chat / Quiz UI]
    GRAPH_UI[Sigma.js Graph Explorer]
  end

  subgraph API ["FastAPI API"]
    ROUTER[Route Layer]
  end

  subgraph Domain ["Domain Logic"]
    TUTOR[TutorAgent\nSocratic / Direct]
    QUIZ[LevelUpQuizAgent\nGenerate + Grade]
    PRAC[PracticeAgent\nFlashcards + Mini-Quizzes]
    RETRIEVER[HybridRetriever\nVector + FTS → RRF]
    RESOLVER[GraphResolver\nOnline Disambiguation]
    GARD[GraphGardener\nOffline Consolidation]
  end

  subgraph DB ["PostgreSQL 16"]
    VEC[(pgvector\nEmbeddings)]
    FTS[(tsvector\nFull-Text)]
    GRAPH_DB[(Graph Tables\nConcepts + Edges)]
    MASTERY[(Mastery + Attempts)]
  end

  UI --> ROUTER
  GRAPH_UI --> ROUTER
  ROUTER --> TUTOR
  ROUTER --> QUIZ
  ROUTER --> PRAC
  TUTOR --> RETRIEVER
  RETRIEVER --> VEC
  RETRIEVER --> FTS
  TUTOR --> MASTERY
  QUIZ --> MASTERY
  RESOLVER --> GRAPH_DB
  GARD --> GRAPH_DB
  ROUTER --> OBS[OpenTelemetry\nArize Phoenix]
```

**FastAPI routes** are intentionally thin — they validate input, call domain functions, and return output. No business logic lives in routes.

**Domain layer** contains all orchestration: the TutorAgent decides response style from mastery and turn plan; the LevelUpQuizAgent generates MCQ + short-answer cards and grades submissions (MCQ deterministic, short-answer via LLM rubric); the HybridRetriever merges vector and FTS results; the GraphResolver runs the three-pass concept disambiguation pipeline.

**PostgreSQL** is the single data store for everything: chunks, embeddings (pgvector), full-text search indexes (tsvector), the canonical concept graph, mastery records, quiz attempts, and session history. No separate vector database needed.

**Frontend** uses Sigma.js (WebGL) backed by graphology for the interactive concept graph explorer, with MiniSearch for client-side fuzzy node search.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn | HTTP API and async serving |
| ORM / Migrations | SQLAlchemy 2.0, Alembic, psycopg 3 | Database access and schema versioning |
| Database | PostgreSQL 16 + pgvector | Chunks, embeddings, FTS, graph, mastery |
| LLM Routing | LiteLLM | Multi-provider abstraction (OpenAI, Gemini, DeepSeek, OpenRouter) |
| Embeddings | OpenAI `text-embedding-3-small` | Semantic chunk embeddings (1536-dim) |
| Frontend | Next.js 16, React 19, TypeScript | Web application |
| Graph Visualization | Sigma.js (WebGL), graphology, @react-sigma | Interactive concept graph explorer |
| Client Search | MiniSearch | Client-side fuzzy concept search |
| Math Rendering | KaTeX | LaTeX math in chat and quizzes |
| Observability | OpenTelemetry + Arize Phoenix | Distributed tracing and LLM call inspection |
| Infrastructure | Docker, Docker Compose | Local PostgreSQL + Phoenix |
| Testing | pytest, Vitest, ruff | Backend tests, frontend tests, linting |

---

## Features

- **Socratic tutoring** — the tutor asks guiding questions by default, switching to direct explanations only after you've demonstrated mastery through a quiz
- **Mastery tracking** — per-concept learned/unlearned state, persisted across sessions and workspaces
- **Level-up quizzes** — in-chat card UI with MCQ (deterministic grading) and short-answer questions (LLM rubric grading); passing updates mastery
- **Practice mode** — flashcards and mini-quizzes for spaced repetition without affecting mastery state
- **Knowledge graph explorer** — browse the canonical concept graph built from your documents, visualized with Sigma.js WebGL with force-atlas layout and fuzzy search
- **Document ingestion** — upload Markdown, text, or PDF files; the system chunks, embeds, and extracts concepts automatically
- **Hybrid grounded mode** — hybrid (keyword + semantic) or strict (refuse if evidence is insufficient)
- **Streaming responses** — SSE streaming for real-time chat with live reasoning summary display
- **Research agent** — surfaces additional source candidates to expand the workspace knowledge base
- **"I'm Feeling Lucky"** — suggests adjacent unexplored concepts from the knowledge graph
- **Magic link auth** — passwordless session-based authentication
- **Multi-provider LLM** — route to OpenAI, Gemini, DeepSeek, or any OpenRouter model via env config

---

## Future Potential

The core graph-and-mastery architecture is model-agnostic and workspace-scoped, making it straightforward to extend. Near-term additions include PDF visual ingestion (crop/zoom for figures), a freeform multi-agent runtime where specialized sub-agents handle research, explanation, and assessment independently, and a conductor layer with typed turn planning that makes routing decisions auditable in traces.

The workspace model maps naturally to institutional use cases: a university course could be a workspace, with the canonical concept graph encoding the course ontology and mastery records tracking individual student progress. Integration with an LMS (Canvas, Moodle) could surface Colearni's mastery signals directly in gradebook views, or trigger review sessions when spaced-repetition half-life expires for a concept cluster.

The knowledge graph is exportable and queryable, which opens a path to personalized curriculum generation — given a target concept and a learner's current mastery frontier, the graph can compute the minimum prerequisite path and generate a structured study plan automatically.

---

## Getting Started

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.11 | [python.org/downloads](https://www.python.org/downloads/) |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org/) |
| Docker Desktop | Latest | [docker.com/get-started](https://www.docker.com/get-started/) |

Docker Desktop must be running before you start the database. Verify with `docker ps` — if it returns a list (even empty) rather than an error, Docker is running.

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/Colearni.git
cd Colearni
```

### 2. Install backend dependencies

Python libraries the API server and domain logic need:

```bash
pip install -e ".[dev]"
```

### 3. Install frontend dependencies

Node packages for the Next.js web app:

```bash
cd apps/web && npm install && cd ../..
```

### 4. Start the database

Spins up PostgreSQL 16 with pgvector in a Docker container:

```bash
./scripts/start-infra.sh
```

You should see `colearni-db` appear in `docker ps` and a health-check message. If you see a port conflict on 5432, another PostgreSQL instance is already running — stop it or change `APP_DATABASE_URL` to use a different port.

### 5. Configure environment variables

Copy the example files:

```bash
cp .env.example .env
cd apps/web && cp .env.example .env.local && cd ../..
```

Open `.env` in a text editor. Required values to fill in:

---

**`APP_OPENAI_API_KEY`** *(required for default config)*
What it does: Used for both chat/tutor LLM calls and embeddings generation.
Where to get it: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) → Create new secret key.
Example: `APP_OPENAI_API_KEY=sk-proj-abc123...`

---

**`APP_DATABASE_URL`** *(pre-filled, change only if your DB port differs)*
What it does: SQLAlchemy connection string for PostgreSQL.
Default: `postgresql+psycopg://colearni:colearni@localhost:5432/colearni`

---

**`APP_EMBEDDING_MODEL`** *(optional, defaults to `text-embedding-3-small`)*
What it does: Which OpenAI embedding model to use. Must match `APP_EMBEDDING_DIM`.
Example: `APP_EMBEDDING_MODEL=text-embedding-3-small` (dim=1536)

---

**Alternative LLM providers** *(all optional — only set the key for providers you want to use)*

| Variable | Provider | Where to get the key |
|---|---|---|
| `APP_DEEPSEEK_API_KEY` | DeepSeek | [platform.deepseek.com](https://platform.deepseek.com/) |
| `APP_GEMINI_API_KEY` | Google Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `APP_OPENROUTER_API_KEY` | OpenRouter | [openrouter.ai/keys](https://openrouter.ai/keys) |

To use a non-OpenAI provider, also set `APP_GRAPH_LLM_PROVIDER` and `APP_GRAPH_LLM_MODEL` (e.g., `litellm` and `gemini/gemini-2.0-flash`).

---

**Observability** *(optional — skip unless you want Phoenix tracing)*

`APP_OBSERVABILITY_ENABLED=true` with `APP_OBSERVABILITY_OTLP_ENDPOINT=http://localhost:6006` enables OpenTelemetry traces sent to Arize Phoenix. Start Phoenix with `make phoenix` before the backend.

---

The `apps/web/.env.local` file can stay as-is for local development — it points the frontend at `http://127.0.0.1:8000` by default.

### 6. Initialize the database

Creates all tables, indexes, and pgvector extensions:

```bash
make db-upgrade
```

You should see `INFO [alembic.runtime.migration] Running upgrade ... -> head`. Only needed once per environment (and again after pulling new migrations).

### 7. Run the application

**Backend** (in one terminal):

```bash
make dev
```

The API will be available at `http://localhost:8000`. You should see `Application startup complete.` in the terminal.

**Frontend** (in a second terminal):

```bash
cd apps/web && npm run dev
```

Open `http://localhost:3000` in your browser.

### Verify everything is working

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

---

## Development

```bash
make lint          # ruff check — Python linting
make test          # pytest -q — run all backend tests
pytest tests/domain/chat/ -v              # run a specific test directory
pytest tests/api/test_chat.py::test_foo   # run a single test
make db-revision m="add new table"        # create a new Alembic migration
make db-reset                             # drop and recreate the DB (dev only)
cd apps/web && npm run typecheck          # TypeScript type checking
cd apps/web && npm run test               # Vitest frontend tests
make phoenix                              # start Arize Phoenix trace UI on :6006
```

---

## License

MIT © 2025 Colearni
