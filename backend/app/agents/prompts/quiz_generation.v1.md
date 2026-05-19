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
- Produce 2 to 4 questions total.
- Use stable ids like `q1`, `q2`, `q3`.
- Cover explain, apply, and compare/misconception checking when the labels support it.

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
      "type": "explain",
      "prompt": "string",
      "mastery_label": "string"
    }
  ]
}
```
