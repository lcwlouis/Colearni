import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .mastery import MasteryRecordRead
from .source import SourceRecordRead
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


class PrimerKeyTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=1, max_length=500)


class ConceptPrimerOutput(BaseModel):
    """Strict shape parsed from the concept_primer LLM generation pass."""

    model_config = ConfigDict(extra="forbid")

    overview: str = Field(min_length=1, max_length=2000)
    key_terms: list[PrimerKeyTerm] = Field(min_length=3, max_length=6)
    # Short learner-facing starter prompts that power dynamic suggestion chips
    # on the chat welcome screen. Tailored to this concept.
    sample_questions: list[Annotated[str, Field(min_length=1, max_length=90)]] = Field(
        min_length=3, max_length=4
    )


class ConceptPrimerRead(BaseModel):
    """Primer read shape: the cached output plus the cache schema version."""

    overview: str
    key_terms: list[PrimerKeyTerm]
    # Default empty so primers cached before sample_questions existed still validate.
    sample_questions: list[str] = Field(default_factory=list)
    version: int = 1


class PrimerGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_new: bool = False


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
    mastery: MasteryRecordRead
    sources: list[SourceRecordRead] = Field(default_factory=list)
    primer: ConceptPrimerRead | None = None
