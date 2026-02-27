# Prompt Inventory

This document tracks prompt-producing code paths by agent/domain.

## Tutor Agent Prompts

### 1) Full tutor system prompt (primary chat path)
- **Purpose**: Main grounded tutor response generation (Socratic/direct style).
- **Prompt builder**: Persona + style rules + document summaries + assessment context + history + evidence + user question.
- **Code path**:
  - `domain/chat/prompt_kit.py`
    - `build_system_prompt(...)`
    - `build_evidence_block(...)`
    - `build_full_tutor_prompt(...)`
  - `domain/chat/respond.py`
    - `_generate_tutor_text(...)` calls `build_full_tutor_prompt(...)`

### 2) Tutor fallback prompt (legacy/simple path)
- **Purpose**: Minimal style/evidence prompt for tutor text generation helper.
- **Code path**:
  - `domain/chat/tutor_agent.py`
    - `build_tutor_prompt(...)`
    - `build_tutor_response_text(...)`

### 3) Social/chitchat response templates
- **Purpose**: Non-grounded social turn replies (greeting/thanks/bye/etc.).
- **Code path**:
  - `domain/chat/prompt_kit.py`
    - `classify_social_intent(...)`
    - `build_social_response(...)`

### 4) Concept clarification prompt template
- **Purpose**: Ask user to resolve concept mismatch before switching context.
- **Code path**:
  - `domain/chat/concept_resolver.py`
    - `resolve_concept_for_turn(...)` (`clarification_prompt` text)

## Level-up Quiz Agent Prompts

### 5) Level-up quiz generation prompt
- **Purpose**: Generate mixed short-answer + MCQ level-up quiz JSON.
- **Prompt includes**: concept name, description, related concepts, strict JSON schema, quality rules, retry metadata.
- **Code path**:
  - `domain/learning/level_up.py`
    - `_generate_level_up_items_with_retries(...)`

### 6) Level-up grading prompt
- **Purpose**: Grade short-answer items against generation-time context.
- **Prompt includes**: item IDs + submission JSON + output schema requirements.
- **Code path**:
  - `domain/learning/level_up.py`
    - `_grading_prompt(...)`

## Practice Agent Prompts

### 7) Practice flashcard generation prompt
- **Purpose**: Generate JSON flashcards (`front`, `back`, `hint`).
- **Code path**:
  - `domain/learning/practice.py`
    - `generate_practice_flashcards(...)`

### 8) Practice quiz generation prompt
- **Purpose**: Generate practice quiz JSON with mixed item types and novelty signal.
- **Code path**:
  - `domain/learning/practice.py`
    - `create_practice_quiz(...)`
    - `_generate_practice_items_with_retries(...)`

## Ingestion/Graph Prompts

### 9) Document summary prompt
- **Purpose**: Generate 2–3 sentence summary from ingested chunk sample.
- **Code path**:
  - `core/ingestion.py`
    - `_generate_document_summary(...)`

### 10) Raw graph extraction prompt
- **Purpose**: Extract concept/edge JSON from chunk text under strict schema.
- **Code path**:
  - `adapters/llm/providers.py`
    - `_BaseGraphLLMClient.extract_raw_graph(...)`

### 11) Graph disambiguation prompt
- **Purpose**: Decide `MERGE_INTO` vs `CREATE_NEW` for canonical concept resolution.
- **Code path**:
  - `adapters/llm/providers.py`
    - `_BaseGraphLLMClient.disambiguate(...)`

### 12) Generic tutor system instruction
- **Purpose**: System instruction wrapper for all `generate_tutor_text(...)` calls.
- **Code path**:
  - `adapters/llm/providers.py`
    - `_BaseGraphLLMClient.generate_tutor_text(...)`
    - `_BaseGraphLLMClient._chat_text(...)`

## Maintenance Rules
- Update this file whenever a new prompt template/instruction is added, deleted, or materially changed.
- If prompt behavior changes API contracts or major tutor behavior, also update:
  - `docs/ARCHITECTURE.md`
  - `docs/PRODUCT_SPEC.md`
  - `docs/PROGRESS.md`
