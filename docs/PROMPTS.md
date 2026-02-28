# Prompt Inventory — Colearni

> Source-of-truth catalog of all LLM prompts used across the codebase.
> Proposed versioned prompt templates for future file-based prompt management live in `docs/prompt_templates/`.
> Last updated: Session 11

## Overview

Colearni uses 14 distinct LLM prompt templates across 7 source files. Prompts fall into four categories:

| Category | Count | Output Format |
|----------|-------|---------------|
| Tutor / Chat | 5 | Free text |
| Knowledge Graph | 3 | Structured JSON |
| Quiz & Practice | 4 | Structured JSON |
| Document Processing | 2 | Mixed |

---

## Tutor Agent Prompts

### 1. Full Tutor System Prompt (Primary Chat Path)

| Field | Detail |
|-------|--------|
| **File** | `domain/chat/prompt_kit.py` |
| **Function** | `build_system_prompt()` |
| **Purpose** | Composes the system-level prompt for the tutor LLM, combining persona identity, teaching style rules, document summaries, assessment history, and conversation history. |
| **Key Inputs** | `persona` (dict with `system_prefix`), `style` (`"socratic"` / `"direct"`), `assessment_context`, `history_summary`, `document_summaries` |
| **Output** | Free text (multi-line system instruction) |
| **Code Path** | `prompt_kit.build_system_prompt()` → `build_evidence_block()` → `build_full_tutor_prompt()` |

Prompt skeleton:
```
You are OpenClaw, an encouraging and curious AI tutor. …
TEACHING STYLE: Socratic | Direct
DOCUMENT SUMMARIES: …
RECENT ASSESSMENT CONTEXT: …
CONVERSATION HISTORY: …
```

### 2. Evidence Block Builder

| Field | Detail |
|-------|--------|
| **File** | `domain/chat/prompt_kit.py` |
| **Function** | `build_evidence_block()` |
| **Purpose** | Formats retrieved evidence chunks into a labeled block (`e1`, `e2`…) appended to the tutor prompt. |
| **Key Inputs** | `evidence` (list of `EvidenceItem`), `max_items` (default 5) |
| **Output** | Free text block (part of larger prompt) |

### 3. Full Tutor Prompt (Composite)

| Field | Detail |
|-------|--------|
| **File** | `domain/chat/prompt_kit.py` |
| **Function** | `build_full_tutor_prompt()` |
| **Purpose** | Assembles the complete user-facing prompt: `system_prompt` + `evidence_block` + `USER_QUESTION: {query}`. Passed to `generate_tutor_text()`. |
| **Key Inputs** | `query`, `evidence`, `persona`, `style`, `assessment_context`, `history_summary`, `document_summaries` |
| **Output** | Free text (complete prompt sent to LLM) |

### 4. Simple Tutor Prompt (Fallback)

| Field | Detail |
|-------|--------|
| **File** | `domain/chat/tutor_agent.py` |
| **Function** | `build_tutor_prompt()` |
| **Purpose** | Simpler standalone tutor prompt used as a fallback when the full `prompt_kit` pipeline can't run. Includes style rules + evidence + question. |
| **Key Inputs** | `query`, `evidence` (top 3 items), `style` |
| **Output** | Free text |

### 5. Tutor System Instruction (LLM Client Wrapper)

| Field | Detail |
|-------|--------|
| **File** | `adapters/llm/providers.py` |
| **Function** | `_BaseGraphLLMClient.generate_tutor_text()` |
| **Purpose** | Wraps every `generate_tutor_text` call with a fixed system instruction message. All tutor prompts flow through this method. |
| **Key Inputs** | `prompt` (user-content from caller) |
| **Output** | Free text |
| **System instruction** | `"You are a grounded tutor. Follow style instructions exactly and stay concise."` |

### Social/Chitchat Templates (Non-LLM)

- **Purpose**: Non-grounded social turn replies (greeting/thanks/bye/etc.) — deterministic, no LLM call.
- **Code path**: `domain/chat/prompt_kit.py` → `classify_social_intent()`, `build_social_response()`

### Concept Clarification Template (Non-LLM)

- **Purpose**: Ask user to resolve concept mismatch before switching context — deterministic template.
- **Code path**: `domain/chat/concept_resolver.py` → `resolve_concept_for_turn()`

---

## Knowledge Graph Prompts

### 6. Raw Graph Extraction

| Field | Detail |
|-------|--------|
| **File** | `adapters/llm/providers.py` |
| **Function** | `_BaseGraphLLMClient.extract_raw_graph()` |
| **Purpose** | Extracts concepts and edges from a document chunk for the knowledge graph. Uses structured JSON output with a strict OpenAI-compatible schema. |
| **Key Inputs** | `chunk_text` |
| **Output** | **Structured JSON** — `{concepts: [{name, context_snippet, description}], edges: [{src_name, tgt_name, relation_type, description, keywords, weight}]}` |
| **System message** | `"Return only JSON that satisfies the provided schema."` |
| **User prompt** | `"Extract concept+edge JSON from this chunk.\n\nCHUNK:\n{chunk_text}"` |

### 7. Concept Disambiguation

| Field | Detail |
|-------|--------|
| **File** | `adapters/llm/providers.py` |
| **Function** | `_BaseGraphLLMClient.disambiguate()` |
| **Purpose** | Resolves whether a newly extracted concept should merge into an existing canonical concept or create a new one. Used by both the online resolver and the offline gardener. |
| **Key Inputs** | `raw_name`, `context_snippet`, `candidates` (list of `{id, canonical_name, description, aliases}`) |
| **Output** | **Structured JSON** — `{decision, confidence, merge_into_id, alias_to_add, proposed_description}` |

