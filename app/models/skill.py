from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base

candidate_skills = Table(
    "candidate_skills",
    Base.metadata,
    Column("candidate_id", Integer, ForeignKey("candidates.id"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id"), primary_key=True),
)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)

    candidates = relationship(
        "Candidate",
        secondary=candidate_skills,
        back_populates="skills",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}')>"