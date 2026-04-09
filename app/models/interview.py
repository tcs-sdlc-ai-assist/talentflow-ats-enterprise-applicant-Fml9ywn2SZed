from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    interviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    rating = Column(Integer, nullable=True)
    feedback_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    application = relationship(
        "Application",
        back_populates="interviews",
        foreign_keys=[application_id],
        lazy="selectin",
    )

    interviewer = relationship(
        "User",
        back_populates="interviews",
        foreign_keys=[interviewer_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Interview(id={self.id}, application_id={self.application_id}, "
            f"interviewer_id={self.interviewer_id}, scheduled_at={self.scheduled_at}, "
            f"rating={self.rating})>"
        )