# Archived Docs

Historical planning artifacts kept for provenance only. They are **not** current
source of truth and should not be used to drive new work. For current state see
`docs/CURRENT_VARIANT.md` (authoritative implementation overlay), `docs/REBUILD_PLAN.md`,
and the domain docs under `docs/`.

| File | Why archived |
|---|---|
| `PHASE_2_HANDOFF.md` | Early rebuild handoff (references the old `rebuild` branch and Phase 1/2 state). Superseded. |
| `CONSOLIDATION_PLAN.md` | Phase 10–12 gap-closing plan. All three items are complete and merged into the mainline phases. Some internal assumptions (e.g. parallel `asyncio.gather` tool dispatch) were later reversed to sequential shared-session dispatch. |
| `CONSOLIDATION_PROMPT_1.md` | One-off implementation prompt for Consolidation Item 1 (frontend `/next`). Complete. |
| `CONSOLIDATION_PROMPT_2.md` | One-off implementation prompt for Consolidation Item 2 (parser pipeline). Complete. |
| `CONSOLIDATION_PROMPT_3.md` | One-off implementation prompt for Consolidation Item 3 (retrieval tool loop). Complete. |
| `CLAUDE_CHAT_CONTEXT.md` | Dated working snapshot. Contradicts current state on marketing/summarization. |
