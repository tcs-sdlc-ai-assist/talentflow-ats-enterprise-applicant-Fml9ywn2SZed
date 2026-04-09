import logging
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.models.user import User

logger = logging.getLogger(__name__)

VALID_STAGES = [
    "Applied",
    "Screening",
    "Interviewing",
    "Offered",
    "Hired",
    "Rejected",
]

ROLES_CAN_MANAGE_APPLICATIONS = ["admin", "recruiter", "hiring_manager"]


async def create_application(
    db: AsyncSession,
    candidate_id: int,
    job_id: int,
    stage: str = "Applied",
    user: Optional[User] = None,
) -> tuple[Optional[Application], Optional[str]]:
    """Create a new application linking a candidate to a job posting.

    Args:
        db: Async database session.
        candidate_id: FK to candidates table.
        job_id: FK to job_postings table.
        stage: Initial pipeline stage (default: Applied).
        user: The user performing the action (for RBAC).

    Returns:
        Tuple of (Application, None) on success, or (None, error_message) on failure.
    """
    if user and user.role not in ROLES_CAN_MANAGE_APPLICATIONS:
        logger.warning(
            "User %s (role=%s) attempted to create an application without permission",
            user.username,
            user.role,
        )
        return None, "You do not have permission to create applications."

    if stage and stage not in VALID_STAGES:
        return None, f"Invalid stage. Must be one of: {', '.join(VALID_STAGES)}"

    try:
        candidate_result = await db.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        if candidate_result.scalar_one_or_none() is None:
            return None, "Candidate not found."

        job_result = await db.execute(
            select(JobPosting).where(JobPosting.id == job_id)
        )
        job = job_result.scalar_one_or_none()
        if job is None:
            return None, "Job posting not found."

        if job.status != "Published":
            return None, "Cannot apply to a job that is not published."

        existing_result = await db.execute(
            select(Application).where(
                Application.candidate_id == candidate_id,
                Application.job_id == job_id,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            return None, "This candidate has already applied to this job."

        application = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            stage=stage or "Applied",
        )
        db.add(application)
        await db.flush()
        await db.refresh(application)

        logger.info(
            "Application created: id=%d, candidate_id=%d, job_id=%d, stage='%s' by user=%s",
            application.id,
            application.candidate_id,
            application.job_id,
            application.stage,
            user.username if user else "system",
        )
        return application, None
    except Exception:
        logger.exception(
            "Error creating application for candidate_id=%d, job_id=%d",
            candidate_id,
            job_id,
        )
        return None, "An unexpected error occurred while creating the application."


async def get_application_by_id(
    db: AsyncSession,
    application_id: int,
) -> Optional[Application]:
    """Fetch a single application by ID with all relationships loaded.

    Args:
        db: Async database session.
        application_id: The application primary key.

    Returns:
        The Application object if found, None otherwise.
    """
    try:
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Application.interviews),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        logger.exception("Error fetching application id=%d", application_id)
        return None


async def update_stage(
    db: AsyncSession,
    application_id: int,
    new_stage: str,
    user: Optional[User] = None,
) -> tuple[Optional[Application], Optional[str]]:
    """Update the pipeline stage of an application.

    Args:
        db: Async database session.
        application_id: The application ID to update.
        new_stage: The new stage value.
        user: The user performing the action (for RBAC).

    Returns:
        Tuple of (Application, None) on success, or (None, error_message) on failure.
    """
    if user and user.role not in ROLES_CAN_MANAGE_APPLICATIONS:
        logger.warning(
            "User %s (role=%s) attempted to update application stage without permission",
            user.username,
            user.role,
        )
        return None, "You do not have permission to update application stages."

    if new_stage not in VALID_STAGES:
        return None, f"Invalid stage. Must be one of: {', '.join(VALID_STAGES)}"

    try:
        application = await get_application_by_id(db, application_id)
        if application is None:
            return None, "Application not found."

        old_stage = application.stage
        application.stage = new_stage

        await db.flush()
        await db.refresh(application)

        logger.info(
            "Application id=%d stage updated: '%s' -> '%s' by user=%s",
            application.id,
            old_stage,
            new_stage,
            user.username if user else "system",
        )
        return application, None
    except Exception:
        logger.exception("Error updating stage for application id=%d", application_id)
        return None, "An unexpected error occurred while updating the application stage."


