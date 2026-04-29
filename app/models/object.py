"""Object model — unified real-estate object registry with history tracking."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime, Numeric,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from app.database import Base


class Object(Base):
    __tablename__ = "objects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=False, index=True,
                         comment="Stable ExternalId: {dev_code}-{jk_code}-{seq}")
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    source_object_id = Column(String(255), nullable=False,
                              comment="Original ID from developer's feed")
    developer_name = Column(String(255), nullable=False)
    jk_name = Column(String(255), nullable=False, comment="Residential complex name")
    jk_id_cian = Column(Integer, nullable=True, comment="CIAN JK database ID")
    house_name = Column(String(255), nullable=True, comment="Building / corpus / liter")
    section_number = Column(String(50), nullable=True)
    flat_number = Column(String(50), nullable=False, comment="Apartment number")
    floor = Column(Integer, nullable=False)
    floors_total = Column(Integer, nullable=True)
    rooms = Column(Integer, nullable=False, comment="0 = studio")
    total_area = Column(Numeric(10, 1), nullable=False)
    living_area = Column(Numeric(10, 1), nullable=True)
    kitchen_area = Column(Numeric(10, 1), nullable=True)
    price = Column(Integer, nullable=False, comment="Price in rubles")
    price_per_sqm = Column(Integer, nullable=True, comment="Auto-calculated")
    sale_type = Column(String(50), nullable=True, comment="DDU, assignment, pdkp")
    decoration = Column(String(50), nullable=True, comment="without, rough, fine, turnkey")
    is_euro = Column(Boolean, nullable=True)
    is_apartments = Column(Boolean, nullable=True)
    address = Column(Text, nullable=True, comment="Street address (from feed)")
    description = Column(Text, nullable=True)
    photos = Column(ARRAY(Text), nullable=True, comment="Array of photo URLs")
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    object_type = Column(String(50), nullable=False, default="квартира",
                         server_default="квартира",
                         comment="квартира / кладовка / машиноместо / апартаменты")
    phone = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active",
                    comment="active, booked, sold, removed")
    hash = Column(String(64), nullable=True, comment="SHA256 of key fields for change detection")
    missing_count = Column(Integer, default=0, comment="Consecutive sync misses")
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    removed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_objects_composite_key", "source_id", "jk_name", "house_name", "flat_number"),
        Index("ix_objects_source_floor_area", "source_id", "jk_name", "floor", "total_area", "rooms"),
        Index("ix_objects_status", "status"),
    )

    def __repr__(self):
        return f"<Object id={self.id} ext='{self.external_id}' jk='{self.jk_name}' flat='{self.flat_number}'>"


class ObjectHistory(Base):
    __tablename__ = "object_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object_id = Column(Integer, ForeignKey("objects.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ObjectHistory obj={self.object_id} field='{self.field_name}'>"
