# Prompt Registry

## Purpose

All LLM prompts in CoLearni are stored as versioned Markdown files in `backend/app/agents/prompts/`. Prompts are never inlined as Python strings. This keeps them reviewable, diffable, and testable independently of code.

## File Format

Each prompt file is a Markdown file with a YAML front-matter block:

```markdown
---
task: trail_generation
version: 1
model_hint: gpt-4o
temperature: 0.4
---

You are a curriculum designer...
```

Front-matter fields:

| Field | Required | Description |
|---|---|---|
| `task` | yes | Machine-readable task identifier (see Task Registry below) |
| `version` | yes | Integer, incremented on breaking changes |
| `model_hint` | no | Preferred model class (`gpt-4o`, `gpt-4o-mini`, etc.). Must be compatible with the configured `LLM_API_BASE` (see LLM client pattern in `docs/ARCHITECTURE.md`). |
| `temperature` | no | Default temperature. Services may override per call. |

## Directory Layout

```text
backend/app/agents/prompts/
  trail_generation.v1.md
  tutor_base.v1.md                      # classifier-style base (mode selection)
  tutor_turn_classifier.v1.md           # unified enforced-JSON turn classifier
  tutor_socratic.v2.md
  tutor_repair.v2.md
  tutor_explore.v2.md
  tutor_direct.v2.md
  tutor_direct_instructions.v1.md
  tutor_direct_locked.v1.md             # gated direct -> guided teaching
  tutor_free_explore_instructions.v1.md
  tutor_locked_mode.v1.md
  tutor_opening.v1.md                   # worked-example-first opening guidance
  quiz_answer_guard.v1.md
  quiz_generation.v1.md                 # retained for a registry regression test
  quiz_generation.v2.md                 # active quiz generation
  quiz_grader.v1.md
  concept_primer.v2.md                  # PRIMER_VERSION = 2
  conversation_summary.v1.md
  learner_state_update.v1.md
  flashcard_generation.v1.md
  artifact_builder.v1.md
  registry.py
  archive/                              # superseded versions, invisible to the registry glob
```

Superseded prompt versions (e.g. `tutor_socratic.v1`, `tutor_mode_classifier.v1`/`.v2`, `concept_primer.v1`) live under `archive/`. The registry globs the prompt directory non-recursively, so archived files are never loaded. Research-agent prompts (`research_query`, `research_select`) are planned but not yet added — research automation is deferred.

## Task Registry

| Task | File | Description |
|---|---|---|
| `trail_generation` | `trail_generation.v1.md` | Generate a 10–30 node concept graph from a topic/goal/depth |
| `tutor_base` | `tutor_base.v1.md` | Base tutor prompt used for first-pass mode selection |
| `tutor_turn_classifier` | `tutor_turn_classifier.v1.md` | Unified enforced-JSON turn classifier: returns `{mode, blocks_active_quiz_answer}` in one call (replaces the archived tagged `tutor_mode_classifier` + the standalone guard for production turns) |
| `tutor_socratic` | `tutor_socratic.v2.md` | Final-response Socratic teaching prompt |
| `tutor_repair` | `tutor_repair.v2.md` | Final-response repair/misconception prompt |
| `tutor_explore` | `tutor_explore.v2.md` | Final-response bounded-explore prompt |
| `tutor_direct` | `tutor_direct.v2.md` | Final-response direct explanation (mastered) prompt |
| `tutor_direct_instructions` | `tutor_direct_instructions.v1.md` | Internal-tool direct-mode instructions |
| `tutor_direct_locked` | `tutor_direct_locked.v1.md` | Guided-teaching prompt for gated `direct` before mastery |
| `tutor_free_explore_instructions` | `tutor_free_explore_instructions.v1.md` | Internal-tool broader-exploration instructions |
| `tutor_locked_mode` | `tutor_locked_mode.v1.md` | Fallback instructions when a gated tutor mode is still locked |
| `tutor_opening` | `tutor_opening.v1.md` | Worked-example-first opening-turn guidance (folds in a cached primer when present) |
| `quiz_answer_guard` | `quiz_answer_guard.v1.md` | Paraphrase guard used by the production tutor to block disguised active-quiz-answer extraction (fails open) |
| `quiz_generation` | `quiz_generation.v2.md` | Generate a level-up or practice quiz from mastery_check_labels plus bounded prior quiz context |
| `quiz_grader` | `quiz_grader.v1.md` | Grade a mixed-format quiz response and return score plus feedback |
| `concept_primer` | `concept_primer.v2.md` | Generate a concept primer (overview + key terms + sample questions); `PRIMER_VERSION = 2` |
| `conversation_summary` | `conversation_summary.v1.md` | Summarize older visible tutor turns for bounded tutor context (now run automatically post-`done`) |
| `learner_state_update` | `learner_state_update.v1.md` | Tutor-driven learner-state observer; enforced-JSON `{should_update, summary, strengths, misconceptions, resolved}` |
| `flashcard_generation` | `flashcard_generation.v1.md` | Source-grounded, dedup-aware flashcard generation returning `{cards, exhausted, reason}` (Phase 15c) |
| `artifact_builder` | `artifact_builder.v1.md` | Artifact-builder sub-agent: validated per-kind envelope payload from a bounded retrieval loop (Phase 15a) |
| `research_query` *(planned)* | — | Generate search queries for a topic/concept (research automation deferred; prompt not yet added) |
| `research_select` *(planned)* | — | Evaluate and rank candidate sources for the research trace (research automation deferred; prompt not yet added) |

