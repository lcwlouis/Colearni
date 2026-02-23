# docs/GRAPH.md

## Purpose
Coleonri’s knowledge graph must stay **connected, manageable, and explainable** as ingestion scales.  
We do this with a **two-layer graph** + two consolidation systems:

1) **Online Resolver (ingestion-time, cheap + bounded)**  
   Prevents duplicates from exploding and keeps the canonical graph usable immediately.

2) **Graph Gardener (offline, smarter + budgeted)**  
   Periodically improves quality by consolidating near-duplicates and fixing earlier mistakes.

The system must **never**:
- scan all nodes every run
- loop endlessly
- burn unbounded LLM tokens

---

## Core Concepts

### Raw Graph (audit trail; never shown directly)
- Extracted per chunk; noisy; duplicates allowed.
- Used for provenance and future reconciliation.

### Canonical Graph (the product graph)
- What users see and what all learning state references.
- Contains merged concepts/edges with descriptions and weights.

---

## Required Data Structures (logical; exact schema in migrations)

### Raw
- `concepts_raw`
  - `workspace_id`
  - `chunk_id`
  - `name` (as extracted)
  - `context_snippet` (small text around mention)
  - `extracted_json` (optional)
  - `created_at`

- `edges_raw`
  - `workspace_id`
  - `chunk_id`
  - `src_name`, `tgt_name` (raw)
  - `relation_type`
  - `description`
  - `keywords[]`
  - `weight`
  - `created_at`

### Canonical
- `concepts_canon`
  - `workspace_id`
  - `canonical_name`
  - `description`  ✅
  - `aliases[]`     ✅
  - `embedding` (optional; recommended for similarity)
  - `is_active` (true unless merged away)
  - `dirty` (bool; queued for gardener)
  - `created_at`, `updated_at`

- `edges_canon`
  - `workspace_id`
  - `src_concept_id`, `tgt_concept_id`
  - `relation_type`
  - `description` ✅
  - `keywords[]` ✅
  - `weight` ✅
  - `updated_at`

- `provenance`
  - `workspace_id`
  - `target_type` (`concept|edge`)
  - `target_id`
  - `chunk_id`

### Merge bookkeeping
- `concept_merge_map`
  - `workspace_id`
  - `alias` (normalized)
  - `canon_concept_id`
  - `confidence`
  - `method` (`exact|lexical|vector|llm|manual`)
  - `updated_at`

- `concept_merge_log`
  - `workspace_id`
  - `from_concept_id`
  - `to_concept_id`
  - `reason`
  - `method`
  - `confidence`
  - `created_at`

> **Important:** All merges must be reversible by reading `concept_merge_log`.

---

## Indexes / Blocking (to avoid full scans)
Use cheap candidate generation before any LLM call:

1) **Exact alias lookup**  
   `concept_merge_map(alias)`

2) **Lexical blocking**  
   Recommended: `pg_trgm` similarity on `canonical_name` and optionally `aliases` (or a flattened alias table).

3) **Vector top-K** (optional but recommended)  
   `concepts_canon.embedding` via pgvector; query with `<->` and `LIMIT K`.

These return **small candidate sets** (K=5 to 10).

---

## Online Resolver (Ingestion-Time Merge)

### Inputs
- `raw_concept: {name, context_snippet, chunk_id}`
- `workspace_id`

### Output
- `canon_concept_id` + optional updates to canonical concept/aliases/description/provenance
- A `dirty` mark if canonical concept was modified

### Candidate generation (bounded)
**Always in this order:**
1) Normalize `name` → `name_norm`
2) Alias map exact match:
   - if `concept_merge_map[name_norm]` exists → MERGE immediately (confidence=1.0)
3) Lexical candidates:
   - find top 5 canonical nodes by trigram similarity
4) Vector candidates (optional):
   - embed `name + context_snippet` (or use chunk embedding centroid)
   - top 10 nearest canonical nodes
5) Combine and de-dup candidates; keep top **<= 10**

### Decision rule (no LLM unless needed)
- If best exact match → MERGE
- Else if best lexical similarity >= `0.85` and margin over #2 >= `0.10` → MERGE (method=lexical)
- Else if best vector similarity strong (your chosen threshold) and margin >= set margin → MERGE (method=vector)
- Else → call LLM disambiguation **once**, with only these candidates.

