import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    provider_id: uuid.UUID
    title: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200, description="Defaults to the provider's default_model")
    document_ids: list[uuid.UUID] = Field(default_factory=list, description="Empty = all completed documents")


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    provider_credential_id: uuid.UUID | None
    model: str
    document_ids: list[uuid.UUID]
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[uuid.UUID] | None = Field(
        default=None, description="Override the conversation's document scope for this question"
    )


class CitationRead(BaseModel):
    citation_id: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    quoted_text: str
    score: float | None


class Usage(BaseModel):
    input_tokens: int | None
    output_tokens: int | None


class MessageRead(BaseModel):
    message_id: uuid.UUID
    role: str
    content: str
    status: str | None
    grounded: bool | None
    citations: list[CitationRead]
    model: str | None
    usage: Usage | None
    latency_ms: int | None
    search_query: str | None
    created_at: datetime


class AnswerResponse(BaseModel):
    message_id: uuid.UUID
    answer: str
    status: str
    grounded: bool
    citations: list[CitationRead]
    model: str | None
    usage: Usage
    latency_ms: int
    truncated: bool
    search_query: str = Field(description="Standalone query used for retrieval (follow-ups are rewritten)")
