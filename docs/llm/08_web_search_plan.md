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
- `tests/domain/test_web_search_tool.py` — 11 tests

Status: ✅ done

**Verification Block:**
- 11 tests pass (`test_web_search_tool.py`)
- EvidenceSourceType.WEB validates correctly
- Tavily API called via httpx with auth header
- Commit: `feat(L8.1): add WebSearchTool and WEB evidence type`

### L8.2 — Register in tool registry

**Files changed:**
- `domain/tools/registry_factory.py` — register `WebSearchTool` when API key present
- `tests/domain/test_builtin_tools.py` — 2 new registry tests

Status: ✅ done

**Verification Block:**
- 17 tests pass (`test_builtin_tools.py`)
- WebSearchTool registered only when `web_search_api_key` provided
- Commit: `feat(L8.2): register WebSearchTool in tool registry factory`

### L8.3 — Query analyzer routing

**Files changed:**
- `domain/chat/query_analyzer.py` — add `needs_web_search: bool` to `QueryAnalysis`
  (True when intent == "explore")
- `tests/domain/test_query_analyzer.py` — 4 new tests

Status: ✅ done

**Verification Block:**
- 32 tests pass (`test_query_analyzer.py`)
- needs_web_search derived from intent == "explore"
- Commit: `feat(L8.3): add needs_web_search routing to query analyzer`

### L8.4 — Evidence formatting

**Files changed:**
- `domain/tools/web_search.py` — `format_as_evidence()` (implemented in L8.1)
- Tests (4 format_as_evidence tests in `test_web_search_tool.py`)

Status: ✅ done (pre-completed in L8.1)

**Verification Block:**
- format_as_evidence tests pass (4 tests in test_web_search_tool.py)
- Returns list[EvidenceItem] with source_type=WEB
- No separate commit needed — code landed in L8.1

## Verification Matrix

| Check | Command | Result |
|-------|---------|--------|
| New tests pass | `.venv/bin/python -m pytest tests/domain/test_web_search_tool.py -v` | ✅ 11 passed |
| Existing tool tests | `.venv/bin/python -m pytest tests/domain/test_builtin_tools.py tests/core/test_tool_framework.py -v` | ✅ all passed |
| Query analyzer tests | `.venv/bin/python -m pytest tests/domain/test_query_analyzer.py -v` | ✅ 32 passed |
| Full suite no regressions | `.venv/bin/python -m pytest tests/ --ignore=tests/db -q` | ✅ |
