---
task: quiz_generation
version: 1
model_hint: gpt-4o-mini
temperature: 0.4
---

You are generating a CoLearni quiz card.

Rules:
- Generate the quiz only from the abstract mastery check labels provided below.
- Do not use private notes, uploaded files, source text, quoted material, or any source-derived details.
- Keep the card scoped to the current concept and Bloom target.
- Return only valid JSON.
- Produce 2 to 3 questions for `practice`; produce 2 to 4 questions for `level_up`.
- Use stable ids like `q1`, `q2`, `q3`.
- Choose the question type dynamically from `multiple_choice`, `short_answer`, and `long_answer`.
- Choose `difficulty` dynamically from `light`, `standard`, and `challenge`.
- Prefer lower-friction `multiple_choice` for beginner recognition checks, supporting details, or early practice.
- Prefer `short_answer` for important recall, definitions, relationships, and misconception checks.
- Use `long_answer` sparingly for essential, high-importance checks that require explanation, application, or comparison.
- Use `light` for supporting or introductory labels, `standard` for core labels, and `challenge` only for essential labels where a learner must integrate or apply ideas.
- Do not scare the learner away: keep prompts compact, use plain language, and avoid unnecessarily complex multi-step tasks.
- For `level_up`, include at least one `short_answer` or `long_answer` question unless every mastery label is purely recognition-level.
- For `multiple_choice`, include 3 or 4 plausible options. Do not include a visible answer key.

Concept:
{{ concept }}

Mastery check labels:
{{ mastery_check_labels }}

Bloom target: {{ bloom_target }}
Quiz type: {{ quiz_type }}

Return this JSON shape exactly:

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple_choice",
      "prompt": "string",
      "mastery_label": "string",
      "difficulty": "light",
      "options": ["string", "string", "string"]
    }
  ]
}
```

For `short_answer` and `long_answer`, omit `options`.
