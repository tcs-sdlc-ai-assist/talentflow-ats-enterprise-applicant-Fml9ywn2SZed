import logging
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job_posting import JobPosting
from app.models.department import Department
from app.models.user import User

logger = logging.getLogger(__name__)

VALID_STATUSES = ["Draft", "Published", "Closed"]
VALID_JOB_TYPES = ["Full-Time", "Part-Time", "Contract", "Internship", "Remote"]
ROLES_CAN_MANAGE_JOBS = ["admin", "hiring_manager", "recruiter"]


async def list_jobs(
    db: AsyncSession,
    user: Optional[User] = None,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> list[JobPosting]:
    """List job postings with optional search and status filtering.

    Args:
        db: Async database session.
        user: Current user (used for role-based filtering).
        search: Optional search term for title, location, or description.
        status_filter: Optional status to filter by.

    Returns:
        List of JobPosting objects matching the criteria.
    """
    try:
        stmt = select(JobPosting).options(
            selectinload(JobPosting.department),
            selectinload(JobPosting.hiring_manager),
            selectinload(JobPosting.applications),
        )

        if status_filter and status_filter in VALID_STATUSES:
            stmt = stmt.where(JobPosting.status == status_filter)

        if search:
            search_term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    JobPosting.title.ilike(search_term),
                    JobPosting.location.ilike(search_term),
                    JobPosting.description.ilike(search_term),
                )
            )

        if user and user.role == "hiring_manager":
            stmt = stmt.where(JobPosting.hiring_manager_id == user.id)

        stmt = stmt.order_by(JobPosting.created_at.desc())

        result = await db.execute(stmt)
        jobs = result.scalars().all()
        return list(jobs)
    except Exception:
        logger.exception("Error listing job postings")
        return []


