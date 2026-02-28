# CoLearni Prompt Refactor Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Template source:
- `docs/prompt_templates/refactor_plan.md`

Related design docs:
- `docs/prompt_templates/README.md`
- `docs/PROMPTS.md`
- `docs/REFERENCE_PROMPTS.md`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 slices
   - after any context compaction / summarization event
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - target `<= 400 LOC net` per PR where practical
4. For each slice, produce a `Verification Block` with:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps
   - Observed outcome
5. Do not mix prompt refactor work with unrelated product changes.
6. If a slice changes user-visible output contracts, update docs and tests in the same slice.
7. If implementation reveals a better prompt boundary or file layout, update this plan before widening scope.

## Purpose

This document is the implementation plan for moving Colearni from prompt strings embedded directly in Python into a file-based, versioned prompt system that fits the product and architecture.

The target design combines two useful reference patterns:

1. LightRAG-style prompt discipline:
   - clear system and task roles
   - explicit context wrappers
   - strict JSON output for machine-consumed tasks
   - repair / continuation prompts for malformed outputs

2. Nanobot-style prompt organization:
   - prompts as Markdown files on disk
   - discoverable and editable without changing core logic
   - small reusable prompt assets rather than one giant instruction blob

The result should fit Colearni's actual agent boundaries:
- Tutor
- Query analysis / routing
- Graph extraction and resolution
- Level-up generation and grading
- Practice generation
- Suggestion copy
- Document summarization

## Inputs Used

This plan is based on:

- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/PROMPTS.md`
- `docs/REFERENCE_PROMPTS.md`
- `docs/prompt_templates/README.md`
- `docs/prompt_templates/tutor.md`
- `docs/prompt_templates/routing.md`
- `docs/prompt_templates/graph.md`
- `docs/prompt_templates/assessment.md`
- `docs/prompt_templates/practice.md`
- `docs/prompt_templates/suggestion.md`
- `docs/prompt_templates/document_processing.md`
- current runtime prompt code in:
  - `domain/chat/prompt_kit.py`
  - `domain/chat/tutor_agent.py`
  - `domain/learning/level_up.py`
  - `domain/learning/practice.py`
  - `adapters/llm/providers.py`

## Executive Summary

The current prompt system works, but the boundaries are wrong for long-term maintainability.

Current issues:

1. Prompt logic is spread across Python modules instead of versioned prompt assets.
2. Non-tutor tasks still use the tutor text generation path and tutor-flavored system instructions.
3. Structured tasks already want LightRAG-style schema discipline, but the retry and repair patterns are inconsistent.
4. The repo now has a prompt template design set in `docs/prompt_templates/`, but runtime code does not consume those templates.
5. There is no shared prompt loader, prompt registry, or task-specific prompt execution seam.

The right move is a phased refactor:

1. Add a file-based prompt asset layer.
2. Add a small typed prompt registry and renderer.
3. Split LLM task entrypoints by job instead of routing everything through `generate_tutor_text()`.
4. Migrate each task family one at a time.
5. Add repair prompts, prompt observability, and regression tests.

## Non-Negotiable Constraints

These constraints apply to every slice:

1. Preserve thin route boundaries.
2. Preserve evidence-first behavior and strict grounded refusal behavior.
3. Do not loosen graph budgets or grading safety rules.
4. Do not merge prompt families into one generic super-prompt.
5. Prefer strict JSON outputs for machine-consumed tasks.
6. Keep prompt rendering deterministic and explicit.
7. Do not introduce a heavy prompt framework unless the slice explicitly justifies it.

## Current Hotspots

These are the main files that should be gradually reduced as prompt-definition hotspots:

| File | Why it matters |
|---|---|
| `domain/chat/prompt_kit.py` | Contains tutor prompt assembly inline in Python. |
| `domain/chat/tutor_agent.py` | Holds fallback prompt text and style-specific prompt logic. |
| `domain/learning/level_up.py` | Contains level-up generation and grading prompts inline. |
| `domain/learning/practice.py` | Contains practice quiz and flashcard prompts inline. |
| `adapters/llm/providers.py` | Uses a tutor-oriented text generation method for multiple unrelated tasks. |
| `docs/PROMPTS.md` | Catalogs current prompts, but not the target file-based runtime design. |

## Target Architecture

### Prompt asset layout

Implement a runtime prompt asset folder under code, not under `docs/`.

Recommended shape:

```text
core/
  prompting/
    registry.py
    renderer.py
    loader.py
    models.py
    assets/
      tutor/
        socratic_v1.md
        direct_v1.md
      routing/
        query_analyzer_v1.md
      graph/
        extract_chunk_v1.md
        disambiguate_v1.md
        merge_summary_v1.md
        repair_json_v1.md
      assessment/
        levelup_generate_v1.md
        levelup_grade_v1.md
        repair_json_v1.md
      practice/
        quiz_generate_v1.md
        flashcards_generate_v1.md
        repair_json_v1.md
      suggestion/
        hook_v1.md
      document/
        summary_v1.md
