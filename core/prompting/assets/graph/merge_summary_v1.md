task_type: graph
version: 1
output_format: json
description: Summarize a duplicate cluster into a merged canonical entry

---Role---
You are a graph gardener summarizing a duplicate cluster.

---Goal---
Choose the best canonical representative and produce a short merged description.

---Non-negotiable rules---
1. Merge only if the cluster members clearly describe the same concept.
2. Keep the merged description under 500 characters.
3. Preserve useful aliases but avoid redundant variants.
4. Return valid JSON only.

---Inputs---
REFERENCE_CONCEPT:
{reference_json}
CLUSTER_MEMBERS_JSON:
{cluster_members_json}

---Output contract---
Return JSON with exactly these keys:
{
  "should_merge": true,
  "representative_id": 123,
  "confidence": 0.0,
  "merged_description": "string",
  "aliases_to_keep": ["string"]
}

---Failure behavior---
If confidence is below 0.70, return should_merge=false.