async def get_kanban_board(
    db: AsyncSession,
    job_id: Optional[int] = None,
    user: Optional[User] = None,
) -> dict:
    """Build a Kanban board grouping applications by stage.

    Args:
        db: Async database session.
        job_id: Optional job ID to filter applications.
        user: Current user (for role-based filtering).

    Returns:
        A dict with keys:
            board: dict mapping stage names to lists of Application objects.
            jobs: list of JobPosting objects for the filter dropdown.
            total_applications: total count of applications on the board.
            selected_job_id: the job_id filter applied (or None).
    """
    try:
        board: dict[str, list[Application]] = {stage: [] for stage in VALID_STAGES}

        stmt = (
            select(Application)
            .options(
                selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Application.interviews),
            )
        )

        if job_id:
            stmt = stmt.where(Application.job_id == job_id)

        if user and user.role == "hiring_manager":
            stmt = stmt.join(JobPosting, Application.job_id == JobPosting.id).where(
                JobPosting.hiring_manager_id == user.id
            )

        stmt = stmt.order_by(Application.applied_at.desc())

        result = await db.execute(stmt)
        applications = result.scalars().unique().all()

        total_applications = 0
        for app in applications:
            stage_key = app.stage if app.stage in VALID_STAGES else "Applied"
            board[stage_key].append(app)
            total_applications += 1

        jobs_stmt = (
            select(JobPosting)
            .options(
                selectinload(JobPosting.department),
            )
            .order_by(JobPosting.created_at.desc())
        )

        if user and user.role == "hiring_manager":
            jobs_stmt = jobs_stmt.where(JobPosting.hiring_manager_id == user.id)

        jobs_result = await db.execute(jobs_stmt)
        jobs = list(jobs_result.scalars().all())

        return {
            "board": board,
            "jobs": jobs,
            "total_applications": total_applications,
            "selected_job_id": job_id,
        }
    except Exception:
        logger.exception("Error building Kanban board (job_id=%s)", job_id)
        return {
            "board": {stage: [] for stage in VALID_STAGES},
            "jobs": [],
            "total_applications": 0,
            "selected_job_id": job_id,
        }


