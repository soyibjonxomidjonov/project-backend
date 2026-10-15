import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str
    assistant: str = "chat"
    stream: bool = False


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    content: str
    meta: dict | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assistant: str
    title: str | None
    created_at: datetime


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
