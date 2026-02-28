task_type: practice
version: 1
output_format: json
description: Generate flashcards for concept review

---Role---
You are generating flashcards for spaced-repetition concept review.

---Goal---
Create concise, targeted flashcards that help the learner recall key facts and relationships about the concept.

---Non-negotiable rules---
1. Return valid JSON only.
2. Each card must have front (question), back (answer), and hint fields.
3. Cards must be specific to the concept and grounded in the source material.
4. Keep front/back text concise.

---Inputs---
CARD_COUNT: {card_count}
CONTEXT_JSON: {context_json}

---Output contract---
Return JSON with this shape:
{{
  "flashcards": [
    {{
      "front": "question text",
      "back": "answer text",
      "hint": "optional hint"
    }}
  ]
}}
