"""Admin API — system-level operations (file uploads, lookup management, etc.)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import async_session
from app.models.development_mapping import DevelopmentIdMapping
from app.models.jk_coordinate import JkCoordinate
from app.models.object import Object
from app.services.avito_lookup import avito_lookup, AVITO_DEV_URL
from app.services.dev_id_mapping import dev_id_mapping

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

AVITO_DEV_MAX_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Avito New Developments directory ──────────────────────────────────────────

@router.get("/avito-developments/status")
async def avito_developments_status(_=Depends(get_current_user)):
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
    if not file.filename or not file.filename.endswith(".xml"):
        raise HTTPException(status_code=400, detail="Ожидается XML файл")

    data = await file.read()
    if len(data) > AVITO_DEV_MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 50 МБ)")

    count = avito_lookup.load_from_bytes(data)
    if count == 0:
        raise HTTPException(status_code=422, detail="Не удалось распарсить XML — проверьте формат файла")

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


# ── Development ID mappings ────────────────────────────────────────────────────

class DevIdMappingIn(BaseModel):
    development_id: str
    jk_name: str
    notes: Optional[str] = None


@router.get("/dev-id-mappings")
async def list_dev_id_mappings(_=Depends(get_current_user)):
    """List all saved development_id → jk_name mappings."""
    async with async_session() as session:
        result = await session.execute(
            select(DevelopmentIdMapping).order_by(DevelopmentIdMapping.development_id)
        )
        rows = result.scalars().all()
        return [
            {
                "development_id": r.development_id,
                "jk_name": r.jk_name,
                "notes": r.notes,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]


@router.post("/dev-id-mappings")
async def save_dev_id_mapping(
    payload: DevIdMappingIn,
    _=Depends(get_current_user),
):
    """Create or update a development_id → jk_name mapping.

    Also immediately applies the jk_name to all existing objects in DB
    that have this development_id but empty jk_name — prevents duplicates
    on the next sync cycle.
    """
    dev_id = payload.development_id.strip()
    jk = payload.jk_name.strip()
    if not dev_id or not jk:
        raise HTTPException(status_code=400, detail="development_id и jk_name обязательны")

    async with async_session() as session:
        result = await session.execute(
            select(DevelopmentIdMapping).where(
                DevelopmentIdMapping.development_id == dev_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.jk_name = jk
            existing.notes = payload.notes
        else:
            session.add(DevelopmentIdMapping(
                development_id=dev_id,
                jk_name=jk,
                notes=payload.notes,
            ))

        # Immediately patch existing objects that have this dev_id but no jk_name.
        # jk_id_cian is Integer in the DB, so cast dev_id to int before comparing.
        patched_count = 0
        try:
            dev_id_int = int(dev_id)
            upd = (
                update(Object)
                .where(
                    and_(
                        Object.jk_id_cian == dev_id_int,
                        (Object.jk_name == "") | Object.jk_name.is_(None),
                    )
                )
                .values(jk_name=jk)
            )
            upd_result = await session.execute(upd)
            patched_count = upd_result.rowcount
        except (ValueError, TypeError):
            pass  # non-numeric dev_id — no objects to patch

        await session.commit()

        # Reload in-memory lookup
        await dev_id_mapping.reload(session)

    logger.info(
        f"DevIdMapping saved: {dev_id!r} → {jk!r}, "
        f"patched {patched_count} existing objects"
    )
    return {
        "success": True,
        "development_id": dev_id,
        "jk_name": jk,
        "patched_objects": patched_count,
    }


@router.post("/dev-id-mappings/reapply-all")
async def reapply_all_dev_id_mappings(_=Depends(get_current_user)):
    """Reapply all saved dev_id_mappings to existing objects in DB.

    Useful after bulk-importing mappings: patches every object that has a
    known jk_id_cian but still carries an empty jk_name.
    """
    async with async_session() as session:
        result = await session.execute(select(DevelopmentIdMapping))
        mappings = result.scalars().all()

        total_patched = 0
        details = []
        for m in mappings:
            try:
                dev_id_int = int(m.development_id)
            except (ValueError, TypeError):
                continue  # skip non-numeric IDs
            upd = (
                update(Object)
                .where(
                    and_(
                        Object.jk_id_cian == dev_id_int,
                        (Object.jk_name == "") | Object.jk_name.is_(None),
                    )
                )
                .values(jk_name=m.jk_name)
            )
            r = await session.execute(upd)
            if r.rowcount:
                details.append({"development_id": m.development_id, "jk_name": m.jk_name, "patched": r.rowcount})
                total_patched += r.rowcount

        await session.commit()

    logger.info(f"Reapply-all: patched {total_patched} objects across {len(details)} mappings")
    return {"success": True, "total_patched": total_patched, "details": details}


@router.delete("/dev-id-mappings/{development_id}")
async def delete_dev_id_mapping(
    development_id: str,
    _=Depends(get_current_user),
):
    """Delete a development_id mapping."""
    async with async_session() as session:
        result = await session.execute(
            select(DevelopmentIdMapping).where(
                DevelopmentIdMapping.development_id == development_id
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Маппинг не найден")
        await session.delete(row)
        await session.commit()
        await dev_id_mapping.reload(session)

    return {"success": True}


@router.get("/unresolved-ids")
async def get_unresolved_ids(_=Depends(get_current_user)):
    """Return NewDevelopmentIds that have objects without JK name in DB.

    Shows: development_id, object count, sample address, developer name.
    Excludes IDs that are already in dev_id_mappings table.
    """
    async with async_session() as session:
        # Objects with empty jk_name but with jk_id_cian (= NewDevelopmentId)
        stmt = (
            select(
                Object.jk_id_cian,
                func.count(Object.id).label("object_count"),
                func.min(Object.address).label("sample_address"),
                func.min(Object.developer_name).label("developer_name"),
                func.min(Object.object_type).label("sample_object_type"),
            )
            .where(
                and_(
                    Object.jk_id_cian.isnot(None),
                    Object.status != "removed",
                    (Object.jk_name == "") | Object.jk_name.is_(None),
                )
            )
            .group_by(Object.jk_id_cian)
            .order_by(func.count(Object.id).desc())
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Get already-mapped IDs
        mapped_result = await session.execute(
            select(DevelopmentIdMapping.development_id)
        )
        already_mapped = {r[0] for r in mapped_result.all()}

        return [
            {
                "development_id": str(row.jk_id_cian),
                "object_count": row.object_count,
                "sample_address": row.sample_address,
                "developer_name": row.developer_name,
                "sample_object_type": row.sample_object_type,
                "already_mapped": str(row.jk_id_cian) in already_mapped,
            }
            for row in rows
        ]


# ── JK Coordinates ────────────────────────────────────────────────────────────

class JkCoordinateIn(BaseModel):
    jk_name: str
    latitude: float
    longitude: float


@router.get("/jk-coordinates")
async def list_jk_coordinates(_=Depends(get_current_user)):
    """List all JK coordinates overrides."""
    async with async_session() as session:
        result = await session.execute(
            select(JkCoordinate).order_by(JkCoordinate.jk_name)
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "jk_name": r.jk_name,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]


@router.post("/jk-coordinates", status_code=201)
async def save_jk_coordinate(
    payload: JkCoordinateIn,
    _=Depends(get_current_user),
):
    """Create or update a JK coordinates record."""
    jk = payload.jk_name.strip()
    if not jk:
        raise HTTPException(status_code=400, detail="jk_name обязателен")

    async with async_session() as session:
        result = await session.execute(
            select(JkCoordinate).where(JkCoordinate.jk_name == jk)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.latitude = payload.latitude
            existing.longitude = payload.longitude
        else:
            session.add(JkCoordinate(
                jk_name=jk,
                latitude=payload.latitude,
                longitude=payload.longitude,
            ))
        await session.commit()

    logger.info(f"JkCoordinate saved: {jk!r} → ({payload.latitude}, {payload.longitude})")
    return {"success": True, "jk_name": jk, "latitude": payload.latitude, "longitude": payload.longitude}


@router.delete("/jk-coordinates/{coord_id}", status_code=204)
async def delete_jk_coordinate(
    coord_id: int,
    _=Depends(get_current_user),
):
    """Delete a JK coordinate record."""
    async with async_session() as session:
        result = await session.execute(
            select(JkCoordinate).where(JkCoordinate.id == coord_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        await session.delete(row)
        await session.commit()
    return
