"""Alert model — log of sent Telegram notifications."""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False, comment="CRITICAL, WARNING, INFO")
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    telegram_response = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Alert id={self.id} type='{self.type}'>"
