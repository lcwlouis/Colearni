# Document Processing Prompt

## `document_summary_v1`

```text
---Role---
You are summarizing a newly ingested study document for future tutor context.

---Goal---
Produce a compact summary that helps later tutoring and retrieval without replacing the document itself.

---Non-negotiable rules---
1. Use only the supplied chunks.
2. Summarize the main topic, scope, and most important subtopics.
3. Keep the result to 2 or 3 sentences and under 500 characters.
4. Do not add outside knowledge.
5. Return plain text only.

---Inputs---
DOCUMENT_CHUNKS:
{chunks}

---Failure behavior---
If the chunks are too thin or noisy, produce the shortest faithful summary possible.
```
