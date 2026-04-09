import logging
from typing import Optional

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate
from app.models.skill import Skill, candidate_skills

logger = logging.getLogger(__name__)


async def get_or_create_skill(db: AsyncSession, skill_name: str) -> Skill:
    """Get an existing skill by name or create a new one.

    Args:
        db: Async database session.
        skill_name: The skill name to look up or create.

    Returns:
        The Skill object.
    """
    name = skill_name.strip()
    if not name:
        raise ValueError("Skill name cannot be empty.")

    result = await db.execute(select(Skill).where(Skill.name == name))
    skill = result.scalars().first()

    if skill is not None:
        return skill

    skill = Skill(name=name)
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    logger.debug("Created new skill: %s (id=%d)", skill.name, skill.id)
    return skill


async def parse_and_sync_skills(
    db: AsyncSession,
    candidate: Candidate,
    skills_csv: Optional[str],
) -> list[Skill]:
    """Parse a comma-separated skills string and sync them to a candidate.

    Existing skills are matched by name (case-sensitive). New skills are created.
    The candidate's skills list is replaced with the parsed set.

    Args:
        db: Async database session.
        candidate: The Candidate object to update.
        skills_csv: Comma-separated skill names, or None/empty to clear skills.

    Returns:
        The list of Skill objects now associated with the candidate.
    """
    if not skills_csv or not skills_csv.strip():
        candidate.skills = []
        return []

    skill_names = [s.strip() for s in skills_csv.split(",") if s.strip()]
    if not skill_names:
        candidate.skills = []
        return []

    skills: list[Skill] = []
    for name in skill_names:
        skill = await get_or_create_skill(db, name)
        skills.append(skill)

    candidate.skills = skills
    return skills


async def create_candidate(
    db: AsyncSession,
    first_name: str,
    last_name: str,
    email: str,
    phone: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    resume_text: Optional[str] = None,
    skills_csv: Optional[str] = None,
) -> tuple[Optional[Candidate], Optional[str]]:
    """Create a new candidate profile.

    Args:
        db: Async database session.
        first_name: Candidate first name.
        last_name: Candidate last name.
        email: Candidate email address (must be unique).
        phone: Optional phone number.
        linkedin_url: Optional LinkedIn profile URL.
        resume_text: Optional resume text or summary.
        skills_csv: Optional comma-separated skill names.

    Returns:
        A tuple of (Candidate, None) on success, or (None, error_message) on failure.
    """
    if not first_name or not first_name.strip():
        return None, "First name is required."

    if not last_name or not last_name.strip():
        return None, "Last name is required."

    if not email or "@" not in email:
        return None, "A valid email address is required."

    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()

    try:
        existing = await db.execute(
            select(Candidate).where(Candidate.email == email)
        )
        if existing.scalars().first() is not None:
            logger.info(
                "Candidate creation failed: email '%s' already exists.", email
            )
            return None, "A candidate with this email already exists."

        candidate = Candidate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone.strip() if phone else None,
            linkedin_url=linkedin_url.strip() if linkedin_url else None,
            resume_text=resume_text if resume_text else None,
        )
        db.add(candidate)
        await db.flush()
        await db.refresh(candidate)

        await parse_and_sync_skills(db, candidate, skills_csv)
        await db.flush()
        await db.refresh(candidate)

        logger.info(
            "Candidate created: %s %s (id=%d, email=%s)",
            candidate.first_name,
            candidate.last_name,
            candidate.id,
            candidate.email,
        )
        return candidate, None
    except Exception:
        logger.exception("Error creating candidate: %s %s", first_name, last_name)
        return None, "An unexpected error occurred while creating the candidate."


async def edit_candidate(
    db: AsyncSession,
    candidate_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    resume_text: Optional[str] = None,
    skills_csv: Optional[str] = None,
) -> tuple[Optional[Candidate], Optional[str]]:
    """Update an existing candidate profile.

    Args:
        db: Async database session.
        candidate_id: The candidate's primary key.
        first_name: Updated first name (if provided).
        last_name: Updated last name (if provided).
        email: Updated email (if provided, must be unique).
        phone: Updated phone number.
        linkedin_url: Updated LinkedIn URL.
        resume_text: Updated resume text.
        skills_csv: Updated comma-separated skill names.

    Returns:
        A tuple of (Candidate, None) on success, or (None, error_message) on failure.
    """
    try:
        result = await db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(selectinload(Candidate.skills))
        )
        candidate = result.scalars().first()

        if candidate is None:
            return None, "Candidate not found."

        if first_name is not None:
            if not first_name.strip():
                return None, "First name is required."
            candidate.first_name = first_name.strip()

        if last_name is not None:
            if not last_name.strip():
                return None, "Last name is required."
            candidate.last_name = last_name.strip()

        if email is not None:
            email = email.strip().lower()
            if not email or "@" not in email:
                return None, "A valid email address is required."

            if email != candidate.email:
                existing = await db.execute(
                    select(Candidate).where(
                        Candidate.email == email,
                        Candidate.id != candidate_id,
                    )
                )
                if existing.scalars().first() is not None:
                    return None, "A candidate with this email already exists."
                candidate.email = email

        if phone is not None:
            candidate.phone = phone.strip() if phone.strip() else None

        if linkedin_url is not None:
            candidate.linkedin_url = linkedin_url.strip() if linkedin_url.strip() else None

        if resume_text is not None:
            candidate.resume_text = resume_text if resume_text.strip() else None

        if skills_csv is not None:
            await parse_and_sync_skills(db, candidate, skills_csv)

        await db.flush()
        await db.refresh(candidate)

        logger.info(
            "Candidate updated: %s %s (id=%d)",
            candidate.first_name,
            candidate.last_name,
            candidate.id,
        )
        return candidate, None
    except Exception:
        logger.exception("Error updating candidate id=%d", candidate_id)
        return None, "An unexpected error occurred while updating the candidate."


