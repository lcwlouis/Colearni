# Next Session Kickoff Prompt

Use this prompt in a fresh Copilot chat to continue exactly where Session 6 ended.

---

You are continuing work on the ColearniCodex repo for the WOW release.

## Critical Context

- Workspace root: `/Users/louisliu/Projects/Personal/ColearniCodex`
- Read first:
  - `AGENTS.md`
  - `docs/CODEX.md`
  - `docs/ARCHITECTURE.md`
  - `docs/PRODUCT_SPEC.md`
  - `docs/GRAPH.md`
- Progress source of truth:
  - `docs/WOW_PROGRESS.md`
  - `docs/PLAN.md`

## Completed Through Session 6

- S1–S13 complete.
- S14 (Eval suite) intentionally deferred.
- New slices added:
  - S15 done: KB ingestion + graph status in list UI.
  - S16 done: KB upload/confirm UX (no browser popups).
  - S17 done: top-right control layout stabilized by moving workspace/theme/logout into tutor sidebar bottom.
  - S18 done: env-configurable graph LLM temperatures.
  - S19 not started (verified): persisted ingestion lifecycle + true async reprocess worker still pending.
  - S20 not started: graph ingestion SDK migration + structured output schema hardening.
  - S21 done: KB live upload queue + multi-file uploads.

## What Was Implemented in Session 5

### KB UX + Status

- `apps/web/app/kb/page.tsx`
  - Explicit `Choose file` then `Upload document` flow.
  - Inline confirmations for reprocess/delete (no `window.confirm` / `alert`).
  - Status/info banners after actions.
  - Table now displays ingestion and graph statuses.

- `apps/api/routes/knowledge_base.py`
  - `GET /workspaces/{ws_id}/knowledge-base/documents` now returns:
    - `ingestion_status`
    - `graph_status`
    - `graph_concept_count`

- `core/schemas.py`
  - `KBDocumentSummary` includes new status fields.

- `apps/web/lib/api/types.ts`
  - Frontend type updated for new KB status fields.

- `docs/API.md`
  - KB response docs updated for new fields.

### Layout Adjustments

- `apps/web/components/app-nav.tsx`
  - Top nav now only route links.

- `apps/web/app/layout.tsx`
  - Removed top-right theme toggle.

- `apps/web/app/tutor/page.tsx`
  - Added bottom sidebar controls for workspace selector, theme toggle, logout.

- `apps/web/app/globals.css`
  - Added styling for sidebar footer and KB page/table/status badges.

### Model Temperature Config

- `core/settings.py`
  - Added:
    - `graph_llm_json_temperature`
    - `graph_llm_tutor_temperature`

- `adapters/llm/factory.py`
  - Wires both temperatures into provider constructors.

- `adapters/llm/providers.py`
  - Uses `json_temperature` for structured JSON calls.
  - Uses `tutor_temperature` for tutor text calls.
  - Constructor defaults retained for backward compatibility.

- `.env.example`
  - Added:
    - `APP_GRAPH_LLM_JSON_TEMPERATURE=0`
    - `APP_GRAPH_LLM_TUTOR_TEMPERATURE=0`

- `tests/adapters/test_graph_llm_observability.py`
  - Added test verifying case-specific temperatures are sent.

## What Was Implemented in Session 6

### KB Upload UX: Live Progress + Multi-file Batch

- `apps/web/app/kb/page.tsx`
  - File picker now supports selecting multiple files.
  - Upload flow now processes selected files in one batch (sequentially).
  - Added in-page upload queue showing per-file status:
    - `queued`
    - `uploading`
    - `uploaded`
    - `failed`

- `apps/web/lib/kb/upload-queue.ts`
  - Added queue reducer + helpers for deterministic upload tracking.

- `apps/web/lib/kb/upload-queue.test.ts`
  - Added unit tests for queue lifecycle and seed generation.

- `apps/web/app/globals.css`
  - Added upload queue and failed-badge styling.

