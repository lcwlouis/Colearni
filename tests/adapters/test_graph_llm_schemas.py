"""Regression tests for graph LLM JSON schema strict-mode compliance."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from adapters.llm.providers import (
    LiteLLMGraphLLMClient,
    _DISAMBIGUATION_SCHEMA,
    _RAW_GRAPH_SCHEMA,
)


# ── Schema structure validators ──────────────────────────────────────


def _assert_strict_schema(schema: dict[str, object], path: str = "") -> None:
    """Recursively validate OpenAI strict-mode requirements on a JSON schema."""
    obj_type = schema.get("type")

    if obj_type == "object":
        props = schema.get("properties")
        assert isinstance(props, dict), f"{path}: object schema must have 'properties'"
        required = schema.get("required")
        assert isinstance(required, list), f"{path}: object schema must have 'required'"
        assert set(required) == set(props.keys()), (
            f"{path}: 'required' must list all property keys; "
            f"missing={set(props.keys()) - set(required)}, extra={set(required) - set(props.keys())}"
        )
        assert schema.get("additionalProperties") is False, (
            f"{path}: object schema must have 'additionalProperties': false"
        )
        for prop_name, prop_schema in props.items():
            assert isinstance(prop_schema, dict), f"{path}.{prop_name}: property must be a dict"
            _assert_strict_schema(prop_schema, path=f"{path}.{prop_name}")

    elif obj_type == "array":
        items = schema.get("items")
        assert items is not None, f"{path}: array schema must have 'items'"
        assert isinstance(items, dict), f"{path}: array 'items' must be a dict"
        _assert_strict_schema(items, path=f"{path}[items]")


# ── Schema compliance tests ──────────────────────────────────────────


def test_raw_graph_schema_is_strict_compatible() -> None:
    """_RAW_GRAPH_SCHEMA must satisfy OpenAI strict JSON schema rules."""
    _assert_strict_schema(_RAW_GRAPH_SCHEMA, path="RAW_GRAPH_SCHEMA")


def test_disambiguation_schema_is_strict_compatible() -> None:
    """_DISAMBIGUATION_SCHEMA must satisfy OpenAI strict JSON schema rules."""
    _assert_strict_schema(_DISAMBIGUATION_SCHEMA, path="DISAMBIGUATION_SCHEMA")


def test_raw_graph_schema_concept_items_match_domain_fields() -> None:
    """Concept items in the schema must include name, context_snippet, description, tier."""
    concept_items = _RAW_GRAPH_SCHEMA["properties"]["concepts"]["items"]  # type: ignore[index]
    assert "name" in concept_items["properties"]
    assert "context_snippet" in concept_items["properties"]
    assert "description" in concept_items["properties"]
    assert "tier" in concept_items["properties"], (
        "tier must be in the JSON schema so OpenAI strict mode allows the LLM to return it"
    )


def test_raw_graph_schema_edge_items_match_domain_fields() -> None:
    """Edge items in the schema must include all expected fields."""
    edge_items = _RAW_GRAPH_SCHEMA["properties"]["edges"]["items"]  # type: ignore[index]
    expected = {"src_name", "tgt_name", "relation_type", "description", "keywords", "weight"}
    assert set(edge_items["properties"].keys()) == expected


# ── Payload round-trip tests ─────────────────────────────────────────


def _make_sdk_response(content: str) -> Any:
    """Build a litellm-style ModelResponse mock that supports .model_dump()."""
    return SimpleNamespace(
        model_dump=lambda: {"choices": [{"message": {"content": content}}]}
    )


def test_extract_raw_graph_sends_schema_with_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """extract_raw_graph must send a schema with items for arrays."""
    captured: list[dict[str, Any]] = []

    def _capture(**kwargs: Any) -> Any:
        captured.append(kwargs)
        return _make_sdk_response('{"concepts": [], "edges": []}')

    monkeypatch.setattr("litellm.completion", _capture)
    client = LiteLLMGraphLLMClient(
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="http://localhost:4000/v1",
    )
    _ = client.extract_raw_graph(chunk_text="Test chunk")

    assert len(captured) == 1
    schema = captured[0]["response_format"]["json_schema"]["schema"]
    assert "items" in schema["properties"]["concepts"]
    assert "items" in schema["properties"]["edges"]


def test_disambiguate_sends_schema_with_all_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """disambiguate must send a schema where all properties are required."""
    captured: list[dict[str, Any]] = []

    def _capture(**kwargs: Any) -> Any:
        captured.append(kwargs)
        return _make_sdk_response(
            json.dumps(
                {
                    "decision": "CREATE_NEW",
                    "confidence": 0.9,
                    "merge_into_id": None,
                    "alias_to_add": None,
                    "proposed_description": "A concept",
                }
            )
        )

    monkeypatch.setattr("litellm.completion", _capture)
    client = LiteLLMGraphLLMClient(
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="http://localhost:4000/v1",
    )
    _ = client.disambiguate(
        raw_name="Vector Space",
        context_snippet="A vector space is a set with operations.",
        candidates=[],
    )

    assert len(captured) == 1
    schema = captured[0]["response_format"]["json_schema"]["schema"]
    props = set(schema["properties"].keys())
    required = set(schema.get("required", []))
    # All fields that are always needed must be required
    assert {"decision", "confidence"} <= required
    # Required fields must be a subset of declared properties
    assert required <= props
