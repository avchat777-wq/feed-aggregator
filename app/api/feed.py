"""Feed API — preview, URL, manual sync trigger."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.auth import require_admin, get_current_user
from app.config import settings
from app.scheduler.scheduler import SyncOrchestrator

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("/url")
async def get_feed_url(_=Depends(get_current_user)):
    """Return the public URL of the current feed."""
    return {"url": f"{settings.feed_base_url}/feed.xml"}


@router.get("/download")
async def download_feed(_=Depends(get_current_user)):
    """Download the current feed XML file."""
    feed_path = Path(settings.feed_output_dir) / "feed.xml"
    if not feed_path.exists():
        raise HTTPException(status_code=404, detail="Feed file not yet generated")
    return FileResponse(
        str(feed_path),
        media_type="application/xml",
        filename="feed.xml",
    )


@router.post("/sync")
async def trigger_sync(_=Depends(require_admin)):
    """Manually trigger a full synchronization cycle."""
    orchestrator = SyncOrchestrator()
    # Run in background
    asyncio.create_task(orchestrator.run_full_sync())
    return {"status": "sync_started", "message": "Synchronization started in background"}


@router.get("/preview")
async def preview_feed(_=Depends(get_current_user)):
    """Return first 2KB of feed for preview."""
    feed_path = Path(settings.feed_output_dir) / "feed.xml"
    if not feed_path.exists():
        return {"content": "", "exists": False}

    with open(feed_path, "r", encoding="utf-8") as f:
        content = f.read(2048)

    return {"content": content, "exists": True, "size_bytes": feed_path.stat().st_size}
