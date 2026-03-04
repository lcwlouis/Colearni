# LLM Call Flows

This document maps the implementation-level LLM call paths in the current codebase.

## Scope

All model traffic funnels through the `GraphLLMClient` protocol in `core/contracts.py` and is built by `adapters/llm/factory.py`.

There are only three provider primitives:

1. `generate_tutor_text`
2. `extract_raw_graph`
3. `disambiguate`

Every higher-level "agent" or background job eventually routes into one of those three methods.

## Call Inventory

| ID | Entrypoint | Primitive | Main purpose | Bound / fallback |
| --- | --- | --- | --- | --- |
| C1 | Chat social fast-path | `generate_tutor_text` | Short social reply | Falls back to local template reply |
| C2 | Chat grounded tutor response | `generate_tutor_text` | Main tutor answer | Falls back to deterministic tutor text |
| C3 | Post-ingest summary | `generate_tutor_text` | 2-3 sentence document summary | Silent skip on failure |
| C4 | Graph extraction | `extract_raw_graph` | Extract raw concepts and edges per chunk | Schema validation required |
| C5 | Online resolver disambiguation | `disambiguate` | Merge-vs-create decision for ambiguous concepts | Budgeted, else deterministic fallback |
| C6 | Graph gardener cluster merge | `disambiguate` | Pick canonical concept inside a dirty cluster | Budgeted, else skip cluster |
| C7 | Level-up quiz generation | `generate_tutor_text` | Produce quiz items JSON | Up to 3 attempts, then auto-generated quiz |
| C8 | Short-answer quiz grading | `generate_tutor_text` | Grade short answers with JSON rubric output | Falls back to keyword grading if no LLM |
| C9 | Practice flashcard generation | `generate_tutor_text` | Generate transient flashcards | Request fails if generation is invalid |
| C10 | Practice quiz generation | `generate_tutor_text` | Generate practice quiz items JSON | Up to 3 attempts, then fallback auto-items |
| C11 | Stateful flashcard generation | `generate_tutor_text` | Generate persisted flashcards with novelty filtering | Request fails if generation is invalid |

Background entrypoints reuse existing calls instead of adding new provider methods:

- `apps/jobs/quiz_gardener.py` reuses `C7`
- `apps/jobs/graph_gardener.py` reuses `C6`
- `domain/learning/practice.py::submit_practice_quiz` reuses `C8`

## Shared Provider Path

```mermaid
flowchart LR
  A["Agent or job"] --> B["GraphLLMClient"]
  B --> C["Observability wrapper"]
  C --> D{"Primitive"}
  D -->|"generate_tutor_text"| E["Text call"]
  D -->|"extract_raw_graph"| F["JSON schema extraction"]
  D -->|"disambiguate"| G["JSON schema merge decision"]
  E --> H{"Configured provider"}
  F --> H
  G --> H
  H -->|"openai"| I["OpenAI chat.completions.create"]
  H -->|"litellm"| J["litellm.completion"]
```

## Per-Call Flows

### C1. Chat Social Fast-Path

```mermaid
flowchart LR
  U["User social message"] --> API["POST /chat/respond"]
  API --> RESP["generate_chat_response"]
  RESP --> CLS{"Social intent?"}
  CLS -->|"no"| EXIT["Continue to grounded chat path"]
  CLS -->|"yes"| S["try_social_response"]
  S --> LLM["generate_tutor_text"]
  LLM --> OUT["AssistantResponseEnvelope social reply"]
  OUT --> DB["Persist chat turn"]
```

Notes:

- Runs before retrieval and evidence assembly.
- If the call fails, the code falls back to `build_social_response`.

### C2. Chat Grounded Tutor Response

```mermaid
flowchart LR
  U["User study question"] --> API["POST /chat/respond"]
  API --> RESP["generate_chat_response"]
  RESP --> RET["Retrieve ranked chunks"]
  RESP --> MEM["Load history, quiz summary, flashcard progress"]
  RET --> EVID["Evidence + citations"]
  MEM --> PROMPT["build_full_tutor_prompt"]
  EVID --> PROMPT
  PROMPT --> LLM["generate_tutor_text"]
  LLM --> VERIFY["verify_assistant_draft"]
  VERIFY --> OUT["Grounded assistant response"]
  OUT --> DB["Persist chat turn"]
```

Connections:

- Pulls quiz results into the prompt via `build_quiz_context`.
- Pulls practice state into the prompt via `load_flashcard_progress`.
- Uses document summaries produced by `C3`.

### C3. Post-Ingest Document Summary

```mermaid
flowchart LR
  UP["Document upload"] --> JOB["run_post_ingest_tasks"]
  JOB --> CH["Load first chunks"]
  CH --> SUM["generate_document_summary"]
  SUM --> LLM["generate_tutor_text"]
  LLM --> DOC["documents.summary"]
```

Connection:

- The stored document summary is later injected into the tutor prompt used by `C2`.

### C4. Raw Graph Extraction Per Chunk

