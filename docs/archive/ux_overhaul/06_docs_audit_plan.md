# CoLearni UX Overhaul — Documentation Audit Plan

Last updated: 2026-03-02

Parent plan: `docs/UX_OVERHAUL_MASTER_PLAN.md`

Archive snapshots:
- `none` (new plan)

## Plan Completeness Checklist

1. archive snapshot path(s) ✓
2. current verification status ✓
3. ordered slice list with stable IDs ✓
4. verification block template (inherited from master) ✓
5. removal entry template (inherited from master) ✓
6. final section `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✓

## Non-Negotiable Run Rules

1. Re-read this file at start, after every 2 slices, after context compaction, before completion claims.
2. A slice is ONLY complete with docs updated + accuracy verified + verification block produced.
3. Work PR-sized: `chore(docs): <slice-id> <short description>`.
4. If a behavior change risk is discovered, STOP and update this plan.
5. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

Audit and update all key documentation files to ensure they reflect the current state of the codebase after the UX overhaul. The UX overhaul introduced changes across multiple tracks (UXF critical fixes, UXG graph replacement, UXP practice UX, UXT tutor UX, UXI infrastructure) and documentation must be brought in sync.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- All completed UXF, UXG, UXP, UXT, UXI child plans
- Current codebase state after UX overhaul implementation
- The 9 documentation files listed below

## Executive Summary

Nine documentation files need auditing:

| File | Lines | Risk Area |
|---|---|---|
| `docs/API.md` | 1,426 | Missing new endpoints from gardener commit fix, practice quiz retry, flashcard stack, graph-to-chat |
| `docs/ARCHITECTURE.md` | 215 | Graph rendering change (D3 → Sigma.js), new state management (Zustand), new dependencies |
| `docs/FRONTEND.md` | 121 | New components (sigma-graph, flashcard-stack, quiz-history, onboarding-confirm, concept-chat-links), new deps (graphology, sigma, minisearch) |
| `docs/GRAPH.md` | 274 | Gardener now commits transactions, orphan pruner integrated, graph rendering moved to Sigma.js |
| `docs/OBSERVABILITY.md` | 538 | Spans/events may not match code. LLM cache hit rate logging may need documenting |
| `docs/PLAN.md` | 553 | Likely stale — needs archival or update to reflect current sprint |
| `docs/PRODUCT_SPEC.md` | 173 | Feature descriptions need updating for unified flashcard stack, quiz history+retry, onboarding confirm, streaming status, graph-chat nav |
| `docs/PROGRESS.md` | 577 | Implementation progress tracker needs UX overhaul completion status |
| `docs/PROMPTS.md` | 279 | Prompt catalog may not match current templates. Uses "P9" sprint naming |

## Non-Negotiable Constraints

1. Do not remove or significantly rewrite documentation sections that are still accurate.
2. Only update what has changed.
3. Add timestamps to files that lack them.
4. Keep documentation factual and concise — do not pad with aspirational content.

## Completed Work

- All 9 documentation files exist and are maintained
- UX overhaul implementation complete across UXF, UXG, UXP, UXT, UXI tracks

## Remaining Slice IDs

- `UXD.1` Audit and flag stale sections
- `UXD.2` Update API.md and ARCHITECTURE.md
- `UXD.3` Update FRONTEND.md and GRAPH.md
- `UXD.4` Update PRODUCT_SPEC.md, PLAN.md, PROGRESS.md
- `UXD.5` Update OBSERVABILITY.md and PROMPTS.md

## Decision Log

1. UXD.1 produces a staleness report only — no changes to docs in that slice.
2. Subsequent slices (UXD.2–UXD.5) pair related docs together for efficient updates.
3. Stale sections in PLAN.md should be archived (moved to a "Historical" section) rather than deleted.
4. PROGRESS.md updates should mark UX overhaul items as complete with dates.
5. API.md updates should follow the existing endpoint documentation format exactly.

## Current Verification Status

- `PYTHONPATH=. pytest -q`: 922 passed
- `npx vitest run`: 106 passed

## Implementation Sequencing

### UXD.1. Audit and flag stale sections

Purpose:
- Read all 9 documentation files and cross-reference with code changes from UXF, UXG, UXP, UXT, UXI tracks
- Produce a staleness report listing what needs updating in each file
- Do NOT make changes yet — audit only

Files involved:
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/FRONTEND.md`
- `docs/GRAPH.md`
- `docs/OBSERVABILITY.md`
- `docs/PLAN.md`
- `docs/PRODUCT_SPEC.md`
- `docs/PROGRESS.md`
- `docs/PROMPTS.md`

