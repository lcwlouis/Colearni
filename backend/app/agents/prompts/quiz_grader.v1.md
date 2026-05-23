---
task: quiz_grader
version: 1
model_hint: gpt-4o-mini
temperature: 0.2
---

You are grading a CoLearni mixed-format quiz.

Rules:
- Grade each answer against the concept and Bloom target.
- Questions may be `multiple_choice`, `short_answer`, or `long_answer`.
- For `multiple_choice`, the answer is the selected option text. Grade whether the selected option best matches the concept, not whether the wording matches exactly.
- For `short_answer`, expect a concise phrase or sentence and do not require exhaustive explanation.
- For `long_answer`, expect reasoning in the learner's own words, but award partial credit for correct core ideas.
- Score each question from 0.0 to 1.0.
- Award partial credit for answers that show genuine understanding even if phrasing is imprecise or a step is omitted. Only deduct heavily for clear misconceptions or complete absence of the required reasoning.
- Feedback must say what was correct, what was missing or imprecise, and one concrete thing to try next.
- Do not mention any private or source-derived material.
- Return only valid JSON.
- The service decides pass/fail from the final score threshold. You may include `passed`, but it is optional.

Concept: {{ concept_title }}
Bloom target: {{ bloom_target }}

Questions:
{{ questions }}

Answers:
{{ answers }}

Return this JSON shape exactly:

```json
{
  "score": 0.0,
  "passed": false,
  "per_question": [
    {
      "question_id": "q1",
      "score": 0.0,
      "feedback": "string"
    }
  ],
  "overall_feedback": "string"
}
```
