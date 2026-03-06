"""Tool calling framework for LLM-powered agentic interactions.

Provides a ``Tool`` protocol, a ``ToolRegistry`` for managing available tools,
and a ``ToolExecutor`` for dispatching tool calls from LLM responses back to
registered handlers.  Follows the OpenAI ``tools`` parameter format which is
supported by both the OpenAI SDK and LiteLLM.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from core.llm_messages import Message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Tool(Protocol):
    """Interface every tool must satisfy."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters_model(self) -> type[BaseModel]: ...

    async def execute(self, **kwargs: Any) -> str:
        """Run the tool with validated keyword arguments and return a string."""
        ...


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Immutable-after-build registry of available :class:`Tool` instances.

    Usage::

        registry = ToolRegistry()
        registry.register(my_tool)
        openai_tools = registry.to_openai_tools()
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    # -- mutators (build phase) ---------------------------------------------

    def register(self, tool: Tool) -> None:
        """Register a tool.  Raises ``ValueError`` on duplicate names."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    # -- accessors ----------------------------------------------------------

    def get(self, name: str) -> Tool | None:
        """Return the tool with *name*, or ``None`` if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools in insertion order."""
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    # -- OpenAI format ------------------------------------------------------

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Produce the ``tools`` list for an OpenAI / LiteLLM completion call.

        Returns a list of dicts in the format::

            [
                {
                    "type": "function",
                    "function": {
                        "name": "...",
                        "description": "...",
                        "parameters": { ... }   # JSON Schema
                    }
                },
                ...
            ]
        """
        result: list[dict[str, Any]] = []
        for tool in self._tools.values():
            schema = tool.parameters_model.model_json_schema()
            # Remove Pydantic metadata keys that OpenAI doesn't expect
            schema.pop("title", None)
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": schema,
                    },
                }
            )
        return result


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------


class ToolExecutor:
    """Dispatches tool calls from an LLM response to registered handlers.

    Given a list of ``tool_calls`` (as returned by the OpenAI / LiteLLM SDK),
    this executor validates arguments, invokes the tool, and returns a list of
    ``Message(role="tool", ...)`` dicts ready to append to the conversation.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[Message]:
        """Execute each tool call and return tool-result messages.

        Never raises on tool execution errors — returns an error message as the
        tool result so the LLM can recover.
        """
        results: list[Message] = []
        for tc in tool_calls:
            tool_call_id = tc.get("id", "")
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")

            result_text = await self._run_one(name, raw_args)
            results.append(
                Message(role="tool", content=result_text, tool_call_id=tool_call_id),
            )
        return results

    async def _run_one(self, name: str, raw_args: str) -> str:
        """Execute a single tool call, catching all errors."""
        tool = self._registry.get(name)
        if tool is None:
            logger.warning("Unknown tool requested: %s", name)
            return json.dumps({"error": f"Unknown tool: {name}"})

        # Parse JSON arguments
        try:
            args_dict = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON arguments for %s: %s", name, exc)
            return json.dumps({"error": f"Invalid arguments JSON: {exc}"})

        # Validate against Pydantic schema
        try:
            validated = tool.parameters_model.model_validate(args_dict)
            kwargs = validated.model_dump()
        except ValidationError as exc:
            logger.warning("Argument validation failed for %s: %s", name, exc)
            return json.dumps({"error": f"Invalid arguments: {exc}"})

        # Execute
        try:
            return await tool.execute(**kwargs)
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            return json.dumps({"error": f"Tool execution failed: {exc}"})
