"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ──────────────────────────── Auth ────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ──────────────────────────── Sources ────────────────────────────

class SourceBase(BaseModel):
    name: str
    developer_name: str
    type: str = Field(
        ...,
        pattern="^(yandex|avito|avito_builder|cian|custom_xml|excel|domclick|domclick_pro)$",
    )
    url: Optional[str] = None
    format: Optional[str] = None
    mapping_config: Optional[dict] = None
    is_active: bool = True
    phone_override: Optional[str] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    developer_name: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    format: Optional[str] = None
    mapping_config: Optional[dict] = None
    is_active: Optional[bool] = None
    phone_override: Optional[str] = None


class SourceResponse(SourceBase):
    id: int
    last_sync_at: Optional[datetime] = None
    last_object_count: Optional[int] = None
    consecutive_failures: int = 0
    status: str = "unknown"           # ok / warning / error / unknown
    cache_last_path: Optional[str] = None
    cache_last_success_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ──────────────────────────── JK stats per source ────────────────────────────

class JkStatItem(BaseModel):
    jk_name: str
    object_count: int
    avg_price: int
    min_price: int
    max_price: int


class SourceJkStatsResponse(BaseModel):
    source_id: int
    source_name: str
    jk_stats: list[JkStatItem]


# ──────────────────────────── Pre-flight diagnostics ────────────────────────────

class DiagnosticsResult(BaseModel):
    source_id: int
    source_name: str
    passed: bool
    checks: dict   # {check_name: {"ok": bool, "detail": str}}
    duration_ms: int


# ──────────────────────────── Objects ────────────────────────────

class ObjectResponse(BaseModel):
    id: int
    external_id: str
    source_id: int
    source_object_id: str
    developer_name: str
    jk_name: str
    jk_id_cian: Optional[int] = None
    house_name: Optional[str] = None
    section_number: Optional[str] = None
    flat_number: str
    floor: int
    floors_total: Optional[int] = None
    rooms: int
    total_area: float
    living_area: Optional[float] = None
    kitchen_area: Optional[float] = None
    price: int
    price_per_sqm: Optional[int] = None
    sale_type: Optional[str] = None
    decoration: Optional[str] = None
    is_euro: Optional[bool] = None
    is_apartments: Optional[bool] = None
    description: Optional[str] = None
    address: Optional[str] = None
    photos: Optional[list[str]] = None
    phone: str
    status: str
    missing_count: int = 0
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ObjectHistoryResponse(BaseModel):
    id: int
    object_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ──────────────────────────── Mappings ────────────────────────────

class MappingBase(BaseModel):
    source_id: int
    source_field: str
    target_field: str
    transform_rule: Optional[str] = None


class MappingCreate(MappingBase):
    pass


class MappingResponse(MappingBase):
    id: int

    model_config = {"from_attributes": True}


# ──────────────────────────── Sync Logs ────────────────────────────

class SyncLogResponse(BaseModel):
    id: int
    source_id: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    objects_total: int = 0
    objects_new: int = 0
    objects_updated: int = 0
    objects_removed: int = 0
    errors_count: int = 0
    status: str = "running"
    details: Optional[str] = None
    http_status: Optional[int] = None
    response_time_ms: Optional[int] = None

    model_config = {"from_attributes": True}


# ──────────────────────────── Alerts ────────────────────────────

class AlertResponse(BaseModel):
    id: int
    type: str
    message: str
    sent_at: Optional[datetime] = None
    telegram_response: Optional[str] = None

    model_config = {"from_attributes": True}


# ──────────────────────────── Dashboard ────────────────────────────

class DashboardStats(BaseModel):
    total_sources: int
    active_sources: int
    total_objects: int
    active_objects: int
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    sources_health: list[SourceHealthItem] = []


class SourceHealthItem(BaseModel):
    source_id: int
    name: str
    status: str  # ok, warning, error
    last_sync: Optional[datetime] = None
    object_count: int = 0
    consecutive_failures: int = 0

    model_config = {"from_attributes": True}


# Fix forward reference
DashboardStats.model_rebuild()


# ──────────────────────────── Notifications settings ────────────────────────────

class NotificationSettings(BaseModel):
    telegram_chat_id: Optional[str] = None
    threshold_drop_warning: int = 20
    threshold_drop_critical: int = 50
    threshold_price_change_pct: int = 15
    threshold_price_change_min: int = 10
    threshold_source_fail_count: int = 2
