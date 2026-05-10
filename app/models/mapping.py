"""Mapping model — custom field mapping configurations for custom XML/Excel sources."""

from sqlalchemy import Column, Integer, String, ForeignKey, Text
from app.database import Base


class Mapping(Base):
    __tablename__ = "mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    source_field = Column(String(255), nullable=False,
                          comment="XPath expression or column name in source")
    target_field = Column(String(100), nullable=False,
                          comment="UnifiedObject field name")
    transform_rule = Column(Text, nullable=True,
                            comment="Optional transform: regex, mapping dict, formula")

    def __repr__(self):
        return f"<Mapping src={self.source_id} '{self.source_field}' -> '{self.target_field}'>"
