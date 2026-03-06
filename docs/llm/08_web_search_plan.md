# L8 — Web Search Integration Plan

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Track: L8 Web Search
Depends on: L4 ✅ (Tool Framework)

## Problem

The tutor currently answers from workspace documents only. Exploratory questions
about topics not covered by uploaded material produce thin or refused answers.
Web search would let the system cite current external sources.

## Approach

Implement web search as a Tool (L4 protocol) backed by Tavily API via httpx.
Wire it into the query analyzer so `explore` intent enables the tool.
Format results as `EvidenceItem(source_type=WEB)`.

## Slices

### L8.1 — Web search tool definition

**Files changed:**
- `core/schemas/assistant.py` — add `WEB = "web"` to `EvidenceSourceType`, relax
  workspace-only validation for web type
- `domain/tools/web_search.py` — `WebSearchTool` implementing `Tool` protocol
- `core/settings.py` — add `web_search_api_key`, `web_search_max_results` settings
- `tests/domain/test_web_search_tool.py` — tests

Status: 🔄 pending

### L8.2 — Register in tool registry

**Files changed:**
- `domain/tools/registry_factory.py` — register `WebSearchTool` when API key present
- `tests/domain/test_builtin_tools.py` — update registry tests

Status: 🔄 pending

### L8.3 — Query analyzer routing

**Files changed:**
- `domain/chat/query_analyzer.py` — add `needs_web_search: bool` to `QueryAnalysis`
  (True when intent == "explore")
- `core/llm_schemas.py` — add `needs_web_search` to `QueryAnalysisResponse`
- `tests/domain/test_query_analyzer.py` — tests

Status: 🔄 pending

### L8.4 — Evidence formatting

**Files changed:**
- `domain/tools/web_search.py` — add `format_as_evidence()` returning `list[EvidenceItem]`
- Tests

Status: 🔄 pending

## Verification Matrix

| Check | Command |
|-------|---------|
| New tests pass | `.venv/bin/python -m pytest tests/domain/test_web_search_tool.py -v` |
| Existing tool tests | `.venv/bin/python -m pytest tests/domain/test_builtin_tools.py tests/core/test_tool_framework.py -v` |
| Full suite no regressions | `.venv/bin/python -m pytest tests/ --ignore=tests/db -q` |

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```
Read docs/llm/LLM_MASTER_PLAN.md and docs/llm/08_web_search_plan.md.
Begin with slice L8.1. Implement exactly the changes listed. Run verification.
Continue to L8.2, then L8.3, then L8.4.
```