### Plan/Progress Corrections

- `docs/WOW_PROGRESS.md`
  - Corrected S19 from `In Progress` to `Not Started` after code verification.
  - Added S20/S21 rows and Session 6 validation notes.

- `docs/PLAN.md`
  - Added Session 6 reliability scope with graph SDK migration + schema debugging/fix steps.

## Validation Already Run

- Backend focused tests pass:
  - `tests/adapters/test_graph_llm_factory.py`
  - `tests/adapters/test_graph_llm_observability.py`
  - `tests/api/test_api_docs_sync.py`
  - `tests/api/test_documents_upload.py`
- Frontend:
  - `npx tsc --noEmit` passes.
  - `npx vitest run` passes (41 tests).

## Active Blocking Issue (Needs Fix Next)

- With `APP_INGEST_BUILD_GRAPH=true`, KB upload can fail with:
  - `RuntimeError: Graph LLM request failed with status 400`
  - OpenAI error: `Invalid schema for response_format 'graph_raw_extraction': ... array schema missing items.`
- Failure originates in `adapters/llm/providers.py` structured-output request path used by graph extraction.
- Current graph adapter path still uses hand-rolled HTTP (`urllib`) instead of SDK-backed client.

## Known Pre-existing Issue

- `tests/core/test_settings.py::test_settings_reads_observability_aliases` can fail due to local env `OTEL_EXPORTER_OTLP_ENDPOINT` leakage (`http://localhost:6006` vs expected value). Treat as pre-existing unless explicitly fixing env precedence policy.

## Main Objective for Next Session (S20 then S19)

Stabilize graph ingestion first (SDK migration + schema fix), then continue lifecycle persistence work.

### Required outcomes

1. Reproduce and pin the graph extraction schema failure in automated tests.
   - Add a regression test around graph structured output request payload validation.
2. Migrate graph LLM providers to SDK-backed implementations.
   - OpenAI provider: official OpenAI Python SDK.
   - LiteLLM provider: SDK path instead of raw OpenAI-compatible HTTP request.
3. Fix strict schema contract used by graph extraction/disambiguation.
   - Ensure all array/object fields satisfy strict JSON schema requirements.
4. Ensure graph ingestion errors are surfaced as controlled API errors (no raw 500 traceback leaks).
5. Re-run ingestion with graph enabled via KB upload and confirm extraction completes.
6. Continue S19 after S20:
   - Persist document lifecycle states (`queued`/`processing`/`ingested`/`failed`).
   - Implement real async reprocess worker path.
7. Keep API routes thin, maintain graph/resolver budgets, and add tests for all new behavior.

## Suggested First Steps

1. Add failing adapter-level tests for graph structured output schema requests.
2. Implement SDK-backed graph clients behind existing `GraphLLMClient` interface.
3. Update/fix schema payload definitions and re-run ingestion tests.
4. Add route-level handling for graph provider failures so upload returns stable API error status.
5. After S20 stabilizes, resume S19 lifecycle persistence slice.

## Commands to Re-validate

From repo root:

- ` .venv/bin/python -m pytest tests/adapters/test_graph_llm_factory.py tests/adapters/test_graph_llm_observability.py tests/domain/test_graph_extraction.py tests/core/test_ingestion_embeddings.py tests/api/test_documents_upload.py -q --tb=short`
- ` .venv/bin/python -m pytest tests/ -q --tb=short --deselect tests/core/test_settings.py::test_settings_reads_observability_aliases`

From `apps/web`:

- `npx tsc --noEmit`
- `npx vitest run`

## Guardrails

- Keep PR-size mindset (`<= 400 LOC net` per slice where practical).
- Don’t add browser popups for confirmations.
- Don’t regress top-right header wrapping behavior.
- Don’t change unrelated APIs.
- Don’t commit; just implement and validate.

---

If anything is ambiguous, prefer the simplest implementation aligned with the current docs and existing design system.
