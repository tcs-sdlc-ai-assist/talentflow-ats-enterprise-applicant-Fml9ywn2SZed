from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(128), nullable=False)
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    user = relationship(
        "User",
        back_populates="activity_logs",
        foreign_keys=[user_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityLog(id={self.id}, action='{self.action}', "
            f"entity_type='{self.entity_type}', entity_id={self.entity_id}, "
            f"user_id={self.user_id})>"
        )