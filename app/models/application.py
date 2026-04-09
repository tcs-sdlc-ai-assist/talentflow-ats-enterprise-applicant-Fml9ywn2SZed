from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False)
    stage = Column(
        String(32),
        nullable=False,
        default="Applied",
        index=True,
    )
    applied_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    candidate = relationship(
        "Candidate",
        back_populates="applications",
        foreign_keys=[candidate_id],
        lazy="selectin",
    )

    job_posting = relationship(
        "JobPosting",
        back_populates="applications",
        foreign_keys=[job_id],
        lazy="selectin",
    )

    interviews = relationship(
        "Interview",
        back_populates="application",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Application(id={self.id}, candidate_id={self.candidate_id}, "
            f"job_id={self.job_id}, stage='{self.stage}')>"
        )