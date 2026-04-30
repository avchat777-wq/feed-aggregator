"""DevelopmentIdMapping model — manual override for NewDevelopmentId → JK name."""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class DevelopmentIdMapping(Base):
    __tablename__ = "development_id_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    development_id = Column(String(50), unique=True, nullable=False, index=True,
                            comment="NewDevelopmentId from Avito feed")
    jk_name = Column(String(255), nullable=False, comment="Resolved JK name")
    notes = Column(Text, nullable=True, comment="Admin notes, e.g. address hint")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    def __repr__(self):
        return f"<DevelopmentIdMapping id={self.development_id!r} jk={self.jk_name!r}>"