```mermaid
flowchart LR
  UP["Document upload"] --> JOB["run_post_ingest_tasks"]
  JOB --> PIPE["build_graph_for_chunks"]
  PIPE --> LOOP["For each chunk"]
  LOOP --> EXT["extract_raw_graph_from_chunk"]
  EXT --> LLM["extract_raw_graph"]
  LLM --> NORM["Validate and normalize payload"]
  NORM --> RAW["Insert concepts_raw and edges_raw"]
```

Notes:

- This is one LLM extraction call per chunk.
- The extracted concepts then flow into `C5`.

### C5. Online Resolver Disambiguation

```mermaid
flowchart LR
  C4["Raw extracted concept"] --> RES["OnlineResolver.resolve_concept"]
  RES --> EXACT{"Exact alias match?"}
  EXACT -->|"yes"| MERGE["Merge without LLM"]
  EXACT -->|"no"| CANDS["Lexical and vector candidates"]
  CANDS --> DET{"Deterministic winner?"}
  DET -->|"yes"| MERGE
  DET -->|"no"| BUDGET{"LLM budget left?"}
  BUDGET -->|"no"| NEW["Create new canonical concept"]
  BUDGET -->|"yes"| LLM["disambiguate"]
  LLM --> APPLY["Merge into candidate or create new"]
  MERGE --> DB["Update canonical graph, aliases, provenance"]
  APPLY --> DB
  NEW --> DB
```

Notes:

- This is the main bounded merge-vs-create decision for ingestion.
- Edge endpoint resolution can also re-enter this same path.

### C6. Graph Gardener Cluster Merge

```mermaid
flowchart LR
  JOB["graph_gardener job"] --> SEED["Select dirty or recent canonical nodes"]
  SEED --> BLOCK["Lexical and vector blocking"]
  BLOCK --> CLUSTER["Connected components"]
  CLUSTER --> BUDGET{"Cluster and LLM budget left?"}
  BUDGET -->|"no"| STOP["Hard stop"]
  BUDGET -->|"yes"| LLM["disambiguate"]
  LLM --> DECIDE{"High-confidence merge?"}
  DECIDE -->|"no"| SKIP["Skip cluster"]
  DECIDE -->|"yes"| APPLY["Repoint edges and alias map"]
  APPLY --> DB["Deactivate merged concepts and stabilize target"]
```

Connection:

- Reuses the same `disambiguate` primitive as `C5`, but at cluster level against canonical nodes.

### C7. Level-Up Quiz Generation

```mermaid
flowchart LR
  ENTRY["Quiz route or quiz_gardener"] --> GEN["create_level_up_quiz"]
  GEN --> CTX["Load concept, neighbors, chunk excerpts, chat history"]
  CTX --> RETRY["Up to 3 generation attempts"]
  RETRY --> LLM["generate_tutor_text"]
  LLM --> VALIDATE{"Valid quiz JSON?"}
  VALIDATE -->|"no and attempts left"| RETRY
  VALIDATE -->|"no and exhausted"| AUTO["Fallback auto_items"]
  VALIDATE -->|"yes"| ITEMS["Normalized quiz items"]
  AUTO --> ITEMS
  ITEMS --> DB["Persist quiz and quiz_items"]
```

Connections:

- Called directly from the level-up quiz route.
- Also called indirectly by `quiz_gardener`.

### C8. Short-Answer Quiz Grading

```mermaid
flowchart LR
  ENTRY["Level-up submit or practice submit"] --> SUB["submit_level_up_quiz"]
  SUB --> LOAD["Load quiz items and answers"]
  LOAD --> SHORT{"Short-answer items present?"}
  SHORT -->|"no"| MCQ["Deterministic MCQ grading"]
  SHORT -->|"yes, no LLM"| FB["Keyword fallback grading"]
  SHORT -->|"yes, with LLM"| PROMPT["grading_prompt"]
  PROMPT --> LLM["generate_tutor_text"]
  LLM --> PARSE["Parse grading JSON"]
  PARSE --> MCQ
  FB --> MCQ
  MCQ --> OUT["Assemble feedback and score"]
  OUT --> DB["Persist attempt and optionally mastery"]
```

Connections:

- `submit_practice_quiz` delegates into this exact path with `update_mastery=False`.
- `submit_level_up_quiz` uses the same path with mastery updates enabled.

### C9. Practice Flashcard Generation

```mermaid
flowchart LR
  U["Practice flashcards request"] --> API["POST /practice/flashcards"]
  API --> GEN["generate_practice_flashcards"]
  GEN --> CTX["Load concept and adjacent concepts"]
  CTX --> LLM["generate_tutor_text"]
  LLM --> PARSE["Parse flashcards JSON"]
  PARSE --> OUT["Return flashcards"]
```

### C10. Practice Quiz Generation

```mermaid
flowchart LR
  U["Practice quiz request"] --> API["POST /practice/quizzes"]
  API --> GEN["create_practice_quiz"]
  GEN --> NOVEL["Load seen fingerprints and overfetch target"]
  NOVEL --> RETRY["Up to 3 generation attempts"]
  RETRY --> LLM["generate_tutor_text"]
  LLM --> VALIDATE{"Valid mixed quiz JSON?"}
  VALIDATE -->|"no and attempts left"| RETRY
  VALIDATE -->|"no and exhausted"| AUTO["Fallback auto_items"]
  VALIDATE -->|"yes"| FILTER["Novelty filtering"]
  AUTO --> FILTER
  FILTER --> SAVE["Delegate to create_level_up_quiz for persistence"]
```

