# Trail Pack Spec

## Purpose

A Trail Pack is a shareable/exportable package containing the safe public structure of a Trail.

Trail Packs are content-light by default. They may include graph structure, concept metadata, learning objectives, mastery check labels, source metadata, and research trace. They must not include private workspace content or raw source-derived content.

## File Structure

```text
trail-pack/
  manifest.yaml
  graph.yaml
  concepts/
    vectors.yaml
    matrices.yaml
    eigenvectors.yaml
  sources.yaml
  research_trace.yaml
```

## manifest.yaml

Example:

```yaml
id: linear-algebra-for-ml
title: Linear Algebra for Machine Learning
version: 1.0.0
created_by: local_user
pack_type: structure
license: CC-BY-NC-4.0
content_included: false
hydration_supported: true
```

Required fields:

- `id`
- `title`
- `version`
- `pack_type`
- `content_included`
- `hydration_supported`

`pack_type` should be `structure` for the MVP.

## graph.yaml

Example:

```yaml
nodes:
  - id: vectors
    title: Vectors
    node_type: concept
    concept_level: topic
  - id: matrices
    title: Matrices
    node_type: concept
    concept_level: topic

edges:
  - source: vectors
    target: matrices
    relation_type: prerequisite
```

Rules:

- Node ids must be unique within the pack.
- Every node must include `concept_level`.
- Valid concept levels are `umbrella`, `topic`, `subtopic`, and `granular`.
- Edge endpoints must reference known node ids.
- Prerequisite edges should be acyclic unless the pack explicitly allows cycles.
- Graph size should stay within MVP import limits.

## concepts/eigenvectors.yaml

Example:

```yaml
id: eigenvectors
title: Eigenvectors
node_type: concept
concept_level: subtopic
parents:
  - linear_transformations
prerequisites:
  - matrices
  - determinants
children:
  - diagonalization
  - pca

learning_objectives:
  - understand_geometric_interpretation
  - compute_basic_example
  - connect_to_pca

mastery_check_labels:
  - explain_in_own_words
  - solve_basic_problem
  - compare_with_related_concept

source_refs:
  - source_id: mit_ocw_linear_algebra_lecture_21
    relevance: primary_explanation

content_included: false
hydration_required: true
```

Concept files may include abstract objectives and mastery labels. They must not include copied source prose, private notes, generated summaries from private/user-uploaded sources, or private quiz content.

`parents` and `children` are convenience references for hierarchy/navigation. They do not replace `concept_level`.

## sources.yaml

Example:

```yaml
sources:
  - id: mit_ocw_linear_algebra_lecture_21
    title: MIT OCW Linear Algebra Lecture 21
    url: https://example.com
    origin: research_agent
    access: public
    license: unknown
    include_on_public_export: true
    content_included: false

  - id: uploaded_textbook_pdf
    title: User uploaded textbook
    origin: user_upload
    access: private
    include_on_public_export: false
    content_included: false
```

Source origins:

```text
research_agent
user_upload
manual
system
```

Access levels:

```text
public
private
restricted
unknown
```

Rules:

- `user_upload` sources must not be included in public export except as excluded-source report entries.
- `research_agent` public sources may include links and metadata only.
- `unknown` license means no content redistribution.
- `content_included` must be `false` for MVP public packs.

## research_trace.yaml

Example:

```yaml
topic: Eigenvectors
generated_by: colearni_research_agent
queries:
  - eigenvectors geometric intuition beginner
  - eigenvectors applications PCA
selected_public_sources:
  - source_id: mit_ocw_linear_algebra_lecture_21
    reason: introductory explanation
excluded_sources:
  - source_id: uploaded_textbook_pdf
    reason: user_uploaded_private_source
```

The research trace may include queries, selected public source links, source titles, source types, selection reasons, and excluded source notes.

It must not include copied source content or long summaries.

## Validation Rules

Reject any public Trail Pack that contains:

- Raw chunks.
- Embeddings.
- Uploaded files.
- Chat history.
- Private notes.
- Mastery records.
- Concrete source-derived prose by default.
- Generated summaries from private/user-uploaded sources.
- Generated quizzes from private/user-uploaded sources.

Import validation must also reject malformed YAML, missing required manifest fields, unknown node references, duplicate node ids, unknown concept levels, and unsafe fields.

## Export Report

Export should return a report like:

```text
Included:
- 23 concepts
- 31 edges
- 8 public source links
- research trace

Excluded:
- 2 uploaded PDFs
- 145 chunks
- 23 embeddings
- 4 private notes
- mastery history
```

The report is part of the safety UX. It tells users what was removed and why.
