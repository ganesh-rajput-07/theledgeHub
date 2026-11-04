import uuid
from datetime import datetime
from typing import Literal

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
    origin: dict | None = None
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


class PageInfo(BaseModel):
    document_id: uuid.UUID
    page_count: int


class MergeRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=2, max_length=50, description="In the order to merge")
    filename: str | None = Field(default=None, max_length=255)


class ExtractPagesRequest(BaseModel):
    pages: str = Field(min_length=1, max_length=200, description="e.g. '1-3, 5'. Pages not listed are left out")
    filename: str | None = Field(default=None, max_length=255)


class SplitRequest(BaseModel):
    ranges: list[str] | None = Field(
        default=None, max_length=100, description="One new document per range, e.g. ['1-2', '3']. Empty: one per page"
    )


class RotateRequest(BaseModel):
    pages: str = Field(default="1-", min_length=1, max_length=200, description="'1-' = every page")
    degrees: Literal[90, 180, 270] = 90
