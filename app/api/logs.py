"""Sync logs API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.sync_log import SyncLog
from app.schemas.schemas import SyncLogResponse

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=list[SyncLogResponse])
async def list_logs(
    source_id: int = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(SyncLog)
    if source_id:
        stmt = stmt.where(SyncLog.source_id == source_id)
    if status:
        stmt = stmt.where(SyncLog.status == status)

    stmt = stmt.order_by(SyncLog.started_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    return result.scalars().all()
