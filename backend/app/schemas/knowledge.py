import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeTextRequest(BaseModel):
    title: str
    content: str


class KnowledgeSearchRequest(BaseModel):
    query: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    filename: str | None
    mime_type: str | None
    status: str
    chunk_count: int
    created_at: datetime


class ChunkResult(BaseModel):
    content: str
    document_title: str
    chunk_index: int
    similarity: float
