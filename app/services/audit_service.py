import logging
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import ActivityLog
from app.models.user import User

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
) -> ActivityLog:
    """Create an immutable audit log entry for a critical action.

    Args:
        db: Async database session.
        action: Short description of the action (e.g. 'create_job', 'reject_candidate').
        user_id: ID of the user who performed the action, or None for system actions.
        entity_type: Type of entity affected (e.g. 'job_posting', 'candidate', 'application').
        entity_id: Primary key of the affected entity.
        details: Optional free-text details about the action.

    Returns:
        The created ActivityLog entry.
    """
    try:
        entry = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)

        logger.info(
            "Audit log created: action=%s, user_id=%s, entity_type=%s, entity_id=%s",
            action,
            user_id,
            entity_type,
            entity_id,
        )
        return entry
    except Exception:
        logger.exception(
            "Failed to create audit log entry: action=%s, user_id=%s",
            action,
            user_id,
        )
        raise


async def get_logs(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    action_filter: Optional[str] = None,
) -> dict:
    """Retrieve paginated audit log entries with optional filtering.

    Args:
        db: Async database session.
        page: Page number (1-indexed).
        per_page: Number of entries per page.
        search: Optional search term to filter by action or details.
        action_filter: Optional exact action name to filter by.

    Returns:
        A dict with keys: logs, page, per_page, total_count, total_pages, action_options.
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 25

    try:
        base_query = select(ActivityLog)
        count_query = select(func.count(ActivityLog.id))

        if action_filter:
            base_query = base_query.where(ActivityLog.action == action_filter)
            count_query = count_query.where(ActivityLog.action == action_filter)

        if search:
            search_term = f"%{search}%"
            search_condition = or_(
                ActivityLog.action.ilike(search_term),
                ActivityLog.details.ilike(search_term),
                ActivityLog.entity_type.ilike(search_term),
            )
            base_query = base_query.where(search_condition)
            count_query = count_query.where(search_condition)

        total_result = await db.execute(count_query)
        total_count = total_result.scalar() or 0

        total_pages = max(1, (total_count + per_page - 1) // per_page)

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        logs_query = (
            base_query
            .order_by(ActivityLog.timestamp.desc())
            .offset(offset)
            .limit(per_page)
        )
        result = await db.execute(logs_query)
        logs = result.scalars().all()

        action_options_result = await db.execute(
            select(ActivityLog.action)
            .distinct()
            .order_by(ActivityLog.action)
        )
        action_options = [row for row in action_options_result.scalars().all()]

        return {
            "logs": logs,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "action_options": action_options,
        }
    except Exception:
        logger.exception("Failed to retrieve audit logs")
        raise


async def get_recent_logs(
    db: AsyncSession,
    limit: int = 10,
) -> list[ActivityLog]:
    """Retrieve the most recent audit log entries.

    Args:
        db: Async database session.
        limit: Maximum number of entries to return.

    Returns:
        A list of the most recent ActivityLog entries.
    """
    try:
        result = await db.execute(
            select(ActivityLog)
            .order_by(ActivityLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        logger.exception("Failed to retrieve recent audit logs")
        raise


async def get_logs_for_entity(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    limit: int = 50,
) -> list[ActivityLog]:
    """Retrieve audit log entries for a specific entity.

    Args:
        db: Async database session.
        entity_type: The type of entity (e.g. 'job_posting', 'candidate').
        entity_id: The primary key of the entity.
        limit: Maximum number of entries to return.

    Returns:
        A list of ActivityLog entries for the specified entity.
    """
    try:
        result = await db.execute(
            select(ActivityLog)
            .where(
                ActivityLog.entity_type == entity_type,
                ActivityLog.entity_id == entity_id,
            )
            .order_by(ActivityLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        logger.exception(
            "Failed to retrieve audit logs for entity: type=%s, id=%s",
            entity_type,
            entity_id,
        )
        raise


async def get_logs_for_user(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> list[ActivityLog]:
    """Retrieve audit log entries for a specific user.

    Args:
        db: Async database session.
        user_id: The user's primary key.
        limit: Maximum number of entries to return.

    Returns:
        A list of ActivityLog entries for the specified user.
    """
    try:
        result = await db.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception:
        logger.exception(
            "Failed to retrieve audit logs for user_id=%s",
            user_id,
        )
        raise