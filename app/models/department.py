from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)

    job_postings = relationship(
        "JobPosting",
        back_populates="department",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, name='{self.name}')>"