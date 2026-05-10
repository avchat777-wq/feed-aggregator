"""Dashboard API — aggregated stats and health indicators."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.source import Source
from app.models.object import Object
from app.models.sync_log import SyncLog

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    # Sources stats
    sources_result = await db.execute(select(Source))
    sources = list(sources_result.scalars().all())

    total_sources = len(sources)
    active_sources = sum(1 for s in sources if s.is_active)

    # Object counts
    active_count = await db.execute(
        select(func.count(Object.id)).where(Object.status == "active")
    )
    total_active = active_count.scalar() or 0

    total_count = await db.execute(select(func.count(Object.id)))
    total_objects = total_count.scalar() or 0

    # Last sync
    last_sync_result = await db.execute(
        select(SyncLog)
        .where(SyncLog.source_id.is_(None))
        .order_by(SyncLog.started_at.desc())
        .limit(1)
    )
    last_sync = last_sync_result.scalar_one_or_none()

    # Sources health
    sources_health = []
    for s in sources:
        health = "ok"
        if s.consecutive_failures >= 2:
            health = "error"
        elif s.consecutive_failures >= 1:
            health = "warning"
        elif not s.is_active:
            health = "disabled"

        sources_health.append({
            "source_id": s.id,
            "name": s.name,
            "developer": s.developer_name,
            "type": s.type,
            "status": health,
            "is_active": s.is_active,
            "last_sync": s.last_sync_at.isoformat() if s.last_sync_at else None,
            "object_count": s.last_object_count or 0,
            "consecutive_failures": s.consecutive_failures or 0,
        })

    # Objects by status
    status_result = await db.execute(
        select(Object.status, func.count(Object.id))
        .group_by(Object.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # Recent sync history (last 10)
    history_result = await db.execute(
        select(SyncLog)
        .where(SyncLog.source_id.is_(None))
        .order_by(SyncLog.started_at.desc())
        .limit(10)
    )
    sync_history = []
    for log in history_result.scalars().all():
        sync_history.append({
            "id": log.id,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "status": log.status,
            "objects_total": log.objects_total,
            "objects_new": log.objects_new,
            "objects_updated": log.objects_updated,
            "objects_removed": log.objects_removed,
            "errors_count": log.errors_count,
        })

    return {
        "total_sources": total_sources,
        "active_sources": active_sources,
        "total_objects": total_objects,
        "active_objects": total_active,
        "objects_by_status": by_status,
        "last_sync": {
            "at": last_sync.started_at.isoformat() if last_sync and last_sync.started_at else None,
            "status": last_sync.status if last_sync else None,
        },
        "sources_health": sources_health,
        "sync_history": sync_history,
    }
