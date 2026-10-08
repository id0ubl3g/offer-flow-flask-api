from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool = Field(strict=True)

class TestSend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: UUID