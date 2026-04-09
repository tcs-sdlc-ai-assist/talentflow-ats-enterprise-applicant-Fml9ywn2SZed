import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(
        String(32),
        nullable=False,
        default="interviewer",
        index=True,
    )
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    job_postings = relationship(
        "JobPosting",
        back_populates="hiring_manager",
        foreign_keys="[JobPosting.hiring_manager_id]",
        lazy="selectin",
    )

    interviews = relationship(
        "Interview",
        back_populates="interviewer",
        foreign_keys="[Interview.interviewer_id]",
        lazy="selectin",
    )

    activity_logs = relationship(
        "ActivityLog",
        back_populates="user",
        foreign_keys="[ActivityLog.user_id]",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"