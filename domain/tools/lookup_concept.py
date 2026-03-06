"""Built-in tool: look up a concept in the knowledge graph."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class LookupConceptParams(BaseModel):
    """Parameters for the lookup_concept tool."""

    concept_id: int = Field(description="ID of the concept to look up")


class LookupConceptTool:
    """Look up concept details (name, description, aliases, tier) from the graph.

    Requires a ``lookup_fn`` (matching ``get_concept_detail`` signature)
    and a ``session`` + ``workspace_id`` injected at construction time.
    """

    name = "lookup_concept"
    description = (
        "Look up a concept in the knowledge graph by its ID. "
        "Returns the concept's name, description, aliases, and tier."
    )
    parameters_model = LookupConceptParams

    def __init__(
        self,
        *,
        lookup_fn: Any,
        session: Any,
        workspace_id: int,
    ) -> None:
        self._lookup = lookup_fn
        self._session = session
        self._workspace_id = workspace_id

    async def execute(self, *, concept_id: int) -> str:
        try:
            detail = self._lookup(
                self._session,
                workspace_id=self._workspace_id,
                concept_id=concept_id,
            )
        except Exception as exc:
            return json.dumps({"error": f"Concept not found: {exc}"})

        return json.dumps({
            "concept_id": concept_id,
            "name": detail.get("canonical_name", ""),
            "description": detail.get("description", ""),
            "aliases": detail.get("aliases", []),
            "tier": detail.get("tier", ""),
        })
