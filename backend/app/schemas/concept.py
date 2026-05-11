import uuid

from pydantic import BaseModel, ConfigDict


class ConceptNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trail_id: uuid.UUID
    slug: str
    title: str
    node_type: str
    concept_level: str
    difficulty: str
    bloom_level: str
    mastery_check_labels: list[str]
    metadata_json: dict


class ConceptEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trail_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relation_type: str
