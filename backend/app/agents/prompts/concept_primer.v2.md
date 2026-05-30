---
task: concept_primer
version: 2
model_hint: gpt-4o-mini
temperature: 0.3
---

You are writing a short orientation primer for a single CoLearni concept.

The primer gives a learner just enough context to get oriented before Socratic
tutoring begins. It is abstract, concept-level orientation content.

Rules:
- Write from the concept title, level, Bloom target, mastery labels, the Trail topic/goal, and the surrounding graph neighbours provided below.
- Do not use private notes, uploaded files, source text, quoted material, or any source-derived details.
- Keep the card scoped to the current concept.
- Stay coherent with the surrounding graph: prefer key terms that map to the neighbouring concepts and to the mastery checks below. Do NOT introduce major topics that are not represented among the neighbours — that signals hallucination.
- Return only valid JSON. No markdown fences, no explanation.
- `overview` is one short orientation paragraph (2-4 sentences). Plain language, no jargon dumps.
- Provide 3 to 6 `key_terms`. Each is a term a learner needs to recognize for this concept; favour terms aligned with the neighbours and mastery checks.
- When choosing key terms, prefer ones that correspond to the concept's **contained** and **related** neighbours — these are the most useful for orienting a learner — while still including any essential terms the concept needs even if they are not named among the neighbours.
- Each `definition` is one concise sentence.
- Provide 3 to 4 `sample_questions`: short learner-facing starter prompts (≤ 90 characters each) tailored to THIS concept (e.g. "Walk me through why X mattered", "Give me one hint to start", "Check my understanding of Y"). Write them in the learner's voice, addressed to the tutor.
- Keep everything tight; this runs on a small token budget.

Trail topic: {{ topic }}
Trail goal: {{ goal }}

Concept title: {{ concept_title }}
Concept level: {{ concept_level }}
Bloom target: {{ bloom_target }}

Mastery check labels:
{{ mastery_check_labels }}

Surrounding graph neighbours (anchor key terms to these; do not stray beyond them):
- Prerequisites: {{ prerequisites }}
- Containing concepts: {{ containing_nodes }}
- Contained concepts: {{ contained_nodes }}
- Related concepts: {{ related }}
- Applications: {{ application_nodes }}
- Nearby (1-2 layers out): {{ nearby }}

Return this JSON shape exactly:

```json
{
  "overview": "string",
  "key_terms": [
    {"term": "string", "definition": "string"}
  ],
  "sample_questions": ["string", "string", "string"]
}
```
