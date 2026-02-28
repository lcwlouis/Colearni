task_type: practice
version: 1
output_format: json
description: Generate a practice quiz for concept reinforcement

---Role---
You are generating a practice quiz for concept reinforcement (not mastery gating).

---Goal---
Create a mixed-format practice quiz that helps the learner reinforce understanding through novel, creative questions.

---Non-negotiable rules---
1. Return valid JSON only.
2. Include at least one short_answer and one mcq item.
3. Each question must be specific to the concept and source material.
4. Generate completely novel and creative questions.

---Inputs---
QUESTION_COUNT: {question_count}
CONTEXT_JSON: {context_json}
NOVELTY_SEED: {novelty_seed}

---Output contract---
Return JSON with this shape:
{{
  "items": [
    {{
      "item_type": "short_answer|mcq",
      "prompt": "string",
      "payload": {{}}
    }}
  ]
}}

short_answer payload:
{{
  "rubric_keywords": ["string"],
  "critical_misconception_keywords": ["string"]
}}

mcq payload:
{{
  "choices": [{{"id": "a", "text": "string"}}],
  "correct_choice_id": "a",
  "critical_choice_ids": ["d"],
  "choice_explanations": {{"a": "string"}}
}}