### 8. Gardener Cluster Merge Decision

| Field | Detail |
|-------|--------|
| **File** | `domain/graph/gardener.py` |
| **Function** | `_cluster_llm_decision()` |
| **Purpose** | During offline graph consolidation, asks the LLM whether a cluster of similar concepts should be merged. Reuses the `disambiguate()` interface (Prompt #7) with cluster members as candidates. |
| **Key Inputs** | `reference.canonical_name`, `reference.description`, cluster members as `candidates` |
| **Output** | **Structured JSON** — subset of #7 schema |

---

## Quiz & Practice Prompts

### 9. Level-Up Quiz Generation

| Field | Detail |
|-------|--------|
| **File** | `domain/learning/level_up.py` |
| **Function** | `_generate_level_up_items_with_retries()` |
| **Purpose** | Generates a mixed quiz (short_answer + mcq) for concept mastery assessment. Includes source material excerpts and adjacent concepts for context. |
| **Key Inputs** | `concept_name`, `concept_description`, `adjacent_concepts`, `chunk_excerpts` (S34), `target_count` |
| **Output** | **Structured JSON** — `{items: [{item_type, prompt, payload}]}` |
| **Added in S34** | Now includes `SOURCE MATERIAL EXCERPTS` block from document chunks for richer generation context. |

### 10. Short-Answer Grading

| Field | Detail |
|-------|--------|
| **File** | `domain/learning/level_up.py` |
| **Function** | `_grading_prompt()` |
| **Purpose** | Sends quiz submissions (short-answer items + student answers) to the LLM for rubric-based grading. Used by both level-up and practice quiz grading. |
| **Key Inputs** | `items` (quiz items with payloads including `_generation_context`), `answer_map` (student answers keyed by `item_id`) |
| **Output** | **Structured JSON** — `{items: [{item_id, score(0..1), critical_misconception(bool), feedback}], overall_feedback}` |

### 11. Practice Quiz Generation

| Field | Detail |
|-------|--------|
| **File** | `domain/learning/practice.py` |
| **Function** | `create_practice_quiz()` |
| **Purpose** | Generates a lighter practice quiz (3–6 items) for spaced repetition. Includes a random UUID seed for novelty. |
| **Key Inputs** | `overfetch` (count), `context` JSON (`{concept_name, concept_description, adjacent_concepts}`) |
| **Output** | **Structured JSON** — `{items: [{item_type, prompt, payload}]}` |

### 12. Flashcard Generation

| Field | Detail |
|-------|--------|
| **File** | `domain/learning/practice.py` |
| **Function** | `generate_practice_flashcards()` / `generate_stateful_flashcards()` |
| **Purpose** | Generates study flashcards (front/back/hint) for a concept. Stateful variant adds dedup + persistence. |
| **Key Inputs** | `card_count`, `context` JSON (`{concept_name, concept_description, adjacent_concepts}`) |
| **Output** | **Structured JSON** — `{flashcards: [{front, back, hint}]}` |

---

## Document Processing Prompts

### 13. Document Summary Generation

| Field | Detail |
|-------|--------|
| **File** | `core/ingestion.py` |
| **Function** | `_generate_document_summary()` |
| **Purpose** | Generates a 2–3 sentence summary of a newly ingested document from its first few chunks. Stored for document-level context in the tutor prompt. |
| **Key Inputs** | `chunks` (first up to 5, capped at 3000 chars total) |
| **Output** | Free text (capped at 500 chars) |

---

## Orchestration Files (No Direct Prompts)

These files orchestrate LLM calls but delegate prompt construction to the modules above:

| File | Role |
|------|------|
| `domain/chat/respond.py` | Chat orchestrator — delegates to `prompt_kit` / `tutor_agent`. Builds quiz context (S34) via `_build_quiz_context()`. |
| `domain/graph/extraction.py` | Calls `extract_raw_graph` (prompt built in `providers.py`) |
| `domain/graph/resolver.py` | Calls `disambiguate` (prompt built in `providers.py`) |
| `apps/jobs/quiz_gardener.py` | Auto-generation orchestrator (S34) — delegates to `create_level_up_quiz` |
| `domain/readiness/analyzer.py` | Pure math (exponential decay) — no LLM calls |

---

## Prompt Flow Diagram

```
User message
  └─► respond.py (orchestrator)
        ├─► _build_quiz_context()  [fetches latest quiz status — S34]
        ├─► prompt_kit.build_full_tutor_prompt()     [#1 + #2 + #3]
        │     └─► providers.generate_tutor_text()    [#5]
        └─► tutor_agent.build_tutor_prompt()         [#4 — fallback]
              └─► providers.generate_tutor_text()    [#5]

Document upload
  └─► ingestion.py
        ├─► providers.extract_raw_graph()            [#6]
        ├─► providers.disambiguate()                 [#7]
        └─► _generate_document_summary()             [#13]

Quiz/Practice generation
  ├─► level_up.py → _generate_level_up_items_with_retries()  [#9]
  ├─► level_up.py → _grading_prompt()                        [#10]
  ├─► practice.py → create_practice_quiz()                   [#11]
  └─► practice.py → generate_*_flashcards()                  [#12]

Graph gardener (offline)
  └─► gardener.py → _cluster_llm_decision()          [#8 via #7]

Auto quiz generation (S34)
  └─► quiz_gardener.py → create_level_up_quiz()      [→ #9]
```

---

## Maintenance Rules

- Update this file whenever a new prompt template/instruction is added, deleted, or materially changed.
- If prompt behavior changes API contracts or major tutor behavior, also update:
  - `docs/ARCHITECTURE.md`
  - `docs/PRODUCT_SPEC.md`
  - `docs/PROGRESS.md`
