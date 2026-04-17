"""Source model — configuration of each developer's feed.

A Source represents a data channel (URL / file) — NOT a single residential
complex (ЖК).  One source may contain data for multiple complexes; the ЖК
name is an attribute of each Object, not of the Source.
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="Human-readable source name")
    developer_name = Column(String(255), nullable=False, comment="Developer company name")
    type = Column(
        String(50), nullable=False,
        comment="Feed type: yandex, avito, avito_builder, cian, domclick, domclick_pro, custom_xml, excel"
    )
    url = Column(Text, nullable=True, comment="URL to fetch feed from (HTTP/FTP)")
    format = Column(String(50), nullable=True, comment="File format hint")
    mapping_config = Column(JSON, nullable=True, comment="XPath / column mapping for custom formats")
    is_active = Column(Boolean, default=True, nullable=False)
    phone_override = Column(String(20), nullable=True, comment="Override contact phone for all objects")

    # Sync state
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_object_count = Column(Integer, nullable=True, comment="Object count from last successful sync")
    consecutive_failures = Column(Integer, default=0)

    # Availability status: ok / warning / error / unknown
    status = Column(String(20), default="unknown", nullable=False,
                    comment="Last pre-flight result: ok/warning/error/unknown")

    # Feed cache — path to the last successfully downloaded raw feed file
    cache_last_path = Column(Text, nullable=True,
                             comment="Filesystem path to latest cached feed file")
    cache_last_success_at = Column(DateTime(timezone=True), nullable=True,
                                   comment="When the cache was last successfully updated")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Source id={self.id} name='{self.name}' type='{self.type}' status='{self.status}'>"