async def get_candidate_by_id(
    db: AsyncSession,
    candidate_id: int,
) -> Optional[Candidate]:
    """Fetch a candidate by their ID with all relationships loaded.

    Args:
        db: Async database session.
        candidate_id: The candidate's primary key.

    Returns:
        The Candidate object if found, None otherwise.
    """
    try:
        result = await db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.skills),
                selectinload(Candidate.applications),
            )
        )
        candidate = result.scalars().first()
        if candidate is None:
            logger.debug("Candidate not found: id=%d", candidate_id)
        return candidate
    except Exception:
        logger.exception("Error fetching candidate id=%d", candidate_id)
        return None


async def list_candidates(
    db: AsyncSession,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Candidate], int]:
    """List candidates with optional search and pagination.

    Search matches against first name, last name, email, and skill names.

    Args:
        db: Async database session.
        search: Optional search query string.
        page: Page number (1-indexed).
        per_page: Number of results per page.

    Returns:
        A tuple of (list of Candidate objects, total count).
    """
    try:
        query = select(Candidate).options(
            selectinload(Candidate.skills),
            selectinload(Candidate.applications),
        )
        count_query = select(func.count(Candidate.id))

        if search and search.strip():
            search_term = f"%{search.strip()}%"
            skill_subquery = (
                select(candidate_skills.c.candidate_id)
                .join(Skill, Skill.id == candidate_skills.c.skill_id)
                .where(Skill.name.ilike(search_term))
            )
            search_filter = or_(
                Candidate.first_name.ilike(search_term),
                Candidate.last_name.ilike(search_term),
                Candidate.email.ilike(search_term),
                Candidate.id.in_(skill_subquery),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0

        offset = (page - 1) * per_page
        query = query.order_by(Candidate.created_at.desc()).offset(offset).limit(per_page)

        result = await db.execute(query)
        candidates = list(result.scalars().unique().all())

        return candidates, total_count
    except Exception:
        logger.exception("Error listing candidates (search=%s, page=%d)", search, page)
        return [], 0


async def manage_skill_tags(
    db: AsyncSession,
    candidate_id: int,
    skills_csv: str,
) -> tuple[Optional[Candidate], Optional[str]]:
    """Update the skill tags for a candidate.

    This is a convenience wrapper around parse_and_sync_skills.

    Args:
        db: Async database session.
        candidate_id: The candidate's primary key.
        skills_csv: Comma-separated skill names.

    Returns:
        A tuple of (Candidate, None) on success, or (None, error_message) on failure.
    """
    try:
        result = await db.execute(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(selectinload(Candidate.skills))
        )
        candidate = result.scalars().first()

        if candidate is None:
            return None, "Candidate not found."

        await parse_and_sync_skills(db, candidate, skills_csv)
        await db.flush()
        await db.refresh(candidate)

        logger.info(
            "Skills updated for candidate id=%d: %s",
            candidate.id,
            skills_csv,
        )
        return candidate, None
    except Exception:
        logger.exception("Error managing skills for candidate id=%d", candidate_id)
        return None, "An unexpected error occurred while updating skills."


async def check_duplicate_candidate(
    db: AsyncSession,
    email: str,
    exclude_id: Optional[int] = None,
) -> bool:
    """Check if a candidate with the given email already exists.

    Args:
        db: Async database session.
        email: Email address to check.
        exclude_id: Optional candidate ID to exclude from the check (for edits).

    Returns:
        True if a duplicate exists, False otherwise.
    """
    try:
        email = email.strip().lower()
        query = select(Candidate).where(Candidate.email == email)
        if exclude_id is not None:
            query = query.where(Candidate.id != exclude_id)

        result = await db.execute(query)
        return result.scalars().first() is not None
    except Exception:
        logger.exception("Error checking duplicate candidate email: %s", email)
        return False