```

Why this layout:

- `core/prompting/` is shared infrastructure and does not violate layer boundaries.
- Markdown assets keep the Nanobot-style file-based editing model.
- Task folders keep prompt ownership clear.
- Version suffixes support prompt iteration without breaking runtime call sites.

### Prompt execution model

Use typed task entrypoints instead of one generic text method:

- `generate_tutor_reply(...)`
- `analyze_query(...)`
- `extract_graph_chunk(...)`
- `disambiguate_concept(...)`
- `merge_graph_cluster(...)`
- `generate_levelup_quiz(...)`
- `grade_short_answers(...)`
- `generate_practice_quiz(...)`
- `generate_flashcards(...)`
- `generate_suggestion_hook(...)`
- `summarize_document(...)`

Each entrypoint should:

1. Load the prompt asset by stable ID.
2. Render placeholders from typed inputs.
3. Use the correct system/task contract.
4. Enforce JSON schema where applicable.
5. Run task-specific repair prompts when allowed.
6. Emit prompt ID/version in observability.

### LightRAG patterns to preserve

Implement these patterns explicitly:

1. `Role`, `Goal`, `Instructions`, `Context`, `Output contract`, `Failure behavior` prompt structure.
2. JSON-schema enforcement for graph, grading, quiz, flashcard, and routing tasks.
3. Dedicated context wrappers instead of ad hoc string concatenation.
4. Repair prompts for malformed or incomplete JSON.
5. Failure templates for strict grounded refusal and no-context outcomes.

### Nanobot patterns to preserve

Implement these patterns explicitly:

1. Prompts live as Markdown files on disk.
2. Runtime reads prompt files by ID rather than hardcoded inline strings.
3. Small prompt assets compose into larger behaviors through code.
4. Prompt edits should not require changing application logic unless the contract changes.

Do NOT implement full Nanobot `MEMORY.md` behavior as part of this plan.

Instead:

- keep memory as explicit structured inputs from existing DB/session state
- express memory in prompt sections such as `ASSESSMENT_CONTEXT`, `HISTORY`, and `FLASHCARD_PROGRESS`

## Stable Slice IDs

Use these IDs in commits, reports, and verification blocks:

- `P1` Prompt Asset Infrastructure
- `P2` Tutor Prompt Migration
- `P3` Query Analysis Prompt
- `P4` Graph Prompt Migration
- `P5` Assessment Prompt Migration
- `P6` Practice Prompt Migration
- `P7` Suggestion and Document Prompt Migration
- `P8` Repair, Observability, and Prompt Regression Hardening
- `P9` Docs and Closeout

## Implementation Sequencing

Execute slices in order. Each slice must finish with green verification before the next begins.

### P1. Prompt Asset Infrastructure

Goal:
- Create the file-based prompt runtime layer.

Requirements:
- Add `core/prompting/` module with loader, renderer, registry, and typed metadata.
- Load prompt assets from `core/prompting/assets/`.
- Support stable prompt IDs and versions.
- Support placeholder rendering with explicit missing-key failures.
- Make it easy to request either plain text or JSON-schema-backed tasks.
- Add tests for asset loading, missing asset failures, and placeholder validation.

Acceptance criteria:
- Runtime can load a prompt asset by stable ID.
- Missing placeholders fail fast with a clear error.
- Prompt registry is test-covered.

Verification gates:
- `pytest -q tests/core/test_prompt_loader.py`
- `pytest -q tests/core/test_prompt_registry.py`

### P2. Tutor Prompt Migration

Goal:
- Move tutor prompts out of `domain/chat/prompt_kit.py` into prompt assets without changing mastery-gating behavior.

Requirements:
- Implement `tutor_socratic_v1` and `tutor_direct_v1` as runtime assets.
- Preserve current mastery gating rules.
- Preserve strict grounded refusal behavior.
- Preserve evidence section formatting and inline evidence markers.
- Keep fallback behavior deterministic if prompt rendering or LLM calls fail.
- Update prompt-related unit tests.

Acceptance criteria:
- Tutor path uses file-based prompt assets.
- Socratic vs direct behavior remains consistent with current product rules.
- Existing evidence/citation policy remains intact.

Verification gates:
- `pytest -q tests/domain/test_prompt_kit.py`
- `pytest -q tests/domain/test_tutor_agent.py`
- targeted chat integration tests if they already exist

### P3. Query Analysis Prompt

Goal:
- Add a small structured query-analysis prompt for routing and retrieval planning.

Requirements:
- Add `query_analyzer_v1` runtime asset.
- Return structured JSON for intent, requested mode, keyword hints, and level-up readiness hints.
- Keep the conductor deterministic about final routing policy.
- Do not let this component answer the user question.
- Add tests for vague, social, learning, practice, and level-up requests.

Acceptance criteria:
- Query analysis returns valid JSON with a stable schema.
- Social and vague cases are handled conservatively.

Verification gates:
- `pytest -q tests/domain/test_query_analyzer.py`

### P4. Graph Prompt Migration

Goal:
- Move graph extraction and disambiguation onto dedicated prompt assets that preserve LightRAG-style schema discipline.

Requirements:
- Add runtime assets for:
  - `graph_extract_chunk_v1`
  - `graph_disambiguate_v1`
  - `graph_merge_summary_v1`
- Add task-specific LLM client methods for graph tasks if missing.
- Keep JSON schema enforcement in the provider layer.
- Bias disambiguation toward `CREATE_NEW` when confidence is low.
- Add tests for extraction shape, empty extraction handling, disambiguation decisions, and merge-summary behavior.

Acceptance criteria:
- Graph tasks no longer depend on inline prompt strings.
- Output contracts stay strict and bounded.
- Existing graph budget rules remain unchanged.

Verification gates:
- `pytest -q tests/domain/graph`
- `pytest -q tests/adapters/test_graph_llm_provider.py`

### P5. Assessment Prompt Migration

Goal:
- Move level-up generation and short-answer grading prompts onto task-specific runtime assets.

Requirements:
- Add runtime assets for:
  - `levelup_generate_v1`
  - `levelup_grade_v1`
- Replace generic tutor text generation calls with assessment-specific client methods.
- Preserve generation-time context use during grading.
- Preserve pass criteria and critical misconception handling.
- Add tests for prompt rendering, grading schema validation, and fallback paths.

Acceptance criteria:
- Level-up generation and grading use task-specific prompt assets.
- Grading remains bound to `_generation_context`.
- No mastery-state regression.

Verification gates:
- `pytest -q tests/domain/test_level_up.py`
- relevant grading integration tests

### P6. Practice Prompt Migration

Goal:
- Move practice quiz and flashcard generation to task-specific prompt assets.

Requirements:
- Add runtime assets for:
  - `practice_quiz_generate_v1`
  - `practice_flashcards_generate_v1`
- Preserve non-leveling behavior.
- Preserve novelty and dedup behavior.
- Add practice-specific repair prompt if JSON output is malformed.
- Add tests for practice quiz structure, flashcard structure, and fallback behavior.

Acceptance criteria:
- Practice generation no longer uses tutor-oriented prompt methods.
- Practice output shape is stable and validated.
- Mastery state remains unchanged.

Verification gates:
- `pytest -q tests/domain/test_practice.py`

### P7. Suggestion and Document Prompt Migration

Goal:
- Move suggestion hook and document summary prompting onto runtime assets.

Requirements:
- Add runtime assets for:
  - `suggestion_hook_v1`
  - `document_summary_v1`
- Keep concept selection deterministic in graph logic; the prompt only writes learner-facing copy.
- Keep document summaries short and source-bound.
- Add tests for prompt rendering and output bounds.

Acceptance criteria:
- Suggestion prompt does not choose concepts.
- Document summary prompt stays within the intended size and grounding limits.

Verification gates:
- `pytest -q tests/domain/test_suggestion_prompt.py`
- `pytest -q tests/core/test_document_summary.py`

### P8. Repair, Observability, and Prompt Regression Hardening

Goal:
- Add the missing operational safety layer around prompt execution.

Requirements:
- Add repair prompts for malformed JSON outputs where regeneration is allowed.
- Emit prompt ID, version, task type, and rendered prompt length in spans/logs.
- Add regression tests for prompt IDs and rendered required sections.
- Add a small snapshot-style prompt regression harness for critical prompts.
- Ensure repair loops are bounded and explicit.

Acceptance criteria:
- Structured tasks can retry via dedicated repair prompts.
- Observability shows which prompt version ran.
- Regression tests fail when required prompt sections disappear.

Verification gates:
- `pytest -q tests/domain/test_prompt_regression.py`
- any existing observability tests impacted by the changes

### P9. Docs and Closeout

Goal:
- Make the docs reflect the new file-based prompt system and close out the plan cleanly.

Requirements:
- Update `docs/PROMPTS.md` from “current code prompt catalog only” to include the new runtime layout or clearly link to it.
- Update `docs/ARCHITECTURE.md` if prompt architecture surfaces are added.
- Update `docs/PROGRESS.md` when slices land.
- Mark old inline prompt locations as compatibility or migrated where relevant.

Acceptance criteria:
- Docs no longer imply that prompt definitions live only in Python strings.
- The plan accurately reflects what landed.

Verification gates:
- manual docs review
- targeted test/doc checks if added

## Implementation Notes By Pattern

### System and user prompt separation

Follow the LightRAG pattern where useful:

1. Keep stable system instructions in the prompt asset.
2. Feed dynamic context through explicit input blocks.
3. Avoid hidden string concatenation of unlabeled context.

### Context wrappers

Move reusable context shaping into code helpers:

- evidence block builder
- assessment history formatter
- chat history formatter
- graph candidate wrapper
- quiz submission wrapper

Keep these wrappers deterministic and test them separately from prompt assets.

### JSON schema discipline

For all machine-consumed tasks:

1. Define one schema in code.
2. Pair it with one prompt asset.
3. Validate response shape after parsing.
4. If repair is allowed, use one bounded repair prompt.

### Prompt versioning

Use stable IDs plus explicit versions:

- `tutor_socratic_v1`
- `graph_extract_chunk_v1`
- `levelup_grade_v1`

Do not silently mutate prompt meaning without bumping the version if:

- required sections change
- output schema changes
- behavioral guarantees change materially

## Removal Safety Rules

These rules apply when removing inline prompt strings or old prompt helpers:

1. Do not delete a prompt builder until the replacement asset path is wired and tested.
2. Prefer staged migration:
   - add asset-backed path
   - dual-run or swap call sites
   - remove obsolete inline prompt string
3. For each meaningful removal, record:
   - old location
   - new prompt ID / asset path
   - tests proving parity or intentional change

## Verification Block Template

Use this exact structure at the end of each slice:

```text
Verification Block - <slice-id>