Connection:

- Shares persistence and item-shaping logic with the level-up quiz flow after generation.

### C11. Stateful Flashcard Generation

```mermaid
flowchart LR
  U["Stateful flashcards request"] --> API["POST /practice/flashcards/stateful"]
  API --> GEN["generate_stateful_flashcards"]
  GEN --> NOVEL["Load seen fingerprints"]
  NOVEL --> LLM["generate_tutor_text"]
  LLM --> PARSE["Parse flashcards JSON"]
  PARSE --> FILTER["Novelty filter and dedupe"]
  FILTER --> BANK["Persist flashcard bank, progress, run metadata"]
  BANK --> OUT["Return persisted flashcards"]
```

## Overall Graph

```mermaid
flowchart TB
  subgraph UserFacing["User-facing entrypoints"]
    CHAT["Chat respond"]
    QUIZ["Level-up quiz create"]
    SUBMIT["Quiz submit"]
    PFLASH["Practice flashcards"]
    PQUIZ["Practice quiz create"]
    PSUB["Practice quiz submit"]
    SFLASH["Stateful flashcards"]
  end

  subgraph Background["Background entrypoints"]
    INGEST["Post-ingest tasks"]
    QG["Quiz gardener"]
    GG["Graph gardener job"]
  end

  subgraph CallSites["LLM call sites"]
    C1["C1 Social reply"]
    C2["C2 Grounded tutor reply"]
    C3["C3 Document summary"]
    C4["C4 Raw graph extraction"]
    C5["C5 Online resolver disambiguation"]
    C6["C6 Gardener merge decision"]
    C7["C7 Level-up quiz generation"]
    C8["C8 Short-answer grading"]
    C9["C9 Practice flashcards"]
    C10["C10 Practice quiz generation"]
    C11["C11 Stateful flashcards"]
  end

  subgraph Stores["Shared state"]
    DOCS["Documents and chunks"]
    GRAPH["Canonical graph"]
    QUIZZES["Quizzes and attempts"]
    MASTERY["Mastery"]
    FLASH["Flashcard bank and progress"]
  end

  subgraph Provider["Shared provider path"]
    CLIENT["GraphLLMClient"]
    OBS["Observability wrapper"]
    SDK{"Configured provider"}
    OPENAI["OpenAI chat.completions.create"]
    LITELLM["litellm.completion"]
  end

  CHAT --> C1
  CHAT --> C2
  QUIZ --> C7
  SUBMIT --> C8
  PFLASH --> C9
  PQUIZ --> C10
  PSUB --> C8
  SFLASH --> C11
  INGEST --> C3
  INGEST --> C4
  C4 --> C5
  QG --> C7
  GG --> C6

  DOCS --> C2
  DOCS --> C3
  DOCS --> C4
  GRAPH --> C2
  GRAPH --> C5
  GRAPH --> C6
  GRAPH --> C7
  GRAPH --> C9
  GRAPH --> C10
  GRAPH --> C11
  QUIZZES --> C2
  QUIZZES --> C8
  MASTERY --> C2
  FLASH --> C2
  FLASH --> C11

  C1 --> CLIENT
  C2 --> CLIENT
  C3 --> CLIENT
  C4 --> CLIENT
  C5 --> CLIENT
  C6 --> CLIENT
  C7 --> CLIENT
  C8 --> CLIENT
  C9 --> CLIENT
  C10 --> CLIENT
  C11 --> CLIENT

  CLIENT --> OBS
  OBS --> SDK
  SDK --> OPENAI
  SDK --> LITELLM

  C3 --> DOCS
  C5 --> GRAPH
  C6 --> GRAPH
  C7 --> QUIZZES
  C8 --> QUIZZES
  C8 --> MASTERY
  C11 --> FLASH
```

## Cross-Agent Connections Worth Calling Out

1. Chat is downstream of both quiz and practice systems.
   `C2` injects quiz summaries and flashcard progress into the tutor prompt, so practice and assessment outputs directly shape the next tutor response.

2. Practice quiz submit is not its own grading agent.
   `submit_practice_quiz` delegates into `submit_level_up_quiz`, so practice and level-up share the same short-answer LLM grading path.

3. Practice quiz create is not its own persistence agent.
   `create_practice_quiz` generates its own items, then delegates persistence to `create_level_up_quiz`.

4. Quiz gardener is a background caller of the same level-up generation path.
   It does not define a separate model prompt family; it reuses `C7`.

5. Post-ingest graph work feeds almost everything else.
   `C4` and `C5` build the canonical graph, which then powers retrieval, quiz context, and practice context.

6. Document summary is upstream of tutor prompts.
   `C3` stores document summaries, and `C2` later pulls them into the chat prompt.
