"""Factory for building a ToolRegistry with the standard built-in tools.

Call :func:`build_tool_registry` to get a registry pre-populated with
search, concept lookup, mastery check, and web search tools, wired to
the given DB session and workspace/user context.
"""

from __future__ import annotations

from typing import Any

from core.tools import ToolRegistry
from domain.tools.check_mastery import CheckMasteryTool
from domain.tools.lookup_concept import LookupConceptTool
from domain.tools.search_knowledge import SearchKnowledgeTool
from domain.tools.web_search import WebSearchTool


def build_tool_registry(
    *,
    session: Any,
    workspace_id: int,
    user_id: int,
    retrieve_fn: Any | None = None,
    concept_lookup_fn: Any | None = None,
    mastery_fn: Any | None = None,
    web_search_api_key: str | None = None,
    web_search_max_results: int = 5,
) -> ToolRegistry:
    """Build a :class:`ToolRegistry` with the standard built-in tools.

    Only tools whose required dependency is provided are registered.
    """
    registry = ToolRegistry()

    if retrieve_fn is not None:
        registry.register(
            SearchKnowledgeTool(
                retrieve_fn=retrieve_fn,
                workspace_id=workspace_id,
            )
        )

    if concept_lookup_fn is not None:
        registry.register(
            LookupConceptTool(
                lookup_fn=concept_lookup_fn,
                session=session,
                workspace_id=workspace_id,
            )
        )

    if mastery_fn is not None:
        registry.register(
            CheckMasteryTool(
                mastery_fn=mastery_fn,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
            )
        )

    if web_search_api_key:
        registry.register(
            WebSearchTool(
                api_key=web_search_api_key,
                max_results=web_search_max_results,
            )
        )

    return registry
