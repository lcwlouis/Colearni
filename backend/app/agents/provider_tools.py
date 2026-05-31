"""Provider-tool schemas and cross-provider normalization helpers.

This module is intentionally small. It defines CoLearni's internal tool shape,
provider wire-format adapters, and safe public previews. It does not execute
tools or run an autonomous loop; services own execution and budgets.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

ToolStreamKind = Literal["text", "thinking", "tool_call", "tool_result", "done"]

_TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class ToolArgumentValidationError(ValueError):
    """Raised when provider tool arguments do not match a registered schema."""


@dataclass(frozen=True)
class ProviderToolDefinition:
    """Provider-agnostic tool definition.

    ``parameters`` is a deliberately small JSON-Schema object. The current
    validator supports object schemas, required fields, primitive types, enums,
    arrays, and ``additionalProperties: false``.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    public_argument_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _TOOL_NAME_RE.match(self.name):
            raise ValueError(f"Invalid tool name: {self.name!r}")
        if self.parameters.get("type") != "object":
            raise ValueError("Tool parameters must be a JSON object schema")

    def validate_arguments(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        return validate_tool_arguments(self, arguments)


@dataclass(frozen=True)
class NormalizedToolCall:
    """Provider-native tool call normalized to one internal shape."""

    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str | dict[str, Any] | None = None
    provider: str = ""
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.validation_error is None


@dataclass(frozen=True)
class NormalizedToolResult:
    """Service-produced or provider-returned tool result in one internal shape."""

    call_id: str
    name: str
    content: str
    provider: str = ""
    is_error: bool = False
    public_preview: dict[str, Any] = field(default_factory=dict)

    def preview_json(self) -> str:
        return json.dumps(self.public_preview or {"status": "received"})


@dataclass(frozen=True)
class NormalizedStreamEvent:
    """A normalized stream event from a provider or fake provider."""

    kind: ToolStreamKind
    text: str | None = None
    tool_call: NormalizedToolCall | None = None
    tool_result: NormalizedToolResult | None = None

    @classmethod
    def text_delta(cls, text: str) -> NormalizedStreamEvent:
        return cls(kind="text", text=text)

    @classmethod
    def thinking_delta(cls, text: str) -> NormalizedStreamEvent:
        return cls(kind="thinking", text=text)

    @classmethod
    def tool_call_event(cls, call: NormalizedToolCall) -> NormalizedStreamEvent:
        return cls(kind="tool_call", tool_call=call)

    @classmethod
    def tool_result_event(cls, result: NormalizedToolResult) -> NormalizedStreamEvent:
        return cls(kind="tool_result", tool_result=result)

    @classmethod
    def done_event(cls) -> NormalizedStreamEvent:
        return cls(kind="done")


@dataclass
class AnthropicStreamState:
    """Accumulator for Anthropic streamed tool-use input_json_delta chunks."""

    tool_blocks: dict[int, dict[str, Any]] = field(default_factory=dict)


def validate_tool_arguments(
    definition: ProviderToolDefinition,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate arguments against the definition's supported JSON-Schema subset."""
    if not isinstance(arguments, Mapping):
        raise ToolArgumentValidationError("Tool arguments must be a JSON object")
    _validate_object_schema(definition.parameters, dict(arguments), path="arguments")
    return dict(arguments)


def normalize_tool_call(
    *,
    call_id: str,
    name: str,
    raw_arguments: str | Mapping[str, Any] | None,
    provider: str,
    definition: ProviderToolDefinition | None = None,
) -> NormalizedToolCall:
    """Parse and validate a tool call without throwing raw provider errors."""
    arguments: dict[str, Any] = {}
    validation_error: str | None = None
    try:
        arguments = _parse_tool_arguments(raw_arguments)
        if definition is not None:
            arguments = definition.validate_arguments(arguments)
    except ToolArgumentValidationError as exc:
        validation_error = str(exc)

    return NormalizedToolCall(
        call_id=call_id or name,
        name=name,
        arguments=arguments,
        raw_arguments=dict(raw_arguments) if isinstance(raw_arguments, Mapping) else raw_arguments,
        provider=provider,
        validation_error=validation_error,
    )


_TEXT_TOOL_CALL_RE = re.compile(
    r"<\s*(?:function[_\s]?call|tool[_\s]?call|tool[_\s]?use)\s*>(.*?)"
    r"<\s*/\s*(?:function[_\s]?call|tool[_\s]?call|tool[_\s]?use)\s*>",
    re.DOTALL | re.IGNORECASE,
)
# Tolerate an UNCLOSED opening tag (model truncated before emitting the close).
_TEXT_TOOL_CALL_OPEN_RE = re.compile(
    r"<\s*(?:function[_\s]?call|tool[_\s]?call|tool[_\s]?use)\s*>(.*)\Z",
    re.DOTALL | re.IGNORECASE,
)


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Return the first balanced top-level JSON object in *text*, or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def parse_text_tool_calls(
    text: str,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
    *,
    provider: str = "text",
) -> list[NormalizedToolCall]:
    """Recover tool calls a model emitted as TEXT instead of native tool calls.

    Small/local models (e.g. deepseek-v4-flash) sometimes ignore the native
    tool-call channel and instead print a ``<functioncall>{...}</functioncall>``
    block (or a bare ``{"name": ..., "arguments": {...}}`` object) directly in the
    text. Without this recovery the call leaks to the learner as raw text and the
    intended action (retrieval, suggest_quiz, suggest_artifact) never fires.

    Only calls whose ``name`` matches a provided definition are returned, each
    validated against that definition (invalid ones carry a ``validation_error``
    so callers can drop them).
    """
    if not text:
        return []
    blobs: list[str] = [m.group(1) for m in _TEXT_TOOL_CALL_RE.finditer(text)]
    if not blobs:
        open_match = _TEXT_TOOL_CALL_OPEN_RE.search(text)
        if open_match is not None:
            blobs.append(open_match.group(1))
    if not blobs:
        stripped = text.strip()
        # Bare JSON object with no wrapping tags: only treat as a call when it
        # advertises a name (and, below, the name matches a known tool).
        if stripped.startswith("{") and '"name"' in stripped:
            blobs.append(stripped)
    calls: list[NormalizedToolCall] = []
    for idx, blob in enumerate(blobs):
        obj = _first_json_object(blob)
        if obj is None:
            continue
        name = obj.get("name")
        if not isinstance(name, str):
            continue
        definition = _definition_for(definitions, name)
        if definition is None:
            continue
        raw_args = obj.get("arguments")
        if raw_args is None:
            raw_args = obj.get("parameters", {})
        calls.append(
            normalize_tool_call(
                call_id=f"text_{idx}_{name}",
                name=name,
                raw_arguments=raw_args,
                provider=provider,
                definition=definition,
            )
        )
    return calls


def strip_text_tool_calls(text: str) -> str:
    """Remove textual tool-call blocks so they never leak to the learner."""
    if not text:
        return text
    cleaned = _TEXT_TOOL_CALL_RE.sub("", text)
    cleaned = _TEXT_TOOL_CALL_OPEN_RE.sub("", cleaned)
    return cleaned.strip()


def safe_public_tool_call_preview(
    call: NormalizedToolCall,
    definition: ProviderToolDefinition | None = None,
) -> dict[str, Any]:
    """Return a learner-safe tool-call preview with only whitelisted arguments."""
    preview: dict[str, Any] = {"name": call.name}
    if call.validation_error is not None:
        preview["status"] = "invalid_arguments"
        return preview
    fields = definition.public_argument_fields if definition is not None else ()
    for field_name in fields:
        if field_name in call.arguments:
            preview[field_name] = call.arguments[field_name]
    return preview


def safe_public_tool_result_preview(
    result: NormalizedToolResult,
) -> dict[str, Any]:
    """Return a learner-safe tool-result preview, never raw result content."""
    if result.public_preview:
        return dict(result.public_preview)
    return {"status": "error" if result.is_error else "received"}


def openai_responses_tool_definitions(
    tools: Sequence[ProviderToolDefinition],
) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


def openai_chat_tool_definitions(
    tools: Sequence[ProviderToolDefinition],
) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def anthropic_tool_definitions(
    tools: Sequence[ProviderToolDefinition],
) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


def normalize_openai_responses_tool_call(
    item: object,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
) -> NormalizedToolCall:
    name = str(_get(item, "name", ""))
    return normalize_tool_call(
        call_id=str(_get(item, "call_id", "") or _get(item, "id", "") or name),
        name=name,
        raw_arguments=_get(item, "arguments", "{}"),
        provider="openai_responses",
        definition=_definition_for(definitions, name),
    )


def normalize_openai_responses_tool_result(
    item: object,
    *,
    name: str,
    public_preview: dict[str, Any] | None = None,
) -> NormalizedToolResult:
    return NormalizedToolResult(
        call_id=str(_get(item, "call_id", "") or _get(item, "id", "") or name),
        name=name,
        content=_stringify_tool_content(_get(item, "output", _get(item, "content", ""))),
        provider="openai_responses",
        public_preview=public_preview or {"status": "received", "name": name},
    )


def normalize_openai_chat_tool_call(
    tool_call: object,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
) -> NormalizedToolCall:
    function = _get(tool_call, "function", {})
    name = str(_get(function, "name", "") or _get(tool_call, "name", ""))
    return normalize_tool_call(
        call_id=str(_get(tool_call, "id", "") or _get(tool_call, "tool_call_id", "") or name),
        name=name,
        raw_arguments=_get(function, "arguments", _get(tool_call, "arguments", "{}")),
        provider="openai_chat",
        definition=_definition_for(definitions, name),
    )


def normalize_openai_chat_tool_result(
    message: object,
    *,
    name: str,
    public_preview: dict[str, Any] | None = None,
) -> NormalizedToolResult:
    return NormalizedToolResult(
        call_id=str(_get(message, "tool_call_id", "") or _get(message, "id", "") or name),
        name=name,
        content=_stringify_tool_content(_get(message, "content", "")),
        provider="openai_chat",
        public_preview=public_preview or {"status": "received", "name": name},
    )


def normalize_anthropic_tool_call(
    block: object,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
) -> NormalizedToolCall:
    name = str(_get(block, "name", ""))
    return normalize_tool_call(
        call_id=str(_get(block, "id", "") or name),
        name=name,
        raw_arguments=_get(block, "input", {}),
        provider="anthropic",
        definition=_definition_for(definitions, name),
    )


def normalize_anthropic_tool_result(
    block: object,
    *,
    name: str,
    public_preview: dict[str, Any] | None = None,
) -> NormalizedToolResult:
    return NormalizedToolResult(
        call_id=str(_get(block, "tool_use_id", "") or _get(block, "id", "") or name),
        name=name,
        content=_stringify_tool_content(_get(block, "content", "")),
        provider="anthropic",
        public_preview=public_preview or {"status": "received", "name": name},
    )


def normalize_openai_responses_stream_event(
    event: object,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
) -> NormalizedStreamEvent | None:
    event_type = str(_get(event, "type", ""))
    delta = _get(event, "delta", "")
    if event_type == "response.reasoning_summary_text.delta" and delta:
        return NormalizedStreamEvent.thinking_delta(str(delta))
    if event_type == "response.output_text.delta" and delta:
        return NormalizedStreamEvent.text_delta(str(delta))
    if event_type == "response.output_item.done":
        item = _get(event, "item", None)
        if str(_get(item, "type", "")) == "function_call":
            return NormalizedStreamEvent.tool_call_event(
                normalize_openai_responses_tool_call(item, definitions)
            )
    if event_type == "response.completed":
        return NormalizedStreamEvent.done_event()
    return None


def normalize_openai_chat_stream_chunk(
    chunk: object,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
) -> list[NormalizedStreamEvent]:
    events: list[NormalizedStreamEvent] = []
    choices = _get(chunk, "choices", []) or []
    if not choices:
        return events
    delta = _get(choices[0], "delta", {})
    content = _get(delta, "content", "")
    if content:
        events.append(NormalizedStreamEvent.text_delta(str(content)))
    for tool_call in _get(delta, "tool_calls", []) or []:
        events.append(
            NormalizedStreamEvent.tool_call_event(
                normalize_openai_chat_tool_call(tool_call, definitions)
            )
        )
    return events


def normalize_anthropic_stream_event(
    event: object,
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition] = (),
    state: AnthropicStreamState | None = None,
) -> NormalizedStreamEvent | None:
    event_type = str(_get(event, "type", ""))
    if event_type == "content_block_delta":
        delta = _get(event, "delta", {})
        delta_type = str(_get(delta, "type", ""))
        if delta_type == "thinking_delta":
            return NormalizedStreamEvent.thinking_delta(str(_get(delta, "thinking", "")))
        if delta_type == "text_delta":
            return NormalizedStreamEvent.text_delta(str(_get(delta, "text", "")))
        if delta_type == "input_json_delta" and state is not None:
            index = _stream_index(event)
            item = state.tool_blocks.setdefault(index, {"block": {}, "input_json": ""})
            item["input_json"] += str(_get(delta, "partial_json", ""))
    if event_type == "content_block_start":
        block = _get(event, "content_block", {})
        if str(_get(block, "type", "")) == "tool_use":
            if state is not None:
                state.tool_blocks[_stream_index(event)] = {"block": block, "input_json": ""}
                return None
            return NormalizedStreamEvent.tool_call_event(
                normalize_anthropic_tool_call(block, definitions)
            )
    if event_type == "content_block_stop" and state is not None:
        item = state.tool_blocks.pop(_stream_index(event), None)
        if item is not None:
            block = item["block"]
            input_json = item["input_json"]
            return NormalizedStreamEvent.tool_call_event(
                normalize_anthropic_tool_call(
                    {
                        "type": "tool_use",
                        "id": _get(block, "id", ""),
                        "name": _get(block, "name", ""),
                        "input": input_json or _get(block, "input", {}),
                    },
                    definitions,
                )
            )
    if event_type == "message_stop":
        return NormalizedStreamEvent.done_event()
    return None


def _parse_tool_arguments(raw_arguments: str | Mapping[str, Any] | None) -> dict[str, Any]:
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, Mapping):
        return dict(raw_arguments)
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ToolArgumentValidationError("Tool arguments must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ToolArgumentValidationError("Tool arguments must be a JSON object")
        return parsed
    raise ToolArgumentValidationError("Tool arguments must be a JSON object")


def _validate_object_schema(
    schema: Mapping[str, Any],
    value: Mapping[str, Any],
    *,
    path: str,
) -> None:
    if schema.get("type") != "object":
        raise ToolArgumentValidationError(f"{path} must be an object")
    properties = schema.get("properties", {}) or {}
    required = schema.get("required", []) or []
    missing = [name for name in required if name not in value]
    if missing:
        raise ToolArgumentValidationError(f"Missing required tool arguments: {', '.join(missing)}")
    if schema.get("additionalProperties") is False:
        unexpected = [name for name in value if name not in properties]
        if unexpected:
            raise ToolArgumentValidationError(
                f"Unexpected tool arguments: {', '.join(sorted(unexpected))}"
            )
    for name, item in value.items():
        if name in properties:
            _validate_schema_value(properties[name], item, path=f"{path}.{name}")


def _validate_schema_value(schema: Mapping[str, Any], value: Any, *, path: str) -> None:
    if "enum" in schema and value not in schema["enum"]:
        raise ToolArgumentValidationError(f"{path} must be one of: {', '.join(schema['enum'])}")
    expected_type = schema.get("type")
    if expected_type == "string" and not isinstance(value, str):
        raise ToolArgumentValidationError(f"{path} must be a string")
    if expected_type == "boolean" and not isinstance(value, bool):
        raise ToolArgumentValidationError(f"{path} must be a boolean")
    if expected_type == "integer" and not isinstance(value, int):
        raise ToolArgumentValidationError(f"{path} must be an integer")
    if expected_type == "number" and not isinstance(value, int | float):
        raise ToolArgumentValidationError(f"{path} must be a number")
    if expected_type == "array":
        if not isinstance(value, list):
            raise ToolArgumentValidationError(f"{path} must be an array")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_schema_value(item_schema, item, path=f"{path}[{index}]")
    if expected_type == "object":
        if not isinstance(value, Mapping):
            raise ToolArgumentValidationError(f"{path} must be an object")
        _validate_object_schema(schema, value, path=path)


def _definition_for(
    definitions: Sequence[ProviderToolDefinition] | Mapping[str, ProviderToolDefinition],
    name: str,
) -> ProviderToolDefinition | None:
    if isinstance(definitions, Mapping):
        return definitions.get(name)
    for definition in definitions:
        if definition.name == name:
            return definition
    return None


def _get(value: object, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _stream_index(event: object) -> int:
    index = _get(event, "index", 0)
    return index if isinstance(index, int) else 0


def _stringify_tool_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _get(item, "text", None)
            if text is not None:
                parts.append(str(text))
            else:
                parts.append(_stringify_tool_content(item))
        return "".join(parts)
    return json.dumps(content)