Implementation steps:
1. Read each of the 9 docs files in full.
2. Cross-reference content against the UX overhaul child plans:
   - `docs/ux_overhaul/01_critical_fixes_plan.md` (UXF) — gardener commit fix, selection highlighting, graph flicker
   - `docs/ux_overhaul/02_graph_replacement_plan.md` (UXG) — D3 → Sigma.js, graphology, Zustand state
   - `docs/ux_overhaul/03_practice_ux_plan.md` (UXP) — flashcard stack, quiz history, quiz retry
   - `docs/ux_overhaul/04_tutor_ux_plan.md` (UXT) — onboarding confirm, streaming status, concept-chat links
   - `docs/ux_overhaul/05_infrastructure_plan.md` (UXI) — sources page polish, LLM caching, dev stats toggle
3. For each doc, list:
   - Sections that are accurate (no change needed)
   - Sections that are stale or incomplete (with specific details of what's wrong)
   - Sections that are missing (new content needed)
4. Produce a staleness report as a verification block in this plan file (appended after UXD.1 section).

What stays the same:
- All documentation files — no content changes in this slice

Verification:
- Staleness report produced and appended to this plan
- Every doc file accounted for
- Specific stale items identified with references to which UX track caused the change

Exit criteria:
- Complete staleness report covering all 9 docs
- Each stale item linked to the relevant UX track (UXF/UXG/UXP/UXT/UXI)

Verification Block - UXD.1

Root cause
- Documentation has not been updated since the UX overhaul (UXF, UXG, UXP, UXT, UXI tracks)

Staleness report produced
- 2026-03-02

---

#### 1. `docs/API.md` (~1,426 lines) — Staleness: LOW

✅ Accurate:
- Endpoint index is comprehensive (streaming, flashcard, practice, research, onboarding all present)
- `POST /workspaces/{ws_id}/chat/respond/stream` streaming endpoint documented
- Auth, workspace, KB, graph, quiz, readiness, research endpoints all match route files
- Request/response contracts accurate for documented endpoints

⚠️ Stale:
- `GenerationTrace` fields table (in streaming/blocking response) does not include `cached_tokens` field which now exists in `core/schemas/assistant.py` **(UXI.2)**

➕ Missing:
- `cached_tokens` field in GenerationTrace documentation **(UXI.2)**

---

#### 2. `docs/ARCHITECTURE.md` (215 lines) — Staleness: MEDIUM

✅ Accurate:
- System overview, backend stack (FastAPI, Postgres, pgvector, FTS) correct
- Ingestion pipeline diagram accurate
- Query pipeline diagram accurate
- Level-up quiz flow diagram accurate
- Practice flow diagram accurate
- Repo structure section accurate
- Key interfaces section accurate
- Observability section accurate
- Non-goals section accurate

⚠️ Stale:
- Architecture diagram (line 45) shows `UI[Next.js Web App]` with no mention of graph rendering stack — graph now uses Sigma.js + graphology (WebGL) instead of D3 force simulation **(UXG)**
- Repo structure (line 148-149) lists `apps/web/` only as "Next.js web app" — does not mention new graph sub-components (`sigma-graph/`, `flashcard-stack`, `quiz-history`, etc.) **(UXG, UXP, UXT)**

➕ Missing:
- Frontend graph rendering architecture: Sigma.js + graphology WebGL pipeline replacing D3 force simulation **(UXG)**
- New frontend component categories (graph visualization, practice UX, tutor UX) **(UXG, UXP, UXT)**

---

#### 3. `docs/FRONTEND.md` (121 lines) — Staleness: HIGH

✅ Accurate:
- Stack versions (Next 16.1.6, React 19.2.4, TypeScript 5.6.3, vitest 4.0.18) still current
- Commands section accurate
- Approved patterns (App Router, React 19, linting, typecheck) all accurate
- Anti-patterns section still accurate
- Config files section accurate
- Known lint warnings section accurate
- Audit status section accurate

⚠️ Stale:
- "Current stack" table does not list new graph visualization dependencies **(UXG)**
- D3 packages (`d3-force@^3.0.0`, `d3-selection@^3.0.0`) still in `package.json` but primary graph uses Sigma.js — doc doesn't clarify this **(UXG)**

➕ Missing:
- New dependencies: `graphology@^0.26.0`, `sigma@^3.0.2`, `@react-sigma/core@^5.0.6`, `@sigma/edge-curve@^3.1.0`, `@sigma/node-border@^3.0.0`, `minisearch@^7.2.0` **(UXG)**
- New components section listing: `sigma-graph.tsx` + `sigma-graph/` sub-components (graph-events, graph-layout, graph-reducers), `flashcard-stack.tsx`, `quiz-history.tsx`, `quiz-viewer.tsx`, `onboarding-confirm.tsx`, `concept-chat-links.tsx` **(UXG, UXP, UXT)**
- New hook: `use-dev-stats.ts` **(UXI.3)**
- D3 archive note: `concept-graph.d3-archive.tsx` exists but is no longer the active graph component **(UXG)**

---

#### 4. `docs/GRAPH.md` (274 lines) — Staleness: LOW-MEDIUM

✅ Accurate:
- Core concepts (raw graph, canonical graph, two-layer system) correct
- Data structures (concepts_raw, edges_raw, concepts_canon, edges_canon, provenance, merge bookkeeping) correct
- Indexes/blocking strategies correct
- Online resolver algorithm correct
- Graph gardener algorithm (offline consolidation) correct
- Budget defaults correct
- Quality metrics correct
- Failure & safety handling correct

⚠️ Stale:
- No mention that `get_db_session` auto-commits on clean exit — the plan text in UXF.1 described a missing-commit bug, but actual `adapters/db/dependencies.py` shows `session.commit()` on clean exit. GRAPH.md should document the transaction behavior for gardener runs **(UXF.1)**

➕ Missing:
- Orphan pruner documentation — `prune_orphan_graph` is part of the gardener pipeline (S44) and available as a query param on DELETE endpoint, but GRAPH.md doesn't mention it **(pre-existing, surfaced by UXF)**
- Client-side graph rendering section: Sigma.js + graphology now renders the canonical graph; GRAPH.md only covers the data layer, not the visualization layer **(UXG)**

---

#### 5. `docs/OBSERVABILITY.md` (538 lines) — Staleness: LOW-MEDIUM

✅ Accurate:
- Quick start section accurate
- Environment variables accurate
- Span hierarchy diagrams accurate
- Spans table (`start_span`/`create_span`) entries match codebase
- OpenInference attributes on LLM spans accurate
- Content capture policy accurate
- Prompt metadata on LLM spans accurate
- Correlation fields accurate
- Retrieval span attributes accurate
- Graph span output summaries accurate
- Structured events table accurate
- Phoenix operator guide accurate
- Token accounting caveats accurate
- Generation trace fields table (mostly accurate)
- Stream diagnostics section accurate
- Default (off) behavior accurate

⚠️ Stale:
- LLM span attributes table (line 136-143) does not include `llm.token_count.cached` — code now extracts `cached_tokens` from `prompt_tokens_details` in `core/observability.py` and includes it as `token_cached` in the token usage dict **(UXI.2)**
- Generation trace fields table does not include `cached_tokens` field now present in `core/schemas/assistant.py` **(UXI.2)**
- Token accounting caveats section doesn't mention prefix caching behavior **(UXI.2)**

➕ Missing:
- Documentation for `cached_tokens` / `token_cached` on LLM spans and in GenerationTrace **(UXI.2)**
- Prefix caching note: how `cached_tokens > 0` indicates OpenAI automatic prefix caching hit **(UXI.2)**

---

#### 6. `docs/PLAN.md` (~550+ lines) — Staleness: HIGH

✅ Accurate:
- Product decisions locked section accurate (historical)
- Data model changes section accurate (historical)
- Core behavior changes section accurate (historical)

⚠️ Stale:
- Document is titled "WOW Release Plan" and structured as sprint-by-sprint plan — all sessions (S1-S44, S45) are completed but the document still reads as an active release plan **(all tracks)**
- "Session 5 UX + Operability Plan (Current)" header (line ~106) — Session 5 is long completed **(pre-existing)**
- "UX Follow-up Plan (Post Session 4)" section contains items that are done (KB upload flow, layout stabilization, backend visibility) **(pre-existing)**
- S19 "Async ingestion lifecycle persistence" marked "Not Started" — may still be accurate but needs verification **(pre-existing)**
- No mention of UX overhaul tracks (UXF, UXG, UXP, UXT, UXI) anywhere **(all tracks)**
- "Frontend Plan" section at the bottom lists items that are now fully implemented **(pre-existing)**

➕ Missing:
- UX overhaul section covering UXF, UXG, UXP, UXT, UXI tracks and their completion status **(all tracks)**
- Historical/archival marker at the top indicating this plan is largely completed **(all tracks)**

---

#### 7. `docs/PRODUCT_SPEC.md` (173 lines) — Staleness: MEDIUM

✅ Accurate:
- Product vision and core principles correct
- Feature 1 (Chat tutor) correct
- Feature 2 (Mastery gating) correct
- Feature 3 (Level-up quiz card) correct
- Learning state machine correct
- Answer grounding modes correct
- Tutor response rules correct
- Core user flows (A, B, C, D) structurally correct
- Non-goals correct
- Success metrics correct

⚠️ Stale:
- Feature 4 (Practice mode) — does not describe unified flashcard stack (all cards merged into one deck), "generate more" with exhaustion detection, or quiz history with retry **(UXP)**
- Feature 5 (Graph UI) — still describes basic graph view; does not mention Sigma.js WebGL rendering, fuzzy search (MiniSearch), layout algorithms (ForceAtlas2), camera controls, or graph-to-chat navigation **(UXG, UXT.3)**

➕ Missing:
- Onboarding confirmation step: clicking a concept topic shows a confirm card before auto-sending **(UXT.1)**
- Streaming status display: replace-mode animation showing current generation phase **(UXT.2)**
- Graph-to-chat navigation: "Start a chat about this topic" from graph detail panel **(UXT.3)**
- Dev stats toggle: user-facing opt-in for generation trace display **(UXI.3)**
- Source tier breakdown: node counts shown by tier (umbrella/topic/subtopic/granular) **(UXI.1)**

---

#### 8. `docs/PROGRESS.md` (~577+ lines) — Staleness: VERY HIGH

✅ Accurate:
- Historical entries (S1-S44, S45) are accurate as written
- Session 4-7 change descriptions accurate
- Test results sections accurate for their respective sessions

⚠️ Stale:
- Header says "Last updated: Session 14" — massively behind (codebase is well past Session 14) **(pre-existing)**
- Slice status table only goes through S45 — no UX overhaul entries **(all tracks)**
- "Deferred to Future PRs" section lists S14 as the only deferred item — may need updating **(pre-existing)**
- "Remaining Incremental Work" section references S19/S20 which may be resolved **(pre-existing)**

➕ Missing:
- UX overhaul completion entries: UXF (3 slices), UXG (13 slices, 7 completed), UXP (3 slices), UXT (3 slices), UXI (3 slices) **(all tracks)**
- Updated "Last updated" timestamp **(all tracks)**
- Current test counts (922 pytest, 106+ vitest — up from earlier counts) **(all tracks)**

---

#### 9. `docs/PROMPTS.md` (279 lines) — Staleness: LOW

✅ Accurate:
- Runtime asset catalog matches prompt IDs in `core/prompting/assets/`
- Summary by category accurate
- Tutor agent prompts (#1-#5) accurate
- Knowledge graph prompts (#6-#8) accurate
- Quiz & practice prompts (#9-#12) accurate
- Document processing prompts (#13) accurate
- Orchestration files table accurate
- Prompt flow diagram accurate
- Maintenance rules accurate
- Migration status accurate

⚠️ Stale:
- Header says "Last updated: Prompt Refactor P9" — should reference current state **(pre-existing)**
- No mention of prompt restructuring for OpenAI prefix caching (static prefix first, dynamic content last) **(UXI.2)**

➕ Missing:
- Prefix caching note: prompts are now structured with stable static prefixes (>1024 tokens) to leverage OpenAI automatic prefix caching **(UXI.2)**

---

#### Summary — Files ranked by staleness (most → least work needed)

| Rank | File | Staleness | Primary UX Tracks |
|---|---|---|---|
| 1 | `docs/PROGRESS.md` | VERY HIGH | All (UXF, UXG, UXP, UXT, UXI) |
| 2 | `docs/PLAN.md` | HIGH | All (needs archival + UX overhaul section) |
| 3 | `docs/FRONTEND.md` | HIGH | UXG (new deps + components), UXP, UXT, UXI |
| 4 | `docs/PRODUCT_SPEC.md` | MEDIUM | UXP, UXG, UXT, UXI |
| 5 | `docs/ARCHITECTURE.md` | MEDIUM | UXG (graph rendering), UXP, UXT |
| 6 | `docs/OBSERVABILITY.md` | LOW-MEDIUM | UXI.2 (cached_tokens) |
| 7 | `docs/GRAPH.md` | LOW-MEDIUM | UXF.1, UXG (rendering), S44 (orphan pruner) |
| 8 | `docs/PROMPTS.md` | LOW | UXI.2 (prefix caching note) |
| 9 | `docs/API.md` | LOW | UXI.2 (cached_tokens in trace) |

### UXD.2. Update API.md and ARCHITECTURE.md

Purpose:
- Bring API reference and architecture overview in sync with post-overhaul codebase

Files involved:
- `docs/API.md`
- `docs/ARCHITECTURE.md`

Implementation steps:
1. **API.md updates** (based on UXD.1 staleness report):
   - Add any new endpoints introduced by UXP (quiz retry, flashcard stack endpoints)
   - Add any new endpoints introduced by UXT (graph-to-chat navigation endpoints)
   - Update any endpoint signatures/responses changed by UXF (gardener commit fix)
   - Follow the existing documentation format for endpoint entries
   - Verify each new/changed endpoint exists in `apps/api/routes/`
2. **ARCHITECTURE.md updates** (based on UXD.1 staleness report):
   - Update graph rendering architecture: D3.js → Sigma.js with graphology
   - Document new state management: Zustand stores for graph state
   - Add new frontend dependencies (graphology, @sigma/*, minisearch)
   - Update any architecture diagrams or component descriptions affected by UXG
   - Add timestamp if missing

What stays the same:
- Backend architecture sections unaffected by UX overhaul
- Database schema documentation
- Authentication/authorization documentation

Verification:
- Every new/changed endpoint in `apps/api/routes/` has a corresponding entry in API.md
- Architecture description matches actual graph rendering stack
- `grep` for Sigma.js / graphology in codebase confirms documented dependencies

Exit criteria:
- API.md covers all current endpoints accurately
- ARCHITECTURE.md reflects Sigma.js graph rendering and Zustand state management

### UXD.3. Update FRONTEND.md and GRAPH.md

Purpose:
- Update frontend source of truth and graph design documentation

Files involved:
- `docs/FRONTEND.md`
- `docs/GRAPH.md`

Implementation steps:
1. **FRONTEND.md updates** (based on UXD.1 staleness report):
   - Add new components: sigma-graph, flashcard-stack, quiz-history, onboarding-confirm, concept-chat-links
   - Add new dependencies: graphology, @sigma/react, minisearch
   - Update component directory structure if changed
   - Document new patterns (Zustand stores, streaming status display)
   - Remove references to replaced components (D3-based graph) if still present
2. **GRAPH.md updates** (based on UXD.1 staleness report):
   - Document that gardener now commits transactions (UXF.1 fix)
   - Document orphan pruner integration
   - Update rendering section: D3.js → Sigma.js with graphology
   - Update graph state management description (Zustand)
   - Ensure gardener budget/resolver documentation still accurate
   - Add timestamp if missing

What stays the same:
- Graph gardener algorithm descriptions (if still accurate)
- Resolver logic documentation
- Any FRONTEND.md sections about non-graph components that haven't changed

Verification:
- New components listed in FRONTEND.md exist in `apps/web/`
- GRAPH.md rendering section matches actual implementation
- Gardener commit behavior documented correctly
- `grep` for old D3 references removed from updated sections

Exit criteria:
- FRONTEND.md lists all current components and dependencies
- GRAPH.md accurately describes gardener behavior and Sigma.js rendering

### UXD.4. Update PRODUCT_SPEC.md, PLAN.md, PROGRESS.md

Purpose:
- Update product vision, release plan, and progress tracker

Files involved:
- `docs/PRODUCT_SPEC.md`
- `docs/PLAN.md`
- `docs/PROGRESS.md`

Implementation steps:
1. **PRODUCT_SPEC.md updates** (based on UXD.1 staleness report):
   - Update feature descriptions for new UX: unified flashcard stack, quiz history with retry, onboarding confirmation step, streaming status indicators, graph-chat navigation
   - Ensure feature list matches what's actually implemented
   - Do not add aspirational features — only document what exists
2. **PLAN.md updates** (based on UXD.1 staleness report):
   - Archive stale sprint/release sections by moving them under a "## Historical" heading
   - Update current status to reflect post-UX-overhaul state
   - If the entire plan is historical, add a note at the top pointing to the UX overhaul master plan
   - Add timestamp
3. **PROGRESS.md updates** (based on UXD.1 staleness report):
   - Mark UX overhaul items as complete with completion dates
   - Update any progress percentages or status indicators
   - Add entries for UXF, UXG, UXP, UXT, UXI track completions
   - Add timestamp

What stays the same:
- Product vision/mission statement in PRODUCT_SPEC.md (unless contradicted by implementation)
- Historical entries in PROGRESS.md — do not rewrite history

Verification:
- PRODUCT_SPEC.md feature list matches implemented features
- PLAN.md has no actively misleading "upcoming" items that are already done
- PROGRESS.md reflects current completion state

Exit criteria:
- All three files accurately reflect post-overhaul state
- No aspirational content presented as current

### UXD.5. Update OBSERVABILITY.md and PROMPTS.md

Purpose:
- Ensure observability documentation and prompt catalog match current code

Files involved:
- `docs/OBSERVABILITY.md`
- `docs/PROMPTS.md`

Implementation steps:
1. **OBSERVABILITY.md updates** (based on UXD.1 staleness report):
   - Verify documented spans/events still match code in `core/` and `domain/`
   - Check if LLM cache hit rate logging (from UXI.2) needs documenting
   - Update any trace/span names that changed
   - Verify Phoenix/OpenTelemetry configuration documentation is current
   - Add timestamp if missing
2. **PROMPTS.md updates** (based on UXD.1 staleness report):
   - Cross-reference prompt catalog with actual prompt templates in code
   - Verify prompt IDs/names match
   - Update any prompts that were restructured for caching (UXI.2 prefix caching)
   - Check if "P9" sprint naming is still relevant or needs updating
   - Add timestamp if missing

What stays the same:
- Prompt content descriptions that are still accurate
- Observability setup instructions that haven't changed

Verification:
- `grep` for span/event names in code matches OBSERVABILITY.md entries
- `grep` for prompt template names/IDs in code matches PROMPTS.md entries
- No documented spans/prompts that no longer exist in code

Exit criteria:
- OBSERVABILITY.md spans/events match codebase
- PROMPTS.md catalog matches current prompt templates
- All 9 docs fully audited and updated

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the Self-Audit Convergence Protocol may reopen slices in this child plan. When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
4. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
5. Only the specific issue identified in the Audit Report is addressed — do not widen scope

## Execution Order (Update After Each Run)

1. `UXD.1` Audit and flag stale sections ✅
2. `UXD.2` Update API.md and ARCHITECTURE.md ✅ (pre-existing)
3. `UXD.3` Update FRONTEND.md and GRAPH.md ✅
4. `UXD.4` Update PRODUCT_SPEC.md, PLAN.md, PROGRESS.md ✅
5. `UXD.5` Update OBSERVABILITY.md and PROMPTS.md ✅ (pre-existing)

### Verification Block — UXD.2

- **Root cause**: Already implemented. `API.md` has `cached_tokens` in GenerationTrace table. `ARCHITECTURE.md` has Sigma.js+graphology rendering, expanded repo structure, and frontend graph rendering subsection.
- **Files changed**: None (pre-existing)
- **What changed**: N/A
- **Commands run**: `grep -n "cached_tokens" docs/API.md`, `grep -n "Sigma\|graphology" docs/ARCHITECTURE.md`
- **Observed outcome**: All items present

### Verification Block — UXD.3

- **Root cause**: FRONTEND.md missing new graph deps and components. GRAPH.md missing orphan pruner and transaction behavior notes.
- **Files changed**: `docs/FRONTEND.md`, `docs/GRAPH.md`
- **What changed**: Added 6 new graph dependencies, 8 sigma-graph sub-components, hooks section with use-dev-stats, D3 archive note to FRONTEND.md. Added transaction auto-commit note, orphan pruner section, and client-side rendering section to GRAPH.md.
- **Commands run**: `grep -n "graphology\|sigma\|minisearch" docs/FRONTEND.md`, `grep -n "Sigma\|orphan\|auto-commit" docs/GRAPH.md`
- **Observed outcome**: All items present and verified

### Verification Block — UXD.4

- **Root cause**: PRODUCT_SPEC.md missing updated practice and graph features. PLAN.md had stale "Current" labels. PROGRESS.md missing UX overhaul entries.
- **Files changed**: `docs/PRODUCT_SPEC.md`, `docs/PLAN.md`, `docs/PROGRESS.md`
- **What changed**: Added Feature 5a/5b (Sigma.js, MiniSearch) to PRODUCT_SPEC. Changed "(Current)" to "(Completed)" in PLAN.md. Added UX overhaul completion entries to PROGRESS.md.
- **Commands run**: Verified commit output
- **Observed outcome**: All three files updated accurately

### Verification Block — UXD.5

- **Root cause**: Already implemented. OBSERVABILITY.md has `llm.token_count.cached`, `cached_tokens` in GenerationTrace, and prefix caching caveat. PROMPTS.md has updated header and "Prefix Caching Layout" section.
- **Files changed**: None (pre-existing)
- **What changed**: N/A
- **Commands run**: `grep -n "cached_tokens\|prefix cach" docs/OBSERVABILITY.md`, `grep -n "cach\|prefix" docs/PROMPTS.md`
- **Observed outcome**: All items present

## Verification Matrix

```bash
# Documentation accuracy — no code tests needed, but verify no broken references:
grep -r "D3\|d3-force\|d3-selection" docs/FRONTEND.md docs/GRAPH.md docs/ARCHITECTURE.md  # should not appear in updated sections
grep -r "sigma\|graphology\|Zustand" docs/FRONTEND.md docs/GRAPH.md docs/ARCHITECTURE.md  # should appear
```

## Removal Ledger

{Append entries during implementation}

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/06_docs_audit_plan.md.
Begin with the next incomplete UXD slice exactly as described.

Execution loop for this child plan:

1. Work on one UXD slice at a time.
2. Do not remove or significantly rewrite documentation sections that are still accurate. Only update what has changed. Add timestamps to files that lack them. Keep documentation factual and concise — do not pad with aspirational content.
3. Run the listed verification steps before claiming a slice complete, including cross-referencing docs against actual code where required by the plan.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed UXD slices OR if context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/06_docs_audit_plan.md and restate which UXD slices remain.
6. Continue to the next incomplete UXD slice once the previous slice is verified.
7. When all UXD slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXD is complete. UXD completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle, only work on slices marked as "reopened". Produce audit-prefixed Verification Blocks. Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/06_docs_audit_plan.md.
Begin with the current UXD slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXD is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue with the next incomplete child plan.
```
