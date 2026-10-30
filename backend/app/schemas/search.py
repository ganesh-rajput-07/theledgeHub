import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    document_ids: list[uuid.UUID] = Field(default_factory=list)
    min_score: float | None = Field(default=None, ge=-1, le=1)


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
