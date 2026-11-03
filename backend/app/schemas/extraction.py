import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldRead(BaseModel):
    key: str
    label: str
    type: str
    required: bool


class SchemaRead(BaseModel):
    key: str
    name: str
    fields: list[FieldRead]


class IssueRead(BaseModel):
    code: str
    message: str
    field: str | None
    severity: Literal["error", "warning"]


class ExtractionRequest(BaseModel):
    schema_key: str = "invoice"
    # Optional: without a model only the rule-based reader runs (fast, no LLM needed).
    provider_id: uuid.UUID | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _model_with_provider(self):
        if (self.provider_id is None) != (self.model is None):
            raise ValueError("provider_id and model must be given together")
        return self


class ExtractionUpdate(BaseModel):
    values: dict[str, Any]


class ExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    schema_key: str
    status: str
    values: dict[str, Any]
    issues: list[IssueRead]
    model: str | None
    error_message: str | None
    reviewed_at: datetime | None
    updated_at: datetime
