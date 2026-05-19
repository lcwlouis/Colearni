---
task: trail_generation
version: 1
---

You are an expert curriculum designer building a concept graph for a learning trail.

## Input

- **Topic**: {{topic}}
- **Learning goal**: {{goal}}
- **Target depth** (Bloom's level): {{target_depth}}
- **Maximum nodes**: {{max_nodes}}

## Your task

Return a JSON object describing a concept graph with `nodes` and `edges`.

The graph must:
- Have between 10 and {{max_nodes}} nodes.
- Generate as many concepts as are useful for the topic, up to {{max_nodes}} nodes.
- Prefer fewer nodes when the topic is narrow; use more nodes when the topic naturally requires breadth.
- Do not exceed {{max_nodes}} nodes.
- Include at least one `umbrella` or `topic` level node that acts as the entry point.
- Have unique `slug` values (lowercase, hyphen-separated, e.g. `linear-algebra`).
- Have edges that only reference slugs present in the node list.
- Have no cycles in `prerequisite` edges.

## Output schema

Return ONLY valid JSON in the final assistant answer/completion, no markdown fences, no explanation. If you use hidden reasoning, do not stop after reasoning; always emit the complete JSON object as the final answer.

```json
{
  "nodes": [
    {
      "slug": "string",
      "title": "string",
      "node_type": "concept | skill | misconception | example",
      "concept_level": "umbrella | topic | subtopic | granular",
      "difficulty": "beginner | intermediate | advanced",
      "bloom_level": "remember | understand | apply | analyze | evaluate | create",
      "mastery_check_labels": ["label1", "label2"],
      "metadata_json": {}
    }
  ],
  "edges": [
    {
      "source_slug": "string",
      "target_slug": "string",
      "relation_type": "prerequisite | contains | application | related"
    }
  ]
}
```

## Guidelines

- `bloom_level` on each node should reflect the cognitive depth required to master that node.
- Nodes with `concept_level: granular` should be the most detailed, leaf-level ideas.
- Use `contains` for parent-to-child structure.
- Use `prerequisite` when the source concept should be learned before the target concept.
- Use `application` when the source concept is applied by, or practiced through, the target concept.
- Use `related` for meaningful cross-links between sibling or distant concepts that are connected but are not prerequisites, containment, or applications.
- Include a few `related` edges when the topic has useful non-linear connections; do not force them when no meaningful relationship exists.
- `mastery_check_labels` are short quiz-topic hints, e.g. `["definition", "example"]`.
- Do NOT include any text outside the JSON object.
