# Codex Rules For CoLearni

## General Rules

- Make small PR-sized changes; target 400 net LOC or less. Split larger work into phases.
- Prefer implementation compatible with the existing repo structure.
- Do not rewrite unrelated parts of the app.
- Update docs when architecture changes.
- Add tests for every core behavior.
- Do not claim completion without running checks.
- If checks cannot run, document why.
- Respect dirty worktrees; do not revert changes you did not make.

## Architecture Rules

- Keep FastAPI routes thin.
- Put business logic in services. If domain modules are later introduced, keep them separate from HTTP routes.
- Keep LLM prompts isolated, versioned, and testable.
- Keep source provenance explicit.
- Never mix public Trail Pack content with private workspace content.
- Do not add multi-agent complexity unless needed.
- Preserve evidence-first behavior: user-visible sourced answers must cite allowed evidence or refuse in strict grounded mode.
- Obey graph resolver and gardener budgets in `docs/GRAPH.md`; no unbounded loops.

## Product Rules

- CoLearni is a learning workspace, not a generic RAG chatbot.
- Treat Workspace, Trail, Trail Pack, Source Manifest, Research Trace, Hydration, and Mastery as stable product terms.
- The graph and mastery model are core primitives.
- Concept graph nodes must carry explicit levels: `umbrella`, `topic`, `subtopic`, or `granular`.
- The tutor should feel like a mentor/coach, not a search engine.
- Trail Pack export/import is a core product identity; do not move safe sharing behind dashboard polish, ingestion, retrieval, provider tools, or SaaS work.
- Provider-native tool foundations should be small, direct-provider adapters, not a large agent-framework rewrite.
- Build local-ready first and keep SaaS as a later thin layer.
- Do not prioritise PDF ingestion, SaaS billing/auth, or a public marketplace over core product loop quality.
- Do not make raw filesystem browsing the primary retrieval architecture.

## Safety Rules

- Never include user-uploaded content in public exports.
- Never include chunks or embeddings in public exports.
- Never include private notes or chat history in public exports.
- Never include mastery records in public exports by default.
- Never include generated summaries from private/user-uploaded sources in public exports.
- Never include generated quizzes from private/user-uploaded sources in public exports.
- Public research-agent sources may export links and metadata only by default.
- Unknown license means no redistribution of content.
- Public access is not the same as redistribution rights.

## Testing Expectations

- Backend behavior needs pytest coverage.
- Frontend behavior should use the repo's existing typecheck/test tooling.
- Export/import safety behavior requires regression tests.
- LLM-facing code should test prompt context assembly and schema validation without requiring live provider calls where possible.
- Manual checks are acceptable only as a supplement, not as a replacement for core safety tests.

## Verification Block

Every implementation PR should include:

```md
## Verification

Root cause / task:
Files changed:
Tests added:
Commands run:
Manual checks:
Known limitations:
```
