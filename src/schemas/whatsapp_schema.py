from src.schemas.offer_schema import normalize_tags

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from uuid import UUID

class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool | None = Field(default=None, strict=True)
    tags: list[str] | None = None

    _tags = field_validator("tags")(normalize_tags)

    @model_validator(mode="after")
    def reject_nulls(self) -> "GroupUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")

        return self

class TestSend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: UUID