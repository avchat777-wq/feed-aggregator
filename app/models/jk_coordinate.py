"""JkCoordinate model — manual lat/lon override per JK name.

When a feed does not provide coordinates (or provides only office-of-sales
coordinates), an administrator can enter precise building coordinates here.
During normalization, if an object's lat/lon are missing, the engine looks
up the object's jk_name in this table and fills the coordinates automatically.

This approach is feed-agnostic: any new source benefits without code changes.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base


class JkCoordinate(Base):
    __tablename__ = "jk_coordinates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jk_name = Column(
        String(512), nullable=False, unique=True,
        comment="Canonical JK name (case-insensitive lookup key)"
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self):
        return f"<JkCoordinate '{self.jk_name}' ({self.latitude}, {self.longitude})>"