Root cause
- <why the current prompt setup was insufficient>

Files changed
- <path>

What changed
- <summary>

Commands run
- <command>

Manual verification steps
- <step>

Observed outcome
- <what happened>
```

## Unified Prompt Refactor Prompt

Use this single kickoff prompt for the implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/PROMPT_REFACTOR_PLAN.md now. This file is the source of truth.
You MUST implement prompt refactor slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

You MUST preserve Colearni's product constraints while doing this work:
- evidence-first tutor behavior
- strict grounded refusal behavior
- mastery-gated tutor behavior
- bounded graph and repair budgets
- thin API routes

You MUST preserve the intended adaptation patterns:
- Nanobot-style prompt assets stored as Markdown files on disk
- LightRAG-style explicit prompt sections, context wrappers, and strict JSON output contracts for machine-consumed tasks

Before removing or replacing any inline prompt string, prompt helper, prompt path, or task-specific LLM call site, you MUST document:
- old location
- replacement prompt ID or asset path
- why the replacement is safe
- how the old behavior can be restored

Removal policy:
- Prefer staged migration over hard deletion.
- Do not delete a prompt builder until the asset-backed path is wired and tested.
- Do not silently change a prompt contract without bumping the prompt version when required.

After every 2 slices OR if your context is compacted/summarized, re-open docs/PROMPT_REFACTOR_PLAN.md and restate which slices remain.
Work in small commits: chore(prompting): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/PROMPT_REFACTOR_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include:
1. The Verification Block for the slice
2. A short note listing any prompt assets added or migrated in that slice

START:

Read docs/PROMPT_REFACTOR_PLAN.md.
Begin with the current slice in execution order. If starting fresh, begin with slice P1 (Prompt Asset Infrastructure) exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/PROMPT_REFACTOR_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```

## Out of Scope

These are NOT part of this plan unless a later update explicitly adds them:

- replacing the DB/session memory model with file-based memory
- introducing autonomous multi-step tool-using agent loops for chat
- redesigning mastery policy
- redesigning graph budgets
- switching to a third-party orchestration framework

## Final Exit Criteria

This plan is complete only when:

1. Runtime prompt assets exist under a code-owned prompt asset directory.
2. Tutor, graph, assessment, practice, suggestion, and document tasks use file-based prompt assets.
3. Structured tasks use task-specific prompt entrypoints and JSON schema validation.
4. Repair prompts are bounded and test-covered.
5. Prompt IDs and versions are visible in observability.
6. Docs accurately describe both the current prompt inventory and the runtime prompt architecture.
