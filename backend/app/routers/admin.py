import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_admin
from app.models.chat import ChatSession
from app.models.document import Document
from app.models.entity import Entity
from app.models.user import User
from app.schemas.admin import AdminOverviewResponse, AdminUserUpdate
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", summary="List all users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count()).select_from(User))).scalar()
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    return {
        "items": [UserResponse.model_validate(u, from_attributes=True) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/users/{user_id}", summary="Update user role/status", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user, from_attributes=True)


@router.get("/overview", summary="Admin overview statistics", response_model=AdminOverviewResponse)
async def admin_overview(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(func.count()).select_from(User))).scalar()
    entities = (await db.execute(select(func.count()).select_from(Entity))).scalar()
    documents = (await db.execute(select(func.count()).select_from(Document))).scalar()
    chat_sessions = (await db.execute(select(func.count()).select_from(ChatSession))).scalar()
    return AdminOverviewResponse(
        users=users, entities=entities, documents=documents, chat_sessions=chat_sessions
    )
