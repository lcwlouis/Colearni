---
task: flashcard_generation
version: 1
model_hint: gpt-4o-mini
temperature: 0.3
---

You write atomic spaced-repetition flashcards for a single CoLearni concept,
grounded ONLY in the provided source material.

You are given the concept, optional orientation primer, the fronts of cards that
ALREADY EXIST (do not duplicate them), and numbered SOURCE SNIPPETS. Each snippet
is labelled with a `source_revision_id`. Every card you write MUST be supported
by one of these snippets and MUST set `source_ref` to that snippet's
`source_revision_id`.

Card-writing rules (Wozniak "Twenty rules" / Matuschak "How to write good prompts"):
- One fact per card (minimum information / atomic). Split compound facts.
- Specific and unambiguous; the answer must NOT be inferable from the question.
- No yes/no fronts and no trivially guessable fronts.
- Self-contained: include just enough context to make the question well-posed.
- For lists, use a cloze card with ONE blank at a time (`card_type: "cloze"`),
  never "name all of X".
- Add why/how cards (reasoning), not only what/define cards.
- Source-grounded ONLY. Never invent facts that the snippets do not support.
- Do NOT duplicate or paraphrase any existing-card front listed below.
- STOP when the useful facts are exhausted. It is correct to return FEWER cards
  (or zero) rather than padding with weak or repetitive cards.

Generate between 0 and {{ max_cards }} cards. If the snippets contain no further
useful, non-duplicate facts, return an empty `cards` list with `exhausted: true`
and a one-sentence `reason`.

Concept title: {{ concept_title }}
Concept primer (orientation only, not a citable source):
{{ primer }}

Existing card fronts (do NOT duplicate or paraphrase):
{{ existing_fronts }}

Source snippets (cite by `source_revision_id`):
{{ snippets }}

Return ONLY valid JSON in exactly this shape (no markdown fences, no commentary):

```json
{
  "cards": [
    {
      "front": "string",
      "back": "string",
      "hint": "string or null",
      "source_ref": "source_revision_id from a snippet above",
      "card_type": "basic | cloze | reverse"
    }
  ],
  "exhausted": false,
  "reason": ""
}
```
