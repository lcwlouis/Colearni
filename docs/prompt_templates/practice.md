# Practice Prompts

## `practice_quiz_generate_v1`

```text
---Role---
You are generating a non-leveling practice quiz for retrieval practice.

---Goal---
Create a short, varied, concept-specific quiz that helps the learner rehearse understanding without affecting mastery state.

---Non-negotiable rules---
1. Produce between 3 and 6 items.
2. Include at least one `short_answer` and one `mcq`.
3. Make the questions novel relative to the supplied context.
4. Prefer concise prompts and concrete distractors.
5. Return valid JSON only.

---Inputs---
QUESTION_COUNT: {question_count}
CONTEXT_JSON:
{context_json}
NOVELTY_SEED: {novelty_seed}

---Output contract---
Return JSON with this shape:
{
  "items": [
    {
      "item_type": "short_answer|mcq",
      "prompt": "string",
      "payload": {}
    }
  ]
}

---Failure behavior---
If you cannot create a diverse set, still return valid JSON with the strongest available concept-specific items.
```

## `practice_flashcards_generate_v1`

```text
---Role---
You are generating study flashcards for retrieval practice.

---Goal---
Create concise flashcards that help the learner actively recall, not passively reread.

---Non-negotiable rules---
1. Produce exactly {card_count} flashcards.
2. Make the front side a cue or question, not a summary heading.
3. Make the back side short and specific.
4. Make the hint useful but not a giveaway.
5. Return valid JSON only.

---Inputs---
CARD_COUNT: {card_count}
CONTEXT_JSON:
{context_json}

---Output contract---
Return JSON with this shape:
{
  "flashcards": [
    {
      "front": "string",
      "back": "string",
      "hint": "string"
    }
  ]
}

---Failure behavior---
If the concept context is thin, keep the cards simple and grounded rather than inventing details.
```
