"""Built-in tool: check a learner's mastery level for a concept."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class CheckMasteryParams(BaseModel):
    """Parameters for the check_mastery tool."""

    concept_id: int = Field(description="ID of the concept to check mastery for")


class CheckMasteryTool:
    """Check the learner's mastery status and score for a specific concept.

    Requires a ``mastery_fn`` (matching ``lookup_mastery`` signature)
    and session/workspace/user context injected at construction time.
    """

    name = "check_mastery"
    description = (
        "Check the learner's mastery level for a concept. "
        "Returns the mastery status (learned/learning/not_started) and score."
    )
    parameters_model = CheckMasteryParams

    def __init__(
        self,
        *,
        mastery_fn: Any,
        session: Any,
        workspace_id: int,
        user_id: int,
    ) -> None:
        self._lookup_mastery = mastery_fn
        self._session = session
        self._workspace_id = workspace_id
        self._user_id = user_id

    async def execute(self, *, concept_id: int) -> str:
        result = self._lookup_mastery(
            self._session,
            workspace_id=self._workspace_id,
            user_id=self._user_id,
            concept_id=concept_id,
        )
        if result is None:
            return json.dumps({
                "concept_id": concept_id,
                "status": "not_started",
                "score": 0.0,
            })

        return json.dumps({
            "concept_id": concept_id,
            "status": result.get("status", "unknown"),
            "score": result.get("score", 0.0),
        })
