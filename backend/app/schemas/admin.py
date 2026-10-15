from pydantic import BaseModel


class AdminUserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AdminOverviewResponse(BaseModel):
    users: int
    entities: int
    documents: int
    chat_sessions: int
