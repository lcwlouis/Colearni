import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrailCreate(BaseModel):
    workspace_id: uuid.UUID
    title: str
    topic: str
    goal: str
    target_depth: str


class TrailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    topic: str
    goal: str
    target_depth: str
    created_at: datetime
