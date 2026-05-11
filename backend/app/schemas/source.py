import uuid

from pydantic import BaseModel, ConfigDict


class SourceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    origin: str
    access: str
    title: str
    url: str | None
    license: str | None
    include_on_public_export: bool
    metadata_json: dict
