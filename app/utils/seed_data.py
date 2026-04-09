import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.department import Department
from app.models.skill import Skill

logger = logging.getLogger(__name__)

DEFAULT_DEPARTMENTS = [
    "Engineering",
    "Marketing",
    "Sales",
    "HR",
    "Finance",
    "Operations",
]

DEFAULT_SKILLS = [
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "FastAPI",
    "SQL",
    "PostgreSQL",
    "Docker",
    "Kubernetes",
    "AWS",
    "GCP",
    "Azure",
    "Git",
    "CI/CD",
    "REST APIs",
    "GraphQL",
    "Machine Learning",
    "Data Analysis",
    "Project Management",
    "Agile",
    "Scrum",
    "Communication",
    "Leadership",
    "Problem Solving",
    "Java",
    "Go",
    "Rust",
    "C++",
    "Node.js",
    "Django",
    "Flask",
    "Vue.js",
    "Angular",
    "HTML/CSS",
    "Tailwind CSS",
    "Redis",
    "MongoDB",
    "Elasticsearch",
    "Linux",
    "Networking",
]


async def seed_departments(session: AsyncSession) -> int:
    """Create default departments if they don't already exist.

    Returns the number of departments created.
    """
    created = 0
    for name in DEFAULT_DEPARTMENTS:
        result = await session.execute(
            select(Department).where(Department.name == name)
        )
        existing = result.scalars().first()
        if existing is None:
            department = Department(name=name)
            session.add(department)
            created += 1
            logger.debug("Created department: %s", name)
    if created > 0:
        await session.flush()
        logger.info("Seeded %d new department(s).", created)
    else:
        logger.info("All default departments already exist.")
    return created


async def seed_skills(session: AsyncSession) -> int:
    """Create default skills if they don't already exist.

    Returns the number of skills created.
    """
    created = 0
    for name in DEFAULT_SKILLS:
        result = await session.execute(
            select(Skill).where(Skill.name == name)
        )
        existing = result.scalars().first()
        if existing is None:
            skill = Skill(name=name)
            session.add(skill)
            created += 1
            logger.debug("Created skill: %s", name)
    if created > 0:
        await session.flush()
        logger.info("Seeded %d new skill(s).", created)
    else:
        logger.info("All default skills already exist.")
    return created


async def seed_all(session: Optional[AsyncSession] = None) -> dict[str, int]:
    """Seed all default data (departments and skills).

    If no session is provided, a new session is created from the factory.

    Returns a dict with counts of created departments and skills.
    """
    results: dict[str, int] = {"departments": 0, "skills": 0}

    if session is not None:
        results["departments"] = await seed_departments(session)
        results["skills"] = await seed_skills(session)
        return results

    async with async_session_factory() as new_session:
        try:
            results["departments"] = await seed_departments(new_session)
            results["skills"] = await seed_skills(new_session)
            await new_session.commit()
            logger.info(
                "Seed data complete: %d departments, %d skills created.",
                results["departments"],
                results["skills"],
            )
        except Exception:
            await new_session.rollback()
            logger.exception("Failed to seed data.")
            raise
        finally:
            await new_session.close()

    return results