# Observability Plan Snapshot Before Phoenix Scope Update

Date: 2026-03-01

This snapshot captures the first observability refactor plan before the Phoenix scope review.

## Outdated assumptions found after partial implementation

- The original plan treated `http.request` root spans as a net improvement.
- Current Phoenix feedback shows those spans create noise, appear with `unknown` kind, and make non-AI endpoints dominate the UI.
- The original plan did not explicitly define a Phoenix export allowlist for AI spans only.
- The original plan mentioned retrieval visibility, but it did not explicitly require separate visibility for:
  - vector retrieval hits
  - FTS hits
  - hybrid fusion
  - graph-derived retrieval or provenance-based bias/context
- The original plan did not require a test that exported Phoenix spans never show `unknown` kind for AI paths.

## Current repo state motivating the update

- `apps/api/middleware.py` now emits `http.request` spans to Phoenix.
- `domain/chat/retrieval_context.py` now emits a coarse `retrieval.hybrid` span.
- `adapters/llm/providers.py` now emits streaming LLM spans and usage-source metadata.
- These changes are directionally useful, but they still do not match the desired Phoenix product surface.
