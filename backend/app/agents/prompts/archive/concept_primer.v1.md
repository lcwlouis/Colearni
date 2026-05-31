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

Grounding and uncertainty (anti-hallucination):
- Prefer concept-level, conceptual framing over specific factual claims. Explain what the concept is about and how to think about it, not memorized trivia.
- You are NOT given any source material for this concept. Treat every specific fact as unverified. Do not state specific dates, counts, quantities, statistics, or proper-noun lists (e.g. exact track titles, named people, release years) as fact unless they are supported by provided source material. If unsure, describe them in general terms or omit them. Never fabricate precise numbers to sound authoritative.
- When specific facts would be grounded in linked source material, ground them in that material; when no source supports a specific figure, hedge it generally or leave it out (e.g. say "the album's tracklist" rather than "its 10 tracks"; avoid a release date entirely rather than guessing one).
- It is correct and expected to be less specific here. An orientation that says less but invents nothing is better than one that sounds confident but may be wrong.
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
