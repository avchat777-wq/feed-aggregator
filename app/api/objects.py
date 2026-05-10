"""Objects API — search, filter, view details with history."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.object import Object, ObjectHistory
from app.schemas.schemas import ObjectResponse, ObjectHistoryResponse

router = APIRouter(prefix="/api/objects", tags=["objects"])


@router.get("", response_model=list[ObjectResponse])
async def list_objects(
    developer: str = Query(None, description="Filter by developer name"),
    jk_name: str = Query(None, description="Filter by residential complex"),
    status: str = Query(None, description="Filter by status"),
    source_id: int = Query(None, description="Filter by source"),
    rooms: int = Query(None, description="Filter by rooms count"),
    price_min: int = Query(None, description="Min price"),
    price_max: int = Query(None, description="Max price"),
    search: str = Query(None, description="Search in external_id or flat_number"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Object)
    conditions = []

    if developer:
        conditions.append(Object.developer_name.ilike(f"%{developer}%"))
    if jk_name:
        conditions.append(Object.jk_name.ilike(f"%{jk_name}%"))
    if status:
        conditions.append(Object.status == status)
    if source_id:
        conditions.append(Object.source_id == source_id)
    if rooms is not None:
        conditions.append(Object.rooms == rooms)
    if price_min:
        conditions.append(Object.price >= price_min)
    if price_max:
        conditions.append(Object.price <= price_max)
    if search:
        conditions.append(
            (Object.external_id.ilike(f"%{search}%")) |
            (Object.flat_number.ilike(f"%{search}%"))
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Object.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/count")
async def count_objects(
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(func.count(Object.id))
    if status:
        stmt = stmt.where(Object.status == status)
    result = await db.execute(stmt)
    return {"count": result.scalar()}


@router.get("/{object_id}", response_model=ObjectResponse)
async def get_object(
    object_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj


@router.get("/{object_id}/history", response_model=list[ObjectHistoryResponse])
async def get_object_history(
    object_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(ObjectHistory)
        .where(ObjectHistory.object_id == object_id)
        .order_by(ObjectHistory.changed_at.desc())
    )
    return result.scalars().all()


@router.get("/stats/by-developer")
async def stats_by_developer(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = (
        select(
            Object.developer_name,
            func.count(Object.id).label("count"),
            func.avg(Object.price).label("avg_price"),
        )
        .where(Object.status == "active")
        .group_by(Object.developer_name)
    )
    result = await db.execute(stmt)
    return [
        {"developer": row[0], "count": row[1], "avg_price": int(row[2] or 0)}
        for row in result.all()
    ]


@router.get("/stats/by-jk")
async def stats_by_jk(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = (
        select(
            Object.jk_name,
            Object.developer_name,
            func.count(Object.id).label("count"),
            func.avg(Object.price).label("avg_price"),
            func.min(Object.price).label("min_price"),
            func.max(Object.price).label("max_price"),
        )
        .where(Object.status == "active")
        .group_by(Object.jk_name, Object.developer_name)
    )
    result = await db.execute(stmt)
    return [
        {
            "jk_name": row[0], "developer": row[1], "count": row[2],
            "avg_price": int(row[3] or 0), "min_price": row[4], "max_price": row[5],
        }
        for row in result.all()
    ]
