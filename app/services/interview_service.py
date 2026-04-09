import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job_posting import JobPosting
from app.models.user import User

logger = logging.getLogger(__name__)

ROLES_CAN_SCHEDULE = ["admin", "hiring_manager", "recruiter"]
ROLES_CAN_VIEW_ALL = ["admin", "hiring_manager", "recruiter"]


async def schedule_interview(
    db: AsyncSession,
    application_id: int,
    interviewer_id: int,
    scheduled_at: datetime,
    user: Optional[User] = None,
) -> tuple[Optional[Interview], Optional[str]]:
    """Schedule a new interview for an application.

    Args:
        db: Async database session.
        application_id: FK to applications table.
        interviewer_id: FK to users table (the interviewer).
        scheduled_at: The date and time for the interview.
        user: The user performing the action (for RBAC).

    Returns:
        Tuple of (Interview, None) on success, or (None, error_message) on failure.
    """
    if user and user.role not in ROLES_CAN_SCHEDULE:
        logger.warning(
            "User %s (role=%s) attempted to schedule an interview without permission",
            user.username,
            user.role,
        )
        return None, "You do not have permission to schedule interviews."

    try:
        app_result = await db.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.candidate),
                selectinload(Application.job_posting),
            )
        )
        application = app_result.scalar_one_or_none()
        if application is None:
            return None, "Application not found."

        interviewer_result = await db.execute(
            select(User).where(User.id == interviewer_id)
        )
        interviewer = interviewer_result.scalar_one_or_none()
        if interviewer is None:
            return None, "Interviewer not found."

        if not interviewer.is_active:
            return None, "Selected interviewer is inactive."

        interview = Interview(
            application_id=application_id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_at,
        )
        db.add(interview)
        await db.flush()
        await db.refresh(interview)

        logger.info(
            "Interview scheduled: id=%d, application_id=%d, interviewer_id=%d, "
            "scheduled_at=%s by user=%s",
            interview.id,
            interview.application_id,
            interview.interviewer_id,
            interview.scheduled_at,
            user.username if user else "system",
        )
        return interview, None
    except Exception:
        logger.exception(
            "Error scheduling interview for application_id=%d",
            application_id,
        )
        return None, "An unexpected error occurred while scheduling the interview."


async def submit_feedback(
    db: AsyncSession,
    interview_id: int,
    rating: int,
    feedback_notes: Optional[str] = None,
    user: Optional[User] = None,
) -> tuple[Optional[Interview], Optional[str]]:
    """Submit feedback and rating for an interview.

    Args:
        db: Async database session.
        interview_id: The interview primary key.
        rating: Integer rating from 1 to 5.
        feedback_notes: Optional text feedback.
        user: The user submitting feedback (for RBAC).

    Returns:
        Tuple of (Interview, None) on success, or (None, error_message) on failure.
    """
    if rating < 1 or rating > 5:
        return None, "Rating must be between 1 and 5."

    try:
        interview = await get_interview_by_id(db, interview_id)
        if interview is None:
            return None, "Interview not found."

        if user:
            is_interviewer = interview.interviewer_id == user.id
            is_admin_or_manager = user.role in ["admin", "hiring_manager"]
            if not is_interviewer and not is_admin_or_manager:
                logger.warning(
                    "User %s (role=%s) attempted to submit feedback for interview id=%d "
                    "without permission",
                    user.username,
                    user.role,
                    interview_id,
                )
                return None, "You do not have permission to submit feedback for this interview."

        interview.rating = rating
        interview.feedback_notes = feedback_notes.strip() if feedback_notes else None

        await db.flush()
        await db.refresh(interview)

        logger.info(
            "Feedback submitted for interview id=%d: rating=%d by user=%s",
            interview.id,
            rating,
            user.username if user else "system",
        )
        return interview, None
    except Exception:
        logger.exception(
            "Error submitting feedback for interview id=%d",
            interview_id,
        )
        return None, "An unexpected error occurred while submitting feedback."


