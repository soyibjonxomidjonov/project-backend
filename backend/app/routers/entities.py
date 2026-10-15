import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, get_optional_user
from app.models.entity import Entity
from app.models.user import User
from app.schemas.entity import (
    EntityCreate,
    EntityListResponse,
    EntityResponse,
    EntityStatsResponse,
    EntityUpdate,
)

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/stats", summary="Entity statistics", response_model=EntityStatsResponse)
async def entity_stats(
    type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if type:
        conditions.append(Entity.type == type)

    q = select(func.count()).select_from(Entity)
    for c in conditions:
        q = q.where(c)
    total = (await db.execute(q)).scalar()

    q = select(Entity.status, func.count()).select_from(Entity).group_by(Entity.status)
    for c in conditions:
        q = q.where(c)
    by_status = {row[0]: row[1] for row in (await db.execute(q)).all()}

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    q = (
        select(func.date_trunc("day", Entity.created_at).label("day"), func.count())
        .select_from(Entity)
        .where(Entity.created_at >= thirty_days_ago)
        .group_by("day")
        .order_by("day")
    )
    for c in conditions:
        q = q.where(c)
    by_day = [{"date": row[0].isoformat(), "count": row[1]} for row in (await db.execute(q)).all()]

    return EntityStatsResponse(total=total, by_status=by_status, by_day=by_day)


@router.get("", summary="List entities", response_model=EntityListResponse)
async def list_entities(
    request: Request,
    type: str | None = Query(None),
    q: str | None = Query(None),
    status: str | None = Query(None),
    owner: str | None = Query(None),
    sort: str = Query("-created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    query = select(Entity)
    count_q = select(func.count()).select_from(Entity)

    filters = []
    if type:
        filters.append(Entity.type == type)
    if status:
        filters.append(Entity.status == status)
    if owner == "me" and user:
        filters.append(Entity.owner_id == user.id)
    elif user is None:
        filters.append(Entity.is_public == True)
    if q:
        filters.append(Entity.title.ilike(f"%{q}%"))

    for key, value in request.query_params.items():
        if key.startswith("filter[data.") and key.endswith("]"):
            field = key[12:-1]
            filters.append(Entity.data[field].astext == value)

    for f in filters:
        query = query.where(f)
        count_q = count_q.where(f)

    sort_field = sort.lstrip("-")
    sort_col = getattr(Entity, sort_field, Entity.created_at)
    query = query.order_by(sort_col.desc() if sort.startswith("-") else sort_col.asc())

    total = (await db.execute(count_q)).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()

    return EntityListResponse(
        items=[EntityResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{entity_id}", summary="Get entity by ID", response_model=EntityResponse)
async def get_entity(entity_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(404, "Entity not found")
    return EntityResponse.model_validate(entity)


@router.post("", summary="Create entity", response_model=EntityResponse, status_code=201)
async def create_entity(
    body: EntityCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = Entity(
        type=body.type,
        title=body.title,
        data=body.data,
        status=body.status,
        is_public=body.is_public,
        owner_id=user.id,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return EntityResponse.model_validate(entity)


@router.patch("/{entity_id}", summary="Update entity", response_model=EntityResponse)
async def update_entity(
    entity_id: uuid.UUID,
    body: EntityUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(404, "Entity not found")
    if entity.owner_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not allowed")

    if body.title is not None:
        entity.title = body.title
    if body.data is not None:
        entity.data = {**entity.data, **body.data}
    if body.status is not None:
        entity.status = body.status
    if body.is_public is not None:
        entity.is_public = body.is_public

    entity.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entity)
    return EntityResponse.model_validate(entity)


@router.delete("/{entity_id}", summary="Delete entity", status_code=204)
async def delete_entity(
    entity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(404, "Entity not found")
    if entity.owner_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not allowed")
    await db.delete(entity)
    await db.commit()
