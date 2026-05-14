import uuid

import pytest
from pydantic import ValidationError

from backend.app.schemas.trail import TrailGenerateRequest, TrailInsert


def test_trail_generate_request_matches_api_contract():
    payload = {
        "topic": "Matrices",
        "goal": "Understand matrix multiplication",
        "target_depth": "understand",
    }

    request = TrailGenerateRequest.model_validate(payload)

    assert request.model_dump() == {**payload, "max_nodes": 40}


def test_trail_generate_request_rejects_workspace_id_and_title():
    with pytest.raises(ValidationError):
        TrailGenerateRequest.model_validate(
            {
                "workspace_id": str(uuid.uuid4()),
                "title": "Client title",
                "topic": "Matrices",
                "goal": "Understand matrix multiplication",
                "target_depth": "understand",
            }
        )


def test_trail_generate_request_rejects_invalid_target_depth():
    with pytest.raises(ValidationError):
        TrailGenerateRequest.model_validate(
            {
                "topic": "Matrices",
                "goal": "Understand matrix multiplication",
                "target_depth": "invalid",
            }
        )


def test_trail_insert_includes_server_side_fields():
    workspace_id = uuid.uuid4()
    trail = TrailInsert.model_validate(
        {
            "workspace_id": str(workspace_id),
            "title": "Matrix Multiplication",
            "topic": "Matrices",
            "goal": "Understand matrix multiplication",
            "target_depth": "understand",
        }
    )

    assert trail.workspace_id == workspace_id
    assert trail.title == "Matrix Multiplication"
