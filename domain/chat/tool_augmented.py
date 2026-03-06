"""Tool-augmented LLM generation via AgentLoop.

Provides a sync entry point that wraps the async :class:`~core.agent_loop.AgentLoop`
behind the ``enable_tool_calling`` feature flag.  Used by
:func:`~domain.chat.response_service.generate_tutor_text` when tool calling is enabled.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.agent_loop import AgentLoop, AgentLoopResult
from core.llm_messages import Message
from core.tools import ToolExecutor, ToolRegistry

logger = logging.getLogger(__name__)

_DEFAULT_TEMPERATURE = 0.7


def _adapt_llm_client(llm_client: Any) -> Any:
    """Adapt a LLM client into the async callable the AgentLoop expects.

    The AgentLoop wants ``async (messages, tools) -> dict`` returning a raw
    OpenAI-format response.  The provider base class exposes
    ``_call_with_observability`` which returns exactly that format (sync).
    We wrap it with ``asyncio.to_thread`` for async compatibility.
    """
    raw_call = getattr(llm_client, "_call_with_observability", None)
    if raw_call is None:
        raise TypeError(
            "LLM client does not expose _call_with_observability; "
            "tool-augmented generation requires a provider-backed client"
        )
    temperature: float = getattr(llm_client, "_tutor_temperature", _DEFAULT_TEMPERATURE)

    async def llm_call(
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = await asyncio.to_thread(
            raw_call,
            messages=messages,
            temperature=temperature,
            response_format=None,
            tools=tools or None,
        )
        return dict(result)

    return llm_call


async def _run_tool_augmented(
    *,
    messages: list[Message],
    llm_client: Any,
    tool_registry: ToolRegistry,
    max_iterations: int = 5,
) -> AgentLoopResult:
    """Run the AgentLoop with tool-augmented generation (async)."""
    executor = ToolExecutor(tool_registry)
    agent_loop = AgentLoop(tool_executor=executor, max_iterations=max_iterations)
    llm_call = _adapt_llm_client(llm_client)
    tools = tool_registry.to_openai_tools()
    return await agent_loop.run(llm_call=llm_call, messages=messages, tools=tools)


def generate_with_tools(
    *,
    messages: list[Message],
    llm_client: Any,
    tool_registry: ToolRegistry,
    max_iterations: int = 5,
) -> AgentLoopResult:
    """Sync entry point for tool-augmented generation.

    Handles the sync→async boundary: uses ``asyncio.run()`` when no event
    loop is running, or spins up a worker thread otherwise (matching the
    pattern in ``adapters.llm.providers``).
    """
    coro = _run_tool_augmented(
        messages=messages,
        llm_client=llm_client,
        tool_registry=tool_registry,
        max_iterations=max_iterations,
    )

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is not None and running_loop.is_running():
        import concurrent.futures  # noqa: PLC0415

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    return asyncio.run(coro)
