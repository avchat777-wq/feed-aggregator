"""JkSynonym model — dictionary for normalising JK names across feeds.

A single residential complex may arrive under different names in different
feeds (e.g. "ЖК Солнечный", "Солнечный", "Солнечный, корпус 2").
This table maps raw variants to a canonical name so the identifier engine
can match objects across sources correctly.

Usage example:
    raw_name        → normalized_name
    "Солнечный"     → "ЖК Солнечный"
    "Солнечный 2"   → "ЖК Солнечный"
    "жк солнечный"  → "ЖК Солнечный"
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class JkSynonym(Base):
    __tablename__ = "jk_synonyms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String(512), nullable=False, unique=True,
                      comment="Raw name as it appears in the feed (stored lowercase)")
    normalized_name = Column(String(512), nullable=False,
                             comment="Canonical name to use instead")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<JkSynonym '{self.raw_name}' → '{self.normalized_name}'>"
