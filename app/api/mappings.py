"""Mappings CRUD API for custom XML/Excel field mappings."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import require_admin, get_current_user
from app.models.mapping import Mapping
from app.schemas.schemas import MappingCreate, MappingResponse

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


@router.get("", response_model=list[MappingResponse])
async def list_mappings(
    source_id: int = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Mapping)
    if source_id:
        stmt = stmt.where(Mapping.source_id == source_id)
    stmt = stmt.order_by(Mapping.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=MappingResponse, status_code=201)
async def create_mapping(
    data: MappingCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    mapping = Mapping(**data.model_dump())
    db.add(mapping)
    await db.flush()
    await db.refresh(mapping)
    return mapping


@router.delete("/{mapping_id}", status_code=204)
async def delete_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    result = await db.execute(select(Mapping).where(Mapping.id == mapping_id))
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await db.delete(mapping)
