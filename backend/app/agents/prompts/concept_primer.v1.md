---
task: concept_primer
version: 1
model_hint: gpt-4o-mini
temperature: 0.3
---

You are writing a short orientation primer for a single CoLearni concept.

The primer gives a learner just enough context to get oriented before Socratic
tutoring begins. It is abstract, concept-level orientation content.

Rules:
- Write from the concept title, level, Bloom target, mastery labels, and the Trail topic/goal provided below.
- Do not use private notes, uploaded files, source text, quoted material, or any source-derived details.
- Keep the card scoped to the current concept.
- Return only valid JSON. No markdown fences, no explanation.
- `overview` is one short orientation paragraph (2-4 sentences). Plain language, no jargon dumps.
- Provide 3 to 6 `key_terms`. Each is a term a learner needs to recognize for this concept.
- Each `definition` is one concise sentence.
- Keep everything tight; this runs on a small token budget.

Trail topic: {{ topic }}
Trail goal: {{ goal }}

Concept title: {{ concept_title }}
Concept level: {{ concept_level }}
Bloom target: {{ bloom_target }}

Mastery check labels:
{{ mastery_check_labels }}

Return this JSON shape exactly:

```json
{
  "overview": "string",
  "key_terms": [
    {"term": "string", "definition": "string"}
  ]
}
```