## PromptRegistry (Python Interface)

```python
class PromptRegistry:
    def load(self, task: str, version: int | None = None) -> PromptTemplate:
        """Load a prompt by task name. If version is None, loads the latest."""

    def render(self, task: str, variables: dict, version: int | None = None) -> str:
        """Load and render a prompt with Jinja2 template variables."""
```

Variables in prompt files use Jinja2 syntax: `{{ variable_name }}`.

## Versioning Policy

- Increment `version` when the prompt changes in a way that could alter model behavior.
- Keep old versions until all dependents migrate.
- Tests should pin to specific versions to avoid regression from prompt changes.

---

## Prompt Skeletons

The following skeletons define the expected inputs (template variables) and outputs for each prompt. These are starting points — the actual prompt text will be refined during implementation and tuning.

---

### `trail_generation.v1.md`

**Template variables:**
- `topic` — the subject area
- `goal` — what the learner wants to achieve
- `target_depth` — Bloom taxonomy level (remember/understand/apply/analyze/evaluate/create)
- `max_nodes` — max graph size (default: 30)
- `min_nodes` — min graph size (default: 10)

**Expected output:** JSON matching the graph schema.

```json
{
  "nodes": [
    {
      "slug": "vectors",
      "title": "Vectors",
      "node_type": "concept",
      "concept_level": "topic",
      "difficulty": "beginner",
      "bloom_level": "understand",
      "mastery_check_labels": [
        "explain_vector_in_own_words",
        "compute_dot_product",
        "distinguish_vector_scalar"
      ]
    }
  ],
  "edges": [
    {
      "source": "vectors",
      "target": "matrices",
      "relation_type": "prerequisite"
    }
  ]
}
```

**Validation after generation:**
1. Every node has all required fields.
2. `concept_level` is one of umbrella/topic/subtopic/granular.
3. Slugs are unique.
4. All edge endpoints exist.
5. No prerequisite cycles.
6. Graph has at least one umbrella or topic entry node.
7. Node count is within `[min_nodes, max_nodes]`.

If validation fails, attempt one repair call with the validation errors appended. If the repaired output still fails, fall back to a smaller graph (5 nodes) or return an error.

---

### `tutor_base.v1.md`

**Template variables:**
- `learner_message` — the raw learner input
- `concept` — current concept plus level
- `concept_level` — umbrella/topic/subtopic/granular
- `prerequisites` — prerequisite titles
- `contained_nodes` — contained concept titles
- `containing_nodes` — broader containing concept titles
- `application_nodes` — application-node titles
- `related_nodes` — related concept titles
- `mastery_status` — current mastery status
- `bloom_target` — current concept Bloom target
- `learning_goal` — Trail goal
- `sources` — safe source titles/URLs/licenses
- `conversation_summary` — brief summary of recent turns
- `recent_turns` — last N conversation messages

**Expected output:** first line is a control tag, followed by visible text when applicable.

Current implementation note: these control tags remain the public/replay compatibility path for tutor mode/tool selection. `get_tutor_instructions` is now wrapped by CoLearni's normalized internal tool schema, but the tutor still emits and persists the tagged representation to preserve SSE ordering, sanitized public tool previews, hidden tool-turn replay, and conversation rehydration behavior. A full provider-native prompt migration is deferred until it can be done without changing the tutor contract.