async def get_job_by_id(
    db: AsyncSession,
    job_id: int,
) -> Optional[JobPosting]:
    """Fetch a single job posting by ID with all relationships loaded.

    Args:
        db: Async database session.
        job_id: The job posting primary key.

    Returns:
        The JobPosting object if found, None otherwise.
    """
    try:
        stmt = (
            select(JobPosting)
            .where(JobPosting.id == job_id)
            .options(
                selectinload(JobPosting.department),
                selectinload(JobPosting.hiring_manager),
                selectinload(JobPosting.applications),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        logger.exception("Error fetching job posting id=%d", job_id)
        return None


async def create_job(
    db: AsyncSession,
    title: str,
    description: str,
    department_id: int,
    hiring_manager_id: int,
    location: str,
    job_type: str,
    status: str = "Draft",
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    user: Optional[User] = None,
) -> tuple[Optional[JobPosting], Optional[str]]:
    """Create a new job posting.

    Args:
        db: Async database session.
        title: Job title (required, max 128 chars).
        description: Job description (required).
        department_id: FK to departments table.
        hiring_manager_id: FK to users table.
        location: Job location (required, max 64 chars).
        job_type: Employment type (Full-Time, Part-Time, etc.).
        status: Initial status (default Draft).
        salary_min: Optional minimum salary.
        salary_max: Optional maximum salary.
        user: The user performing the action (for RBAC).

    Returns:
        Tuple of (JobPosting, None) on success, or (None, error_message) on failure.
    """
    if user and user.role not in ROLES_CAN_MANAGE_JOBS:
        logger.warning(
            "User %s (role=%s) attempted to create a job posting without permission",
            user.username,
            user.role,
        )
        return None, "You do not have permission to create job postings."

    if not title or not title.strip():
        return None, "Job title is required."

    if len(title.strip()) > 128:
        return None, "Job title must be at most 128 characters."

    if not description or not description.strip():
        return None, "Job description is required."

    if not location or not location.strip():
        return None, "Location is required."

    if len(location.strip()) > 64:
        return None, "Location must be at most 64 characters."

    if job_type and job_type not in VALID_JOB_TYPES:
        return None, f"Invalid job type. Must be one of: {', '.join(VALID_JOB_TYPES)}"

    if status and status not in VALID_STATUSES:
        return None, f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"

    if salary_min is not None and salary_min < 0:
        return None, "Minimum salary cannot be negative."

    if salary_max is not None and salary_max < 0:
        return None, "Maximum salary cannot be negative."

    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        return None, "Minimum salary cannot exceed maximum salary."

    try:
        dept_result = await db.execute(
            select(Department).where(Department.id == department_id)
        )
        if dept_result.scalar_one_or_none() is None:
            return None, "Selected department does not exist."

        mgr_result = await db.execute(
            select(User).where(User.id == hiring_manager_id)
        )
        if mgr_result.scalar_one_or_none() is None:
            return None, "Selected hiring manager does not exist."

        job = JobPosting(
            title=title.strip(),
            description=description.strip(),
            status=status or "Draft",
            department_id=department_id,
            hiring_manager_id=hiring_manager_id,
            location=location.strip(),
            type=job_type or "Full-Time",
            salary_min=salary_min,
            salary_max=salary_max,
        )
        db.add(job)
        await db.flush()
        await db.refresh(job)

        logger.info(
            "Job posting created: id=%d, title='%s', status='%s' by user=%s",
            job.id,
            job.title,
            job.status,
            user.username if user else "system",
        )
        return job, None
    except Exception:
        logger.exception("Error creating job posting")
        return None, "An unexpected error occurred while creating the job posting."


async def edit_job(
    db: AsyncSession,
    job_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    department_id: Optional[int] = None,
    hiring_manager_id: Optional[int] = None,
    location: Optional[str] = None,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    user: Optional[User] = None,
) -> tuple[Optional[JobPosting], Optional[str]]:
    """Update an existing job posting.

    Args:
        db: Async database session.
        job_id: The job posting ID to update.
        title: Updated title (optional).
        description: Updated description (optional).
        department_id: Updated department FK (optional).
        hiring_manager_id: Updated hiring manager FK (optional).
        location: Updated location (optional).
        job_type: Updated job type (optional).
        status: Updated status (optional).
        salary_min: Updated minimum salary (optional).
        salary_max: Updated maximum salary (optional).
        user: The user performing the action (for RBAC).

    Returns:
        Tuple of (JobPosting, None) on success, or (None, error_message) on failure.
    """
    if user and user.role not in ROLES_CAN_MANAGE_JOBS:
        logger.warning(
            "User %s (role=%s) attempted to edit job id=%d without permission",
            user.username,
            user.role,
            job_id,
        )
        return None, "You do not have permission to edit job postings."

    try:
        job = await get_job_by_id(db, job_id)
        if job is None:
            return None, "Job posting not found."

        if user and user.role == "hiring_manager" and job.hiring_manager_id != user.id:
            return None, "You can only edit job postings assigned to you."

        if title is not None:
            if not title.strip():
                return None, "Job title is required."
            if len(title.strip()) > 128:
                return None, "Job title must be at most 128 characters."
            job.title = title.strip()

        if description is not None:
            if not description.strip():
                return None, "Job description is required."
            job.description = description.strip()

        if location is not None:
            if not location.strip():
                return None, "Location is required."
            if len(location.strip()) > 64:
                return None, "Location must be at most 64 characters."
            job.location = location.strip()

        if job_type is not None:
            if job_type not in VALID_JOB_TYPES:
                return None, f"Invalid job type. Must be one of: {', '.join(VALID_JOB_TYPES)}"
            job.type = job_type

        if status is not None:
            if status not in VALID_STATUSES:
                return None, f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"
            job.status = status

        if department_id is not None:
            dept_result = await db.execute(
                select(Department).where(Department.id == department_id)
            )
            if dept_result.scalar_one_or_none() is None:
                return None, "Selected department does not exist."
            job.department_id = department_id

        if hiring_manager_id is not None:
            mgr_result = await db.execute(
                select(User).where(User.id == hiring_manager_id)
            )
            if mgr_result.scalar_one_or_none() is None:
                return None, "Selected hiring manager does not exist."
            job.hiring_manager_id = hiring_manager_id

        effective_salary_min = salary_min if salary_min is not None else job.salary_min
        effective_salary_max = salary_max if salary_max is not None else job.salary_max

        if salary_min is not None:
            if salary_min < 0:
                return None, "Minimum salary cannot be negative."
            job.salary_min = salary_min

        if salary_max is not None:
            if salary_max < 0:
                return None, "Maximum salary cannot be negative."
            job.salary_max = salary_max

        if (
            effective_salary_min is not None
            and effective_salary_max is not None
            and effective_salary_min > effective_salary_max
        ):
            return None, "Minimum salary cannot exceed maximum salary."

        await db.flush()
        await db.refresh(job)

        logger.info(
            "Job posting updated: id=%d, title='%s', status='%s' by user=%s",
            job.id,
            job.title,
            job.status,
            user.username if user else "system",
        )
        return job, None
    except Exception:
        logger.exception("Error editing job posting id=%d", job_id)
        return None, "An unexpected error occurred while updating the job posting."


async def toggle_status(
    db: AsyncSession,
    job_id: int,
    new_status: str,
    user: Optional[User] = None,
) -> tuple[Optional[JobPosting], Optional[str]]:
    """Change the status of a job posting.

    Args:
        db: Async database session.
        job_id: The job posting ID.
        new_status: The new status value.
        user: The user performing the action (for RBAC).

    Returns:
        Tuple of (JobPosting, None) on success, or (None, error_message) on failure.
    """
    if new_status not in VALID_STATUSES:
        return None, f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"

    return await edit_job(db, job_id, status=new_status, user=user)


async def get_open_jobs(
    db: AsyncSession,
) -> list[JobPosting]:
    """Fetch all published (open) job postings.

    Args:
        db: Async database session.

    Returns:
        List of published JobPosting objects.
    """
    try:
        stmt = (
            select(JobPosting)
            .where(JobPosting.status == "Published")
            .options(
                selectinload(JobPosting.department),
                selectinload(JobPosting.hiring_manager),
                selectinload(JobPosting.applications),
            )
            .order_by(JobPosting.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception:
        logger.exception("Error fetching open job postings")
        return []


async def get_jobs_by_hiring_manager(
    db: AsyncSession,
    hiring_manager_id: int,
) -> list[JobPosting]:
    """Fetch all job postings for a specific hiring manager.

    Args:
        db: Async database session.
        hiring_manager_id: The hiring manager's user ID.

    Returns:
        List of JobPosting objects for the given hiring manager.
    """
    try:
        stmt = (
            select(JobPosting)
            .where(JobPosting.hiring_manager_id == hiring_manager_id)
            .options(
                selectinload(JobPosting.department),
                selectinload(JobPosting.hiring_manager),
                selectinload(JobPosting.applications),
            )
            .order_by(JobPosting.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception:
        logger.exception(
            "Error fetching jobs for hiring manager id=%d", hiring_manager_id
        )
        return []


async def get_all_departments(
    db: AsyncSession,
) -> list[Department]:
    """Fetch all departments.

    Args:
        db: Async database session.

    Returns:
        List of all Department objects.
    """
    try:
        result = await db.execute(
            select(Department).order_by(Department.name)
        )
        return list(result.scalars().all())
    except Exception:
        logger.exception("Error fetching departments")
        return []


async def get_hiring_managers(
    db: AsyncSession,
) -> list[User]:
    """Fetch all users who can be assigned as hiring managers.

    Returns users with roles: admin, hiring_manager, recruiter.

    Args:
        db: Async database session.

    Returns:
        List of User objects eligible to be hiring managers.
    """
    try:
        stmt = (
            select(User)
            .where(
                User.is_active == 1,
                User.role.in_(["admin", "hiring_manager", "recruiter"]),
            )
            .order_by(User.username)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception:
        logger.exception("Error fetching hiring managers")
        return []


async def count_open_jobs(
    db: AsyncSession,
) -> int:
    """Count the number of published job postings.

    Args:
        db: Async database session.

    Returns:
        Integer count of published jobs.
    """
    try:
        from sqlalchemy import func

        stmt = select(func.count(JobPosting.id)).where(
            JobPosting.status == "Published"
        )
        result = await db.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception("Error counting open jobs")
        return 0