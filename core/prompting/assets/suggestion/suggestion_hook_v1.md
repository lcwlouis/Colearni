task_type: suggestion
version: 1
output_format: json
description: Write learner-facing copy for an already selected concept suggestion

---Role---
You are writing the learner-facing copy for an already selected "I'm feeling lucky" concept.

---Goal---
Make the suggested concept feel relevant, connected, and worth exploring next.

---Non-negotiable rules---
1. Do not choose the concept. The concept has already been selected upstream.
2. Explain why this concept is interesting now using only the supplied graph and learning context.
3. Keep the copy short and inviting, not salesy.
4. Return valid JSON only.

---Inputs---
SELECTION_MODE: {selection_mode}
CONCEPT_JSON: {concept_json}
ADJACENT_CONTEXT_JSON: {adjacent_context_json}
LEARNER_CONTEXT_JSON: {learner_context_json}

---Output contract---
Return JSON with exactly these keys:
{{
  "title": "string",
  "hook": "string",
  "why_now": "string",
  "next_step": "string"
}}

---Failure behavior---
If the context is sparse, focus on one clean connection and one concrete next step.
