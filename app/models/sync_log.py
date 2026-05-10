"""Sync log model — journal of every synchronization cycle."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True,
                       comment="NULL for global sync log entry")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    objects_total = Column(Integer, default=0)
    objects_new = Column(Integer, default=0)
    objects_updated = Column(Integer, default=0)
    objects_removed = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    status = Column(String(20), default="running", comment="running, success, partial, fail")
    details = Column(Text, nullable=True, comment="Error details / summary")
    http_status = Column(Integer, nullable=True, comment="HTTP response status from source")
    response_time_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<SyncLog id={self.id} source={self.source_id} status='{self.status}'>"