### LLM disambiguation (schema-first)
Provide:
- `raw_name`, `context_snippet`
- candidates: `id`, `canonical_name`, `description`, `aliases`

LLM must output:
- `decision`: `MERGE_INTO` or `CREATE_NEW`
- `merge_into_id` (if merge)
- `confidence` (0–1)
- `alias_to_add` (optional)
- `proposed_description` (optional, short)

If `confidence < 0.65` → default to `CREATE_NEW` (safety).

### Canonical concept merge rules
When merging raw into canonical:
- Add raw `name` into `aliases` if not present
- Update `concept_merge_map` for raw alias → canonical
- Update description with **safe merge**:
  - Keep canonical description if present and good
  - Else set from `proposed_description`
  - Never let description exceed ~500 chars without summarising
- Add provenance link: canonical concept ↔ chunk_id
- Mark `dirty = true` if any significant update happened

When creating new:
- Insert canonical node with:
  - `canonical_name = raw_name` (or normalized title-case)
  - `aliases = [raw_name]`
  - `description` from LLM extraction (short)
- Insert alias mapping (raw_name → new_id)
- Add provenance
- Mark `dirty = true`

### Edge upsert rules (canonical)
Convert raw edges to canonical IDs via resolver, then:
- Unique key: `(workspace_id, src_id, tgt_id, relation_type)`
- If exists:
  - merge keywords (set union)
  - merge descriptions:
    - prefer the clearer/longer up to 300 chars
  - `weight = min(weight + delta, weight_cap)`
  - append provenance
- If not:
  - insert edge with description/keywords/weight + provenance

---

## Graph Gardener (Offline Consolidation)

### Goal
Improve canonical graph quality over time with strict budgets.

### Input set (NEVER “all nodes”)
Only nodes that are **dirty** OR recently created OR have high duplicate risk:
- `concepts_canon WHERE dirty=true AND is_active=true LIMIT N`

### Blocking + clustering (bounded)
For each dirty node:
1) Generate candidate set using:
   - lexical blocking (top 10)
   - vector top-K (top 10)
2) Build an undirected similarity graph among candidates + node
3) Find clusters via simple union-find / connected components with threshold

### LLM merge step (budgeted)
For each cluster with size >= 2:
- LLM chooses:
  - canonical representative
  - best description (<= 500 chars)
  - alias merge list
- Confidence must be provided; if < 0.70 skip cluster (leave for later/manual)

### Merge execution (idempotent)
For each node being merged-away:
- set `is_active=false`
- write `concept_merge_log(from -> to)`
- repoint edges:
  - update all `edges_canon` where src/tgt = from_id to to_id
  - then upsert to dedupe edge keys
- update `concept_merge_map` for all aliases → final canonical
- mark impacted canonical node(s) dirty=false at end (if stable)

### No endless loops
- Each run processes a finite dirty set.
- Merged-away nodes cannot be processed again (`is_active=false`).
- A node can be re-marked dirty only by new ingestion updates or explicit changes.

---

## Budget Defaults (tune later)
### Online Resolver
- Max candidates per raw concept: **10**
- Max LLM disambiguations per chunk: **3**
- Max LLM disambiguations per document: **50**
- If exceeded → fallback to deterministic create/merge rules (no more LLM)

### Gardener
- Run frequency: daily OR every `N=20` documents ingested
- Max dirty nodes per run: **200**
- Max clusters merged per run: **50**
- Max LLM calls per run: **30**
- Hard stop when budget reached

---

## Quality Metrics (simple, actionable)
Track per workspace:
- Duplicate rate: `#inactive_canon / #total_canon`
- Connectivity: average degree of canonical nodes
- Merge correctness sampling: random 20 merges/week for review
- Token cost: LLM calls per doc + per gardener run
- User outcome: “level-up completion rate” per concept (from PRODUCT_SPEC)

---

## Failure & Safety Handling
- If resolver is unsure → create new node (safe).
- Never delete anything; use `is_active=false` + logs.
- Always preserve provenance links.
- Provide admin endpoint later to manually map alias → canonical and rerun affected edges.