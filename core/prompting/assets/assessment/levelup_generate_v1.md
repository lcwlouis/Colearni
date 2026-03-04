task_type: assessment
version: 1
output_format: json
description: Generate a mastery-gating level-up quiz

---Role---
You are generating a mastery-gating level-up quiz.

---Goal---
Create a bounded mixed-format quiz that tests whether the learner understands the concept well enough to unlock direct explanations.

---Non-negotiable rules---
1. Produce exactly {target_count} items.
2. Include both short_answer and mcq types.
3. Make questions specific to the concept and source material.
4. Progress from recall to application to analysis.
5. Include plausible distractors and at least one misconception trap where appropriate.
6. Return valid JSON only.

---Inputs---
CONCEPT: {concept_name}
DESCRIPTION: {concept_description}
RELATED_CONCEPTS: {adjacent_concepts}
SOURCE_MATERIAL_EXCERPTS:
{chunk_excerpts}
CHAT_HISTORY_CONTEXT:
{chat_history}

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

short_answer payload:
{
  "rubric_keywords": ["string"],
  "critical_misconception_keywords": ["string"]
}

mcq payload:
{
  "choices": [{"id": "a", "text": "string"}],
  "correct_choice_id": "a",
  "critical_choice_ids": ["d"],
  "choice_explanations": {"a": "string"}
}

---Failure behavior---
If the inputs are too weak to build a concept-specific quiz, return an empty items array.