async def list_applications(
    db: AsyncSession,
    search: Optional[str] = None,
    stage_filter: Optional[str] = None,
    job_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 25,
    user: Optional[User] = None,
) -> tuple[list[Application], int]:
    """List applications with optional filtering and pagination.

    Args:
        db: Async database session.
        search: Optional search term for candidate name or job title.
        stage_filter: Optional stage to filter by.
        job_id: Optional job ID to filter by.
        page: Page number (1-indexed).
        per_page: Number of results per page.
        user: Current user (for role-based filtering).

    Returns:
        A tuple of (list of Application objects, total count).
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 25

    try:
        base_query = (
            select(Application)
            .join(Candidate, Application.candidate_id == Candidate.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
            .options(
                selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Application.interviews),
            )
        )

        count_query = (
            select(func.count(Application.id))
            .join(Candidate, Application.candidate_id == Candidate.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
        )

        if stage_filter and stage_filter in VALID_STAGES:
            base_query = base_query.where(Application.stage == stage_filter)
            count_query = count_query.where(Application.stage == stage_filter)

        if job_id:
            base_query = base_query.where(Application.job_id == job_id)
            count_query = count_query.where(Application.job_id == job_id)

        if user and user.role == "hiring_manager":
            base_query = base_query.where(JobPosting.hiring_manager_id == user.id)
            count_query = count_query.where(JobPosting.hiring_manager_id == user.id)

        if search and search.strip():
            search_term = f"%{search.strip()}%"
            search_condition = or_(
                Candidate.first_name.ilike(search_term),
                Candidate.last_name.ilike(search_term),
                Candidate.email.ilike(search_term),
                JobPosting.title.ilike(search_term),
            )
            base_query = base_query.where(search_condition)
            count_query = count_query.where(search_condition)

        total_result = await db.execute(count_query)
        total_count = total_result.scalar() or 0

        offset = (page - 1) * per_page
        base_query = (
            base_query
            .order_by(Application.applied_at.desc())
            .offset(offset)
            .limit(per_page)
        )

        result = await db.execute(base_query)
        applications = list(result.scalars().unique().all())

        return applications, total_count
    except Exception:
        logger.exception(
            "Error listing applications (search=%s, stage=%s, job_id=%s, page=%d)",
            search,
            stage_filter,
            job_id,
            page,
        )
        return [], 0


async def list_applications_for_job(
    db: AsyncSession,
    job_id: int,
    stage_filter: Optional[str] = None,
) -> list[Application]:
    """List all applications for a specific job posting.

    Args:
        db: Async database session.
        job_id: The job posting ID.
        stage_filter: Optional stage to filter by.

    Returns:
        List of Application objects for the given job.
    """
    try:
        stmt = (
            select(Application)
            .where(Application.job_id == job_id)
            .options(
                selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Application.interviews),
            )
        )

        if stage_filter and stage_filter in VALID_STAGES:
            stmt = stmt.where(Application.stage == stage_filter)

        stmt = stmt.order_by(Application.applied_at.desc())

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception("Error listing applications for job_id=%d", job_id)
        return []


async def list_applications_for_candidate(
    db: AsyncSession,
    candidate_id: int,
) -> list[Application]:
    """List all applications for a specific candidate.

    Args:
        db: Async database session.
        candidate_id: The candidate ID.

    Returns:
        List of Application objects for the given candidate.
    """
    try:
        stmt = (
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .options(
                selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Application.interviews),
            )
            .order_by(Application.applied_at.desc())
        )

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception("Error listing applications for candidate_id=%d", candidate_id)
        return []


async def get_recent_applications(
    db: AsyncSession,
    limit: int = 10,
    user: Optional[User] = None,
) -> list[Application]:
    """Retrieve the most recent applications.

    Args:
        db: Async database session.
        limit: Maximum number of entries to return.
        user: Current user (for role-based filtering).

    Returns:
        A list of the most recent Application objects.
    """
    try:
        stmt = (
            select(Application)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Application.interviews),
            )
        )

        if user and user.role == "hiring_manager":
            stmt = stmt.join(
                JobPosting, Application.job_id == JobPosting.id
            ).where(JobPosting.hiring_manager_id == user.id)

        stmt = stmt.order_by(Application.applied_at.desc()).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception("Error fetching recent applications")
        return []


async def get_pipeline_stage_counts(
    db: AsyncSession,
    user: Optional[User] = None,
) -> list[dict]:
    """Get the count of applications in each pipeline stage.

    Args:
        db: Async database session.
        user: Current user (for role-based filtering).

    Returns:
        A list of dicts with keys: name (stage name), count (number of applications).
    """
    try:
        stmt = (
            select(
                Application.stage,
                func.count(Application.id).label("count"),
            )
            .group_by(Application.stage)
        )

        if user and user.role == "hiring_manager":
            stmt = stmt.join(
                JobPosting, Application.job_id == JobPosting.id
            ).where(JobPosting.hiring_manager_id == user.id)

        result = await db.execute(stmt)
        rows = result.all()

        stage_counts_map: dict[str, int] = {}
        for row in rows:
            stage_counts_map[row[0]] = row[1]

        pipeline_stages = []
        for stage in VALID_STAGES:
            pipeline_stages.append({
                "name": stage,
                "count": stage_counts_map.get(stage, 0),
            })

        return pipeline_stages
    except Exception:
        logger.exception("Error fetching pipeline stage counts")
        return [{"name": stage, "count": 0} for stage in VALID_STAGES]


async def count_active_applications(
    db: AsyncSession,
    user: Optional[User] = None,
) -> int:
    """Count applications that are not in terminal stages (Hired, Rejected).

    Args:
        db: Async database session.
        user: Current user (for role-based filtering).

    Returns:
        Integer count of active applications.
    """
    active_stages = ["Applied", "Screening", "Interviewing", "Offered"]
    try:
        stmt = select(func.count(Application.id)).where(
            Application.stage.in_(active_stages)
        )

        if user and user.role == "hiring_manager":
            stmt = stmt.join(
                JobPosting, Application.job_id == JobPosting.id
            ).where(JobPosting.hiring_manager_id == user.id)

        result = await db.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception("Error counting active applications")
        return 0