async def get_interview_by_id(
    db: AsyncSession,
    interview_id: int,
) -> Optional[Interview]:
    """Fetch a single interview by ID with all relationships loaded.

    Args:
        db: Async database session.
        interview_id: The interview primary key.

    Returns:
        The Interview object if found, None otherwise.
    """
    try:
        stmt = (
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Interview.interviewer),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        logger.exception("Error fetching interview id=%d", interview_id)
        return None


async def list_my_interviews(
    db: AsyncSession,
    user: User,
    upcoming_only: bool = False,
) -> list[Interview]:
    """List all interviews assigned to a specific interviewer.

    Args:
        db: Async database session.
        user: The interviewer user.
        upcoming_only: If True, only return interviews scheduled in the future.

    Returns:
        List of Interview objects assigned to the user.
    """
    try:
        stmt = (
            select(Interview)
            .where(Interview.interviewer_id == user.id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Interview.interviewer),
            )
        )

        if upcoming_only:
            stmt = stmt.where(Interview.scheduled_at >= datetime.utcnow())

        stmt = stmt.order_by(Interview.scheduled_at.asc())

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception(
            "Error listing interviews for user_id=%d",
            user.id,
        )
        return []


async def list_interviews_for_application(
    db: AsyncSession,
    application_id: int,
) -> list[Interview]:
    """List all interviews for a specific application.

    Args:
        db: Async database session.
        application_id: The application ID.

    Returns:
        List of Interview objects for the given application.
    """
    try:
        stmt = (
            select(Interview)
            .where(Interview.application_id == application_id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.interviewer),
            )
            .order_by(Interview.scheduled_at.desc())
        )

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception(
            "Error listing interviews for application_id=%d",
            application_id,
        )
        return []


