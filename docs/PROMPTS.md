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
| `model_hint` | no | Preferred model class (`gpt-4o`, `gpt-4o-mini`, etc.). LiteLLM routing may override. |
| `temperature` | no | Default temperature. Services may override per call. |

## Directory Layout

```text
backend/app/agents/prompts/
  trail_generation.v1.md
  tutor_socratic.v1.md
  tutor_direct.v1.md
  tutor_repair.v1.md
  tutor_explore.v1.md
  tutor_mode_classifier.v1.md
  quiz_generation.v1.md
  quiz_grader.v1.md
  research_query.v1.md
  research_select.v1.md
```

## Task Registry

| Task | File | Description |
|---|---|---|
| `trail_generation` | `trail_generation.v1.md` | Generate a 10–30 node concept graph from a topic/goal/depth |
| `tutor_socratic` | `tutor_socratic.v1.md` | Socratic mode: ask one focused guiding question |
| `tutor_direct` | `tutor_direct.v1.md` | Direct mode: explain clearly, then check understanding |
| `tutor_repair` | `tutor_repair.v1.md` | Repair mode: address misconception, give hint, invite retry |
| `tutor_explore` | `tutor_explore.v1.md` | Explore mode: discuss adjacent topics and applications |
| `tutor_mode_classifier` | `tutor_mode_classifier.v1.md` | Classify which tutor mode to use for a learner message |
| `quiz_generation` | `quiz_generation.v1.md` | Generate a level-up or practice quiz from mastery_check_labels |
| `quiz_grader` | `quiz_grader.v1.md` | Grade a short-answer quiz response; return score and feedback |
| `research_query` | `research_query.v1.md` | Generate search queries for a topic/concept |
| `research_select` | `research_select.v1.md` | Evaluate and rank candidate sources for inclusion in research trace |

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

### `tutor_mode_classifier.v1.md`

**Template variables:**
- `learner_message` — the raw learner input
- `concept_title` — current concept
- `mastery_status` — current mastery status
- `conversation_summary` — brief summary of recent turns

**Expected output:**

```json
{
  "mode": "socratic | direct | repair | quiz_prompt | explore",
  "reason": "one sentence explanation"
}
```

**Mode selection logic (guide for the LLM):**
- `socratic` — default; learner is engaging normally
- `direct` — learner explicitly asks "explain", "just tell me", "what is", "give me the answer"
- `repair` — learner answer contains a clear misconception or is incorrect
- `quiz_prompt` — learner says they feel ready or asks to be tested
- `explore` — learner asks about applications, real-world use, why it matters, or adjacent topics

---

### `tutor_socratic.v1.md`

**Template variables:**
- `concept` — ConceptNode JSON
- `concept_level` — umbrella/topic/subtopic/granular
- `prerequisites` — list of prerequisite concept titles
- `children` — list of contained concept titles
- `mastery_status` — current status
- `bloom_target` — target Bloom level for this concept
- `learning_goal` — Trail goal statement
- `sources` — list of available source titles (no content, just titles and URLs)
- `conversation_summary` — summary of recent turns (see context management)
- `recent_turns` — last N conversation messages
- `learner_message` — current message

**Output:** Plain text Socratic question or response (streamed). One focused question.

---

### `tutor_direct.v1.md`

Same variables as `tutor_socratic`. Output is a direct explanation followed by a short check-in question.

---

### `tutor_repair.v1.md`

Same variables as `tutor_socratic`. Output names the likely misconception, gives a hint, and invites the learner to try again.

---

### `tutor_explore.v1.md`

**Additional variable:** `application_nodes` — list of application-edge concepts.

Output explores adjacent topics and applications, anchored to the current Trail. Stays bounded unless the learner explicitly asks to go broader.

---

### `quiz_generation.v1.md`

**Template variables:**
- `concept` — ConceptNode JSON
- `mastery_check_labels` — list of abstract check labels from the concept
- `bloom_target` — target Bloom level
- `quiz_type` — `level_up` or `practice`

**Expected output:**

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "explain | apply | compare",
      "prompt": "string",
      "mastery_label": "explain_in_own_words"
    }
  ]
}
```

A standard level-up card has 2–4 questions covering explain, apply, and compare types. Questions are generated from abstract labels only — never from private source-derived content.

---

### `quiz_grader.v1.md`

**Template variables:**
- `concept_title` — concept being checked
- `bloom_target` — target Bloom level
- `questions` — list of QuizQuestion objects
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
