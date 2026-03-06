"""Built-in tool: search the knowledge base via hybrid retrieval."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class SearchKnowledgeParams(BaseModel):
    """Parameters for the search_knowledge_base tool."""

    query: str = Field(description="Natural-language search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


class SearchKnowledgeTool:
    """Search the workspace's ingested documents via hybrid vector + FTS retrieval.

    Requires a ``retriever`` (callable matching ``HybridRetriever.retrieve``)
    and a ``workspace_id`` injected at construction time.
    """

    name = "search_knowledge_base"
    description = (
        "Search the learner's knowledge base for relevant passages. "
        "Returns ranked text chunks from ingested documents."
    )
    parameters_model = SearchKnowledgeParams

    def __init__(
        self,
        *,
        retrieve_fn: Any,
        workspace_id: int,
    ) -> None:
        self._retrieve = retrieve_fn
        self._workspace_id = workspace_id

    async def execute(self, *, query: str, top_k: int = 5) -> str:
        results = self._retrieve(
            query=query,
            workspace_id=self._workspace_id,
            top_k=top_k,
        )
        if not results:
            return json.dumps({"results": [], "count": 0})

        items = []
        for r in results:
            item: dict[str, Any] = {"text": getattr(r, "text", str(r))}
            if hasattr(r, "score"):
                item["score"] = round(r.score, 4)
            if hasattr(r, "document_title"):
                item["source"] = r.document_title
            items.append(item)
        return json.dumps({"results": items, "count": len(items)})
