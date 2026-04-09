from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.skill import candidate_skills


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    email = Column(String(128), unique=True, nullable=False, index=True)
    phone = Column(String(32), nullable=True)
    linkedin_url = Column(String(256), nullable=True)
    resume_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    skills = relationship(
        "Skill",
        secondary=candidate_skills,
        back_populates="candidates",
        lazy="selectin",
    )

    applications = relationship(
        "Application",
        back_populates="candidate",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, name='{self.first_name} {self.last_name}', email='{self.email}')>"