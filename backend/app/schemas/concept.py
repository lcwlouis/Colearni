import uuid

from pydantic import BaseModel, ConfigDict, Field

from .types import BloomLevel, ConceptLevel, Difficulty, NodeType, RelationType


class ConceptNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trail_id: uuid.UUID
    slug: str
    title: str
    node_type: NodeType
    concept_level: ConceptLevel
    difficulty: Difficulty
    bloom_level: BloomLevel
    mastery_check_labels: list[str]
    metadata_json: dict


class ConceptEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trail_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relation_type: RelationType


class ConceptDetailResponse(BaseModel):
    concept: ConceptNodeRead
    prerequisites: list[ConceptNodeRead]
    contained_nodes: list[ConceptNodeRead]
    containing_nodes: list[ConceptNodeRead]
    related: list[ConceptNodeRead]
    mastery: None = None
    sources: list[dict] = Field(default_factory=list)