async def list_interviews(
    db: AsyncSession,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
    user: Optional[User] = None,
) -> tuple[list[Interview], int]:
    """List interviews with optional filtering and pagination.

    Args:
        db: Async database session.
        search: Optional search term for candidate name or job title.
        status_filter: Optional status filter ('scheduled', 'completed', 'pending_feedback').
        page: Page number (1-indexed).
        per_page: Number of results per page.
        user: Current user (for role-based filtering).

    Returns:
        A tuple of (list of Interview objects, total count).
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 25

    try:
        base_query = (
            select(Interview)
            .join(Application, Interview.application_id == Application.id)
            .join(Candidate, Application.candidate_id == Candidate.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate).selectinload(Candidate.skills),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Interview.interviewer),
            )
        )

        count_query = (
            select(func.count(Interview.id))
            .join(Application, Interview.application_id == Application.id)
            .join(Candidate, Application.candidate_id == Candidate.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
        )

        # Role-based filtering
        if user:
            if user.role == "interviewer":
                base_query = base_query.where(Interview.interviewer_id == user.id)
                count_query = count_query.where(Interview.interviewer_id == user.id)
            elif user.role == "hiring_manager":
                base_query = base_query.where(JobPosting.hiring_manager_id == user.id)
                count_query = count_query.where(JobPosting.hiring_manager_id == user.id)

        # Status filtering
        if status_filter:
            now = datetime.utcnow()
            if status_filter == "scheduled":
                base_query = base_query.where(Interview.scheduled_at >= now)
                count_query = count_query.where(Interview.scheduled_at >= now)
            elif status_filter == "completed":
                base_query = base_query.where(
                    Interview.rating.isnot(None),
                    Interview.feedback_notes.isnot(None),
                )
                count_query = count_query.where(
                    Interview.rating.isnot(None),
                    Interview.feedback_notes.isnot(None),
                )
            elif status_filter == "pending_feedback":
                base_query = base_query.where(
                    Interview.rating.is_(None),
                )
                count_query = count_query.where(
                    Interview.rating.is_(None),
                )

        # Search filtering
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
            .order_by(Interview.scheduled_at.desc())
            .offset(offset)
            .limit(per_page)
        )

        result = await db.execute(base_query)
        interviews = list(result.scalars().unique().all())

        return interviews, total_count
    except Exception:
        logger.exception(
            "Error listing interviews (search=%s, status=%s, page=%d)",
            search,
            status_filter,
            page,
        )
        return [], 0


async def get_upcoming_interviews(
    db: AsyncSession,
    user: Optional[User] = None,
    limit: int = 10,
) -> list[Interview]:
    """Retrieve upcoming interviews (scheduled in the future).

    Args:
        db: Async database session.
        user: Current user (for role-based filtering).
        limit: Maximum number of entries to return.

    Returns:
        A list of upcoming Interview objects.
    """
    try:
        now = datetime.utcnow()
        stmt = (
            select(Interview)
            .where(Interview.scheduled_at >= now)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Interview.interviewer),
            )
        )

        if user:
            if user.role == "interviewer":
                stmt = stmt.where(Interview.interviewer_id == user.id)
            elif user.role == "hiring_manager":
                stmt = stmt.join(
                    Application, Interview.application_id == Application.id
                ).join(
                    JobPosting, Application.job_id == JobPosting.id
                ).where(JobPosting.hiring_manager_id == user.id)

        stmt = stmt.order_by(Interview.scheduled_at.asc()).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception("Error fetching upcoming interviews")
        return []


async def count_upcoming_interviews(
    db: AsyncSession,
    user: Optional[User] = None,
) -> int:
    """Count interviews scheduled in the future.

    Args:
        db: Async database session.
        user: Current user (for role-based filtering).

    Returns:
        Integer count of upcoming interviews.
    """
    try:
        now = datetime.utcnow()
        stmt = select(func.count(Interview.id)).where(
            Interview.scheduled_at >= now
        )

        if user:
            if user.role == "interviewer":
                stmt = stmt.where(Interview.interviewer_id == user.id)
            elif user.role == "hiring_manager":
                stmt = stmt.join(
                    Application, Interview.application_id == Application.id
                ).join(
                    JobPosting, Application.job_id == JobPosting.id
                ).where(JobPosting.hiring_manager_id == user.id)

        result = await db.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception("Error counting upcoming interviews")
        return 0


async def count_pending_feedback(
    db: AsyncSession,
    user: User,
) -> int:
    """Count interviews assigned to a user that are missing feedback.

    Args:
        db: Async database session.
        user: The interviewer user.

    Returns:
        Integer count of interviews pending feedback.
    """
    try:
        stmt = select(func.count(Interview.id)).where(
            Interview.interviewer_id == user.id,
            Interview.rating.is_(None),
        )

        result = await db.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception(
            "Error counting pending feedback for user_id=%d",
            user.id,
        )
        return 0


async def get_interviews_for_hiring_manager(
    db: AsyncSession,
    hiring_manager_id: int,
    limit: int = 20,
) -> list[Interview]:
    """Retrieve interviews for jobs managed by a specific hiring manager.

    Args:
        db: Async database session.
        hiring_manager_id: The hiring manager's user ID.
        limit: Maximum number of entries to return.

    Returns:
        A list of Interview objects for the hiring manager's jobs.
    """
    try:
        stmt = (
            select(Interview)
            .join(Application, Interview.application_id == Application.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
            .where(JobPosting.hiring_manager_id == hiring_manager_id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.hiring_manager),
                selectinload(Interview.interviewer),
            )
            .order_by(Interview.scheduled_at.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception(
            "Error fetching interviews for hiring_manager_id=%d",
            hiring_manager_id,
        )
        return []


async def get_all_interviewers(
    db: AsyncSession,
) -> list[User]:
    """Fetch all active users who can be assigned as interviewers.

    Args:
        db: Async database session.

    Returns:
        List of User objects eligible to be interviewers.
    """
    try:
        stmt = (
            select(User)
            .where(User.is_active == 1)
            .order_by(User.username)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception:
        logger.exception("Error fetching interviewers")
        return []


async def get_schedulable_applications(
    db: AsyncSession,
    user: Optional[User] = None,
) -> list[Application]:
    """Fetch applications that are in stages eligible for interview scheduling.

    Args:
        db: Async database session.
        user: Current user (for role-based filtering).

    Returns:
        List of Application objects eligible for scheduling.
    """
    schedulable_stages = ["Applied", "Screening", "Interviewing"]
    try:
        stmt = (
            select(Application)
            .where(Application.stage.in_(schedulable_stages))
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

        stmt = stmt.order_by(Application.applied_at.desc())

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception("Error fetching schedulable applications")
        return []