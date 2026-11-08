"""``POST /internal/ingestions`` payload (TECH-V2-core-api §8.1), stored as the job payload."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class AccessSpec(_Camel):
    visibility: Literal["WORKSPACE", "DEPARTMENTS"]
    department_ids: list[UUID] = Field(default_factory=list)
    access_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def _departments(self) -> AccessSpec:
        if self.visibility == "DEPARTMENTS" and not self.department_ids:
            raise ValueError("DEPARTMENTS visibility needs at least one department")
        return self


class SuggestCategory(_Camel):
    id: UUID
    name: str


class SuggestSpec(_Camel):
    enabled: bool = False
    categories: list[SuggestCategory] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class IngestionRequest(_Camel):
    workspace_id: UUID
    document_id: UUID
    version_id: UUID
    version_no: int = Field(ge=1)
    object_key: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    attempt: int = Field(0, ge=0)
    file_type: str = Field(min_length=1)  # unsupported values fail the job (UNSUPPORTED_TYPE)
    mime_type: str | None = None
    original_name: str | None = None
    title: str = Field(min_length=1)
    access: AccessSpec
    suggest: SuggestSpec | None = None
