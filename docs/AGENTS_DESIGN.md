# Agent Architecture

This document catalogues every agent in the CoLearni codebase, their
responsibilities, inter-agent connections, and the call flows they
participate in. Use it to understand how connected or disconnected the
agents are.

---

## Agents Inventory

### Chat Domain (`domain/chat/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 1 | Tutor Response Agent | `tutor_agent.py`, `response_service.py` | Yes |
| 2 | Query Analyzer Agent | `query_analyzer.py` | Yes |
| 3 | Social Intent Fast-Path | `social_turns.py` | Optional |
| 4 | Concept Resolver | `concept_resolver.py` | No |
| 5 | Streaming Chat Response | `stream.py` | Yes (delegates) |

**1. Tutor Response Agent** — `domain/chat/tutor_agent.py` + `domain/chat/response_service.py`

- **Purpose:** Generates tutoring responses in socratic or direct style
  based on evidence and learner mastery.
- **LLM calls:** `generate_tutor_text()` with `tutor_socratic_v1` /
  `tutor_direct_v1` prompts.
- **Inputs:** Query, evidence, mastery status, grounding mode, history,
  assessment context, doc summaries, graph context.
- **Outputs:** Generated tutor text + `GenerationTrace`.
- **Called by:** `domain/chat/respond.py` (main pipeline),
  `domain/chat/stream.py` (streaming).
- **Observability:** Spans via `generate_tutor_text_traced()`.

**2. Query Analyzer Agent** — `domain/chat/query_analyzer.py`

- **Purpose:** Classifies user queries into intents (`learn`, `practice`,
  `level_up`, `explore`, `social`, `clarify`) and signals retrieval needs.
- **LLM calls:** `generate()` with `routing_query_analyzer_v1` prompt.
- **Inputs:** User query, conversation history summary.
- **Outputs:** `QueryAnalysis` (intent, requested_mode, needs_retrieval,
  keywords, concept_hints).
- **Called by:** `domain/chat/respond.py` (THINKING phase),
  `domain/chat/stream.py`.
- **Feeds into:** `domain/chat/turn_plan.py:build_turn_plan()`.

**3. Social Intent Fast-Path** — `domain/chat/social_turns.py`

- **Purpose:** Routes casual/greeting queries away from evidence retrieval
  for lower latency.
- **LLM calls:** `generate_tutor_text()` (optional; falls back to
  rule-based).
- **Called by:** `domain/chat/respond.py` early in THINKING phase.

**4. Concept Resolver** — `domain/chat/concept_resolver.py`

- **Purpose:** Maps user queries to canonical learning concepts; suggests
  concept switches.
- **LLM calls:** None (pure DB-driven matching with heuristics).
- **Called by:** `domain/chat/respond.py` (SEARCHING phase).
- **Output feeds into:** Evidence planner and turn plan.

**5. Streaming Chat Response** — `domain/chat/stream.py`

- **Purpose:** Orchestrates streaming tutor response via SSE.
- Mirrors logic from `respond.py`, calls same helpers.
- **Key span:** `"chat.stream"` parent, with `"chat.stream.socratic"` for
  tutor LLM call at line 390.

### Learning Domain (`domain/learning/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 6 | Quiz Generation Flow | `quiz_flow.py` | Yes |
| 7 | Quiz Grading | `quiz_grading.py` | Yes |
| 8 | Practice Quiz | `practice.py` | No (wraps quiz_flow) |

**6. Quiz Generation Flow** — `domain/learning/quiz_flow.py`

- **Purpose:** Orchestrates quiz creation (generate items) and submission
  (grade answers).
- **LLM calls:** `generate_tutor_text()` for item generation +
  short-answer grading.
- **Observability:** CHAIN spans for `"quiz.create"`, `"quiz.submit"`.

**7. Quiz Grading** — `domain/learning/quiz_grading.py`

- **Purpose:** Grades quiz submissions (MCQ deterministic, short-answer
  via LLM).
- **Fallback:** Rubric keyword matching if LLM unavailable.

**8. Practice Quiz** — `domain/learning/practice.py`

- **Purpose:** Practice quiz lifecycle with novelty tracking.
- Wraps `quiz_flow.py`.

### Graph Domain (`domain/graph/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 9 | Raw Graph Extraction | `extraction.py` | Yes |
| 10 | Online Graph Resolver | `resolver.py:OnlineResolver` | Yes |
| 11 | Graph Pipeline | `pipeline.py` | No (orchestrator) |
| 12 | Graph Gardener | `gardener.py` | Yes |

**9. Raw Graph Extraction** — `domain/graph/extraction.py`

- **Purpose:** Extracts concepts + edges from text chunks using
  schema-validated LLM output.
- **Called by:** `domain/graph/pipeline.py:build_graph_for_chunks()`.

**10. Online Graph Resolver** — `domain/graph/resolver.py:OnlineResolver`

- **Purpose:** Merges extracted concepts into canonical graph via
  lexical/vector matching + LLM disambiguation.
- **LLM calls:** `disambiguate()` and `disambiguate_batch()`.
- **Called by:** `domain/graph/pipeline.py`.

**11. Graph Pipeline** — `domain/graph/pipeline.py`

