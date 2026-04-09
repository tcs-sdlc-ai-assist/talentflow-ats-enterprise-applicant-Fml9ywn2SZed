import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.models.audit_log import ActivityLog
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job_posting import JobPosting
from app.models.user import User
from app.services.application_service import (
    count_active_applications,
    get_pipeline_stage_counts,
    get_recent_applications,
)
from app.services.audit_service import get_recent_logs
from app.services.job_service import count_open_jobs, get_jobs_by_hiring_manager

logger = logging.getLogger(__name__)


async def _count_total_candidates(db: AsyncSession) -> int:
    """Count total number of candidates in the system.

    Args:
        db: Async database session.

    Returns:
        Integer count of all candidates.
    """
    try:
        result = await db.execute(select(func.count(Candidate.id)))
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception("Error counting total candidates")
        return 0


async def _count_upcoming_interviews(
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
            Interview.scheduled_at > now
        )

        if user and user.role == "interviewer":
            stmt = stmt.where(Interview.interviewer_id == user.id)
        elif user and user.role == "hiring_manager":
            stmt = (
                stmt
                .join(Application, Interview.application_id == Application.id)
                .join(JobPosting, Application.job_id == JobPosting.id)
                .where(JobPosting.hiring_manager_id == user.id)
            )

        result = await db.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception("Error counting upcoming interviews")
        return 0


async def _get_upcoming_interviews_for_interviewer(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[Interview]:
    """Fetch upcoming interviews assigned to a specific interviewer.

    Args:
        db: Async database session.
        user_id: The interviewer's user ID.
        limit: Maximum number of interviews to return.

    Returns:
        List of upcoming Interview objects for the interviewer.
    """
    try:
        now = datetime.utcnow()
        stmt = (
            select(Interview)
            .where(
                Interview.interviewer_id == user_id,
                Interview.scheduled_at > now,
            )
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.interviewer),
            )
            .order_by(Interview.scheduled_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception("Error fetching upcoming interviews for user_id=%d", user_id)
        return []


async def _count_pending_feedback(
    db: AsyncSession,
    user_id: int,
) -> int:
    """Count interviews assigned to a user that have no rating/feedback yet.

    Args:
        db: Async database session.
        user_id: The interviewer's user ID.

    Returns:
        Integer count of interviews pending feedback.
    """
    try:
        stmt = select(func.count(Interview.id)).where(
            Interview.interviewer_id == user_id,
            Interview.rating.is_(None),
        )
        result = await db.execute(stmt)
        count = result.scalar()
        return count if count is not None else 0
    except Exception:
        logger.exception("Error counting pending feedback for user_id=%d", user_id)
        return 0


async def _get_interviews_for_hiring_manager(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[Interview]:
    """Fetch interviews for jobs owned by a hiring manager.

    Args:
        db: Async database session.
        user_id: The hiring manager's user ID.
        limit: Maximum number of interviews to return.

    Returns:
        List of Interview objects for the hiring manager's jobs.
    """
    try:
        stmt = (
            select(Interview)
            .join(Application, Interview.application_id == Application.id)
            .join(JobPosting, Application.job_id == JobPosting.id)
            .where(JobPosting.hiring_manager_id == user_id)
            .options(
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job_posting).selectinload(JobPosting.department),
                selectinload(Interview.interviewer),
            )
            .order_by(Interview.scheduled_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())
    except Exception:
        logger.exception(
            "Error fetching interviews for hiring manager user_id=%d", user_id
        )
        return []


async def get_dashboard_data(
    db: AsyncSession,
    user: User,
) -> dict:
    """Aggregate dashboard data based on the user's role.

    Returns role-specific metrics:
    - Admin/Super Admin/Recruiter: pipeline counts, recent audit logs,
      total jobs/candidates, recent applications.
    - Hiring Manager: their job requisitions, interview status for their jobs.
    - Interviewer: upcoming interviews, pending feedback count.
    - Viewer: basic stats only.

    Args:
        db: Async database session.
        user: The authenticated user requesting dashboard data.

    Returns:
        A dict containing all dashboard data keyed by section.
    """
    data: dict = {
        "stats": {
            "open_jobs": 0,
            "total_candidates": 0,
            "active_applications": 0,
            "upcoming_interviews": 0,
        },
        "pipeline_stages": [],
        "recent_applications": [],
        "recent_audit_logs": [],
        "my_jobs": [],
        "my_interviews": [],
        "upcoming_interviews": [],
        "pending_feedback_count": 0,
    }

    try:
        # Stats available to all roles
        data["stats"]["open_jobs"] = await count_open_jobs(db)
        data["stats"]["total_candidates"] = await _count_total_candidates(db)
        data["stats"]["active_applications"] = await count_active_applications(
            db, user=user
        )
        data["stats"]["upcoming_interviews"] = await _count_upcoming_interviews(
            db, user=user
        )

        # Admin / Super Admin / Recruiter dashboard
        if user.role in ["admin", "super_admin", "recruiter"]:
            data["pipeline_stages"] = await get_pipeline_stage_counts(db, user=user)
            data["recent_applications"] = await get_recent_applications(
                db, limit=10, user=user
            )

            if user.role in ["admin", "super_admin"]:
                data["recent_audit_logs"] = await get_recent_logs(db, limit=10)

        # Hiring Manager dashboard
        if user.role == "hiring_manager":
            data["pipeline_stages"] = await get_pipeline_stage_counts(db, user=user)
            data["recent_applications"] = await get_recent_applications(
                db, limit=10, user=user
            )
            data["my_jobs"] = await get_jobs_by_hiring_manager(db, user.id)
            data["my_interviews"] = await _get_interviews_for_hiring_manager(
                db, user.id, limit=10
            )

        # Interviewer dashboard
        if user.role == "interviewer":
            data["upcoming_interviews"] = await _get_upcoming_interviews_for_interviewer(
                db, user.id, limit=10
            )
            data["pending_feedback_count"] = await _count_pending_feedback(
                db, user.id
            )

        logger.info(
            "Dashboard data aggregated for user '%s' (role=%s): "
            "open_jobs=%d, total_candidates=%d, active_applications=%d, "
            "upcoming_interviews=%d",
            user.username,
            user.role,
            data["stats"]["open_jobs"],
            data["stats"]["total_candidates"],
            data["stats"]["active_applications"],
            data["stats"]["upcoming_interviews"],
        )

    except Exception:
        logger.exception(
            "Error aggregating dashboard data for user '%s' (role=%s)",
            user.username,
            user.role,
        )

    return data