```text
<mode name="socratic" />
<mode name="repair" />
<mode name="quiz_prompt" />
<mode name="explore" />
<tool name="get_tutor_instructions" mode="direct" />
<tool name="get_tutor_instructions" mode="free_explore" />
```

**Mode selection logic:**
- `socratic` — default; learner is engaging normally
- `direct` — learner explicitly asks "explain", "just tell me", "give me the answer", "summarize", "summarise", or to be shown an example directly; requested through the internal tool when mastery allows it
- `repair` — learner answer contains a clear misconception or is incorrect
- `quiz_prompt` — learner says they feel ready or asks to be tested
- `explore` — learner asks about applications, real-world use, why it matters, or adjacent topics while staying bounded to the current Trail
- `free_explore` — learner explicitly wants to go broader than the normal bounded explore response; requested through the internal tool when mastery allows it

---

### `tutor_direct_instructions.v1.md`

Uses the same concept/context variables as `tutor_base`. Output is instruction text returned by the internal `get_tutor_instructions(mode)` tool, telling the continuation call how to answer in direct mode.

---

### `tutor_free_explore_instructions.v1.md`

Uses the same concept/context variables as `tutor_base`. Output is instruction text returned by the internal tool for broader, mastery-gated exploration.

### `tutor_locked_mode.v1.md`

Uses the same concept/context variables plus `requested_mode` and `fallback_mode`. Output is instruction text for the continuation call when the learner requests a gated mode that is still locked.

---

---

### `conversation_summary.v1.md`

**Template variables:**
- `previous_summary` — latest stored summary text, or an explicit no-summary placeholder
- `new_turns` — formatted visible user/assistant turns newly covered by this summary batch

**Expected output:** Plain-text summary for future tutor context. The summary should capture durable learner understanding, misconceptions, prior tutor explanations, preferences/goals, and next repair targets. Hidden tool turns/provider reasoning are never provided to the prompt.

---

### `quiz_generation.v2.md`

**Template variables:**
- `concept` — ConceptNode JSON
- `mastery_check_labels` — list of abstract check labels from the concept
- `bloom_target` — target Bloom level
- `quiz_type` — `level_up` or `practice`
- `prior_quiz_context` — bounded prior attempt summaries/fingerprints used to avoid repeated prompts without exposing answers

**Expected output:**

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple_choice | short_answer | long_answer",
      "prompt": "string",
      "mastery_label": "explain_in_own_words",
      "difficulty": "light | standard | challenge",
      "options": ["string", "string", "string"]
    }
  ]
}
```

Practice cards should have 2-3 questions. Level-up cards should have 2-4 questions.

Questions are generated from abstract labels only — never from private source-derived content. The generator should choose the lowest-friction question type that still checks the required mastery label, and only include `options` for `multiple_choice` questions.

---

### `quiz_grader.v1.md`

**Template variables:**
- `concept_title` — concept being checked
- `bloom_target` — target Bloom level
- `questions` — list of mixed-format QuizQuestion objects
- `answers` — list of `{question_id, answer}` objects

**Expected output:**

```json
{
  "score": 0.85,
  "passed": true,
  "per_question": [
    {
      "question_id": "q1",
      "score": 0.9,
      "feedback": "Strong. You correctly identified..."
    }
  ],
  "overall_feedback": "You demonstrated solid understanding of X. For Y, revisit..."
}
```

**Pass threshold:** `score >= 0.7`. Enforced in service code, not in the prompt.

Score meanings:
- `0.0–0.4` — incorrect or missing
- `0.5–0.69` — partial, needs improvement
- `0.7–0.89` — passing with room to grow
- `0.9–1.0` — strong mastery

---

### `research_query.v1.md`

**Template variables:**
- `topic` — Trail topic
- `concept_title` — optional, scoped concept
- `goal` — Trail goal
- `max_queries` — max number of queries to generate (default: 5)

**Expected output:**

```json
{
  "queries": [
    "eigenvectors geometric intuition beginner",
    "eigenvectors applications PCA explained"
  ]
}
```

---

### `research_select.v1.md`

**Template variables:**
- `topic` — Trail topic
- `concept_title` — optional
- `candidates` — list of `{title, url, snippet}` from search results
- `max_select` — max sources to include (default: 5)

**Expected output:**

```json
{
  "selected": [
    {
      "url": "https://...",
      "reason": "introductory explanation with geometric intuition"
    }
  ],
  "excluded": [
    {
      "url": "https://...",
      "reason": "paywalled, access restricted"
    }
  ]
}
```
