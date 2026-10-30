import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    message: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str | None
    file_size: int | None
    checksum: str | None
    status: str
    page_count: int | None
    embedding_model: str | None
    created_at: datetime


class DocumentDetail(DocumentRead):
    chunk_count: int


class DocumentStatusRead(BaseModel):
    document_id: uuid.UUID
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    chunk_count: int


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    page_number: int | None
    token_count: int | None
    content: str
    metadata: dict = Field(validation_alias="metadata_")


class ChunkPage(BaseModel):
    total: int
    items: list[ChunkRead]
