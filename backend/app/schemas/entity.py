import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntityCreate(BaseModel):
    type: str
    title: str
    data: dict = {}
    status: str = "active"
    is_public: bool = True


class EntityUpdate(BaseModel):
    title: str | None = None
    data: dict | None = None
    status: str | None = None
    is_public: bool | None = None


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    data: dict
    status: str
    owner_id: uuid.UUID | None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class EntityListResponse(BaseModel):
    items: list[EntityResponse]
    total: int
    page: int
    page_size: int


class EntityStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_day: list[dict]
