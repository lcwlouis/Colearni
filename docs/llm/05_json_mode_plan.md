# L5 — JSON Mode Standardization

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Track ID: `L5`
Status: ✅ done

## Purpose

Switch all structured output paths to use LiteLLM's native `response_format` parameter
with proper Pydantic models, runtime model support checks, and client-side validation.

## Current State

- JSON mode: `complete_messages_json()` has a 3-level fallback chain
  (json_schema → json_object+hint → prompt-only) — already robust
- Schema format: All schemas are raw dicts (`_RAW_GRAPH_SCHEMA`, etc.)
- Model support detection: Hardcoded provider/model-name heuristics
- Manual parsing: `json.loads()` on LLM text + manual dict validation
- Quiz grading: No Pydantic model, manual dict parsing
- Query analysis: Uses dataclass, not Pydantic
- Client-side validation: Not enabled

## Slice Status

| Slice | Description | Status |
|-------|-------------|--------|
| L5.1 | Define Pydantic response models for all JSON schemas | ✅ done |
| L5.2 | Add `response_format=PydanticModel` support to `complete_messages_json()` | ✅ done — returns Pydantic instance when `response_model` provided, dict otherwise |
| L5.3 | Enable `litellm.enable_json_schema_validation` for client-side validation | ✅ done |
| L5.4 | Migrate call sites to Pydantic models, remove manual parsing | ✅ done — all call sites use `response_model=PydanticModel` with `.model_dump()` for backward compat |
| L5.5 | Add runtime model support checks via `supports_response_schema()` | ✅ done |

## Slice Definitions

### L5.1 — Define Pydantic response models for all JSON schemas

**Purpose**: Create proper Pydantic models for every JSON schema used in LLM calls.

**Implementation Steps**:
1. Create `core/llm_schemas.py` with Pydantic models:
   - `RawGraphResponse` — mirrors `_RAW_GRAPH_SCHEMA` (concepts + edges)
   - `DisambiguationResponse` — mirrors `_DISAMBIGUATION_SCHEMA`
   - `DisambiguationBatchResponse` — mirrors `_DISAMBIGUATION_BATCH_SCHEMA`
   - `QueryAnalysisResponse` — mirrors `_QUERY_ANALYSIS_SCHEMA` from query_analyzer
   - `QuizGradingResponse` — mirrors the expected quiz grading output
2. Each model should have `model_json_schema()` that matches the existing dict schemas
3. Add tests verifying schema compatibility

**Exit Criteria**:
- All 5 Pydantic models exist in `core/llm_schemas.py`
- `model_json_schema()` produces schemas compatible with existing dict schemas
- Tests pass

### L5.2 — Add `response_format=PydanticModel` support

**Purpose**: Allow `complete_messages_json()` to accept a Pydantic model class.

**Implementation Steps**:
1. Add overloaded signature: `complete_messages_json(messages, *, response_model=None, schema_name=None, schema=None)`
2. When `response_model` is provided, generate schema from `response_model.model_json_schema()`
3. After JSON parsing, validate with `response_model.model_validate(data)` for type safety
4. Return the validated Pydantic instance (or dict for backward compat)
5. Keep existing dict-schema path unchanged

**Exit Criteria**:
- `complete_messages_json()` accepts `response_model` parameter
- Pydantic validation applied when model provided
- Existing dict-schema callers unchanged
- Tests pass

### L5.3 — Enable `litellm.enable_json_schema_validation`

**Purpose**: Enable LiteLLM's client-side JSON schema validation as a safety net.

**Implementation Steps**:
1. In app startup (or LiteLLM client init), set `litellm.enable_json_schema_validation = True`
2. Add a settings toggle: `llm_json_schema_validation: bool = True`
3. Test that validation is enabled

**Exit Criteria**:
- Setting exists and defaults to True
- LiteLLM validation enabled on startup
- Tests pass

### L5.4 — Migrate call sites to Pydantic models

**Purpose**: Replace manual JSON parsing with Pydantic model validation at call sites.

**Implementation Steps**:
1. Update `query_analyzer.py` to use `QueryAnalysisResponse` model
2. Update `quiz_grading.py` to use `QuizGradingResponse` model
3. Update graph extraction call sites to use `RawGraphResponse`
4. Remove manual `json.loads()` + dict validation where Pydantic handles it

**Exit Criteria**:
- All call sites use Pydantic models
- Manual parsing removed or reduced
- Tests pass

### L5.5 — Add runtime model support checks

**Purpose**: Replace hardcoded model-name heuristics with LiteLLM runtime checks.

**Implementation Steps**:
1. Replace `_model_supports_json_schema()` with `litellm.supports_response_schema(model, ...)`
2. Keep hardcoded check as fallback if litellm check is unavailable
3. Test runtime check integration

**Exit Criteria**:
- Runtime model support check used
- Fallback to heuristic if litellm check unavailable
- Tests pass

## Verification Blocks

(Populated as slices are completed)

## Removal Ledger

(Populated as code is removed/replaced)

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/llm/05_json_mode_plan.md. Begin with the current incomplete slice.
Follow the execution loop in docs/llm/LLM_MASTER_PLAN.md.
```
