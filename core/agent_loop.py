"""Bounded agent loop for multi-turn tool-calling interactions.

The :class:`AgentLoop` repeatedly calls the LLM, dispatches any requested tool
calls via :class:`~core.tools.ToolExecutor`, appends results, and loops until
the LLM produces a final text response — or a hard iteration budget is
exhausted (per ``docs/CODEX.md`` budget rules).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.llm_messages import Message
from core.tools import ToolExecutor

logger = logging.getLogger(__name__)

# Default budget — can be overridden per call.
DEFAULT_MAX_ITERATIONS = 5


@dataclass
class AgentLoopResult:
    """Result of a bounded agent loop run."""

    text: str
    """Final assistant text (may be empty if budget exhausted)."""

    messages: list[Message]
    """Full message history including tool call/result messages."""

    iterations: int
    """Number of LLM calls made."""

    tool_calls_made: int = 0
    """Total number of tool calls dispatched."""

    budget_exhausted: bool = False
    """True if the loop stopped because max_iterations was reached."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0


class AgentLoop:
    """Bounded LLM ↔ tool loop.

    Each iteration:
      1. Call the LLM with messages + tools.
      2. If the response contains ``tool_calls``, execute them and append
         results to messages.
      3. Repeat until the LLM returns a text response with no tool calls,
         or ``max_iterations`` is reached.
    """

    def __init__(
        self,
        *,
        tool_executor: ToolExecutor,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        self._executor = tool_executor
        self._max_iterations = max_iterations

    async def run(
        self,
        *,
        llm_call: LLMCallable,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> AgentLoopResult:
        """Run the agent loop.

        Parameters
        ----------
        llm_call:
            An async callable ``(messages, tools) -> dict`` that calls the LLM.
            The returned dict must have a ``choices[0].message`` structure.
        messages:
            Initial message list (system + user messages).
        tools:
            OpenAI-format tool definitions.
        """
        messages = list(messages)  # don't mutate caller's list
        total_tool_calls = 0
        total_prompt = 0
        total_completion = 0

        for iteration in range(1, self._max_iterations + 1):
            response = await llm_call(messages, tools)

            # Accumulate token usage
            usage = response.get("usage", {})
            total_prompt += usage.get("prompt_tokens", 0)
            total_completion += usage.get("completion_tokens", 0)

            # Extract assistant message
            choices = response.get("choices", [])
            if not choices:
                logger.warning("AgentLoop: empty choices from LLM")
                return AgentLoopResult(
                    text="",
                    messages=messages,
                    iterations=iteration,
                    tool_calls_made=total_tool_calls,
                    total_prompt_tokens=total_prompt,
                    total_completion_tokens=total_completion,
                )

            msg = choices[0].get("message", {})
            tool_calls = msg.get("tool_calls")
            content = msg.get("content") or ""

            # Append assistant message to history
            assistant_msg: Message = {"role": "assistant", "content": content}
            if tool_calls:
                # Store tool_calls in the message for SDK compatibility
                assistant_msg["tool_calls"] = tool_calls  # type: ignore[typeddict-unknown-key]
            messages.append(assistant_msg)

            # If no tool calls, we're done
            if not tool_calls:
                return AgentLoopResult(
                    text=content.strip(),
                    messages=messages,
                    iterations=iteration,
                    tool_calls_made=total_tool_calls,
                    total_prompt_tokens=total_prompt,
                    total_completion_tokens=total_completion,
                )

            # Execute tool calls and append results
            total_tool_calls += len(tool_calls)
            tool_results = await self._executor.execute_tool_calls(tool_calls)
            messages.extend(tool_results)

            logger.debug(
                "AgentLoop iteration %d: %d tool call(s)",
                iteration, len(tool_calls),
            )

        # Budget exhausted
        logger.warning(
            "AgentLoop budget exhausted after %d iterations (%d tool calls)",
            self._max_iterations,
            total_tool_calls,
        )
        return AgentLoopResult(
            text=content.strip() if "content" in dir() else "",
            messages=messages,
            iterations=self._max_iterations,
            tool_calls_made=total_tool_calls,
            budget_exhausted=True,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
        )


# ---------------------------------------------------------------------------
# Type alias for the LLM callable
# ---------------------------------------------------------------------------

from collections.abc import Callable, Coroutine  # noqa: E402

LLMCallable = Callable[
    [list[Message], list[dict[str, Any]]],
    Coroutine[Any, Any, dict[str, Any]],
]
