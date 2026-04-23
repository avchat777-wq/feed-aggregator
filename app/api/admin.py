"""Admin API — system-level operations (file uploads, lookup management, etc.)."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.api.auth import get_current_user
from app.services.avito_lookup import avito_lookup, AVITO_DEV_URL

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

AVITO_DEV_MAX_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Avito New Developments directory ──────────────────────────────────────────

@router.get("/avito-developments/status")
async def avito_developments_status(_=Depends(get_current_user)):
    """Return current status of the Avito developments lookup."""
    return {
        "loaded": avito_lookup.is_loaded,
        "entry_count": avito_lookup.entry_count,
        "file_exists": avito_lookup._loaded,
        "source_url": AVITO_DEV_URL,
    }


@router.post("/avito-developments/upload")
async def upload_avito_developments(
    file: UploadFile = File(...),
    _=Depends(get_current_user),
):
    """Upload New_developments.xml from Avito. Replaces the existing lookup."""
    if not file.filename or not file.filename.endswith(".xml"):
        raise HTTPException(status_code=400, detail="Ожидается XML файл")

    data = await file.read()
    if len(data) > AVITO_DEV_MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 50 МБ)")

    count = avito_lookup.load_from_bytes(data)
    if count == 0:
        raise HTTPException(status_code=422, detail="Не удалось распарсить XML — проверьте формат файла")

    # Save to disk for persistence across restarts
    avito_lookup.save_to_disk(data)

    logger.info(f"Avito developments uploaded: {count} entries, {len(data)} bytes")
    return {
        "success": True,
        "entry_count": count,
        "size_bytes": len(data),
        "message": f"Справочник загружен: {count} записей",
    }


@router.post("/avito-developments/download")
async def download_avito_developments(_=Depends(get_current_user)):
    """Download New_developments.xml directly from Avito servers."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(AVITO_DEV_URL, follow_redirects=True)
            resp.raise_for_status()
            data = resp.content
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Авито вернул ошибку: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка скачивания: {e}")

    count = avito_lookup.load_from_bytes(data)
    if count == 0:
        raise HTTPException(status_code=422, detail="Не удалось распарсить XML от Авито")

    avito_lookup.save_to_disk(data)
    logger.info(f"Avito developments downloaded: {count} entries, {len(data)} bytes")

    return {
        "success": True,
        "entry_count": count,
        "size_bytes": len(data),
        "message": f"Справочник скачан с Авито: {count} записей",
    }
