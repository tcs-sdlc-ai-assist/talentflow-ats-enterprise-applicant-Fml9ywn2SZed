from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="Draft", index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    hiring_manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    location = Column(String(64), nullable=False)
    type = Column(String(32), nullable=False, default="Full-Time")
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    department = relationship(
        "Department",
        back_populates="job_postings",
        lazy="selectin",
    )

    hiring_manager = relationship(
        "User",
        back_populates="job_postings",
        foreign_keys=[hiring_manager_id],
        lazy="selectin",
    )

    applications = relationship(
        "Application",
        back_populates="job_posting",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<JobPosting(id={self.id}, title='{self.title}', status='{self.status}')>"