- **Purpose:** End-to-end graph building (chunking, extraction,
  resolution).
- **Called by:** `domain/ingestion/post_ingest.py`.

**12. Graph Gardener** — `domain/graph/gardener.py`

- **Purpose:** Offline graph maintenance — merges similar canonical
  concepts within bounds.
- **LLM calls:** `disambiguate_batch()`.

### Ingestion Domain (`domain/ingestion/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 13 | Document Summary | `post_ingest.py:generate_document_summary()` | Yes |
| 14 | Post-Ingest Pipeline | `post_ingest.py:run_post_ingest_tasks()` | No (orchestrator) |

**13. Document Summary** — `domain/ingestion/post_ingest.py:generate_document_summary()`

- **Purpose:** Generates 2–3 sentence document summaries.
- **LLM calls:** `generate_tutor_text()`.

**14. Post-Ingest Pipeline** — `domain/ingestion/post_ingest.py:run_post_ingest_tasks()`

- **Purpose:** Orchestrates embeddings, summary, graph extraction after
  upload.
- **Delegates to:** Embedding pipeline + Graph pipeline.

### Embeddings Domain (`domain/embeddings/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 15 | Embedding Pipeline | `pipeline.py` | No (embedding model) |

**15. Embedding Pipeline** — `domain/embeddings/pipeline.py`

- **Purpose:** Vectorizes chunk text for semantic retrieval.
- **Calls:** `embedding_provider.embed_texts()`.

### Retrieval Domain (`domain/retrieval/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 16 | Evidence Planner | `evidence_planner.py` | No |
| 17 | Vector Retriever | `vector_retriever.py` | No |
| 18 | FTS Retriever | `fts_retriever.py` | No |
| 19 | Hybrid Retriever | `hybrid_retriever.py` | No |

**16. Evidence Planner** — `domain/retrieval/evidence_planner.py`

- **Purpose:** Plans retrieval strategy (budget, passes, expansion).
- No LLM calls (deterministic planning).

**17. Vector Retriever** — `domain/retrieval/vector_retriever.py`

- **Purpose:** Semantic search via embeddings.

**18. FTS Retriever** — `domain/retrieval/fts_retriever.py`

- **Purpose:** Full-text search via Postgres tsvector.

**19. Hybrid Retriever** — `domain/retrieval/hybrid_retriever.py`

- **Purpose:** Combines vector + FTS with weighted RRF.

### Research Domain (`domain/research/`)

| # | Agent | Source | LLM? |
|---|-------|--------|------|
| 20 | Query Planner | `query_planner.py` | Yes |

**20. Query Planner** — `domain/research/query_planner.py`

- **Purpose:** Generates bounded search queries for candidate discovery.
- **LLM calls:** `generate_tutor_text()` with JSON schema.

---

## Agent Connection Map

### Chat Turn Flow (primary user-facing flow)

```
API Endpoint (apps/api/routes/chat.py)
  └─ generate_chat_response() / generate_chat_response_stream()
     ├─ [1] Query Analyzer Agent ← LLM call (classification)
     ├─ [2] Concept Resolver ← DB lookup (no LLM)
     ├─ [3] Evidence Planner ← deterministic planning
     │    └─ execute_evidence_plan()
     │         └─ Hybrid Retriever
     │              ├─ Vector Retriever (pgvector NN)
     │              └─ FTS Retriever (tsvector)
     └─ [4] Tutor Response Agent ← LLM call (main generation)
          └─ Span: "llm.chat.stream.socratic" or "llm.chat.stream"
```

### Ingestion Flow

```
Upload Endpoint
  └─ Post-Ingest Pipeline
     ├─ Embedding Pipeline (embed_texts)
     ├─ Document Summary Agent (LLM)
     └─ Graph Pipeline
          ├─ Raw Graph Extraction Agent (LLM)
          └─ Online Resolver Agent (LLM disambiguation)
```

### Learning Flow

```
Quiz Endpoint
  └─ Quiz Generation Flow
     ├─ Item Generation (LLM)
     └─ Quiz Grading (LLM or rubric fallback)
```

### Background Maintenance

```
Graph Gardener (bounded offline LLM)
```

---

## Key Observations

- **Chat turn = 2 LLM calls.** Query Analyzer (lightweight classification)
  + Tutor Response (main generation). The query analyzer is a necessary
  router that prevents expensive retrieval for social intents.
- **Loosely coupled agents.** They share contracts (`core/contracts.py`)
  but don't call each other directly except through orchestration layers
  (`respond.py`, `pipeline.py`, `quiz_flow.py`).
- **Ingestion and chat are fully decoupled.** Ingestion writes to the
  database (chunks, embeddings, graph); chat reads from it. There is no
  runtime dependency between the two flows.
- **Graph ↔ Chat connection is narrow.** The graph domain connects to
  chat only through concept resolution and evidence context — never
  through direct agent-to-agent calls.
- **LLM vs. logic split.** Of the 20 agents, 13 make LLM calls and 7 are
  pure logic/infrastructure (Concept Resolver, Evidence Planner, Practice
  Quiz, Graph Pipeline, Post-Ingest Pipeline, Embedding Pipeline, Hybrid/
  Vector/FTS Retrievers).
