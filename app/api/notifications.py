"""Notifications API — manage Telegram settings and view alert history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_admin
from app.models.alert import Alert
from app.monitoring import TelegramNotifier
from app.schemas.schemas import AlertResponse

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    type: str = Query(None, description="Filter by type: CRITICAL, WARNING, INFO"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Alert)
    if type:
        stmt = stmt.where(Alert.type == type)
    stmt = stmt.order_by(Alert.sent_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/test")
async def test_notification(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Send a test notification to Telegram."""
    notifier = TelegramNotifier(db)
    success = await notifier.send("Test notification from Feed Aggregator", level="INFO")
    return {"success": success, "enabled": notifier.enabled}
