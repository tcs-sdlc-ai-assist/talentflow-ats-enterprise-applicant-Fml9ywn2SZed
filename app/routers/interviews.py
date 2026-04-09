import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_login, require_role
from app.models.user import User
from app.services.audit_service import log_action
from app.services.interview_service import (
    get_all_interviewers,
    get_interview_by_id,
    get_schedulable_applications,
    list_interviews,
    list_my_interviews,
    schedule_interview,
    submit_feedback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

ROLES_CAN_SCHEDULE = ["admin", "hiring_manager", "recruiter"]
ROLES_CAN_VIEW_ALL = ["admin", "hiring_manager", "recruiter"]


@router.get("")
async def interview_list_page(
    request: Request,
    search: str = "",
    status_filter: str = "",
    page: int = 1,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    per_page = 25
    if page < 1:
        page = 1

    interviews, total_count = await list_interviews(
        db=db,
        search=search if search else None,
        status_filter=status_filter if status_filter else None,
        page=page,
        per_page=per_page,
        user=current_user,
    )

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request,
        "interview_list.html",
        context={
            "current_user": current_user,
            "interviews": interviews,
            "search": search,
            "status_filter": status_filter,
            "current_page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    )


@router.get("/my")
async def my_interviews_page(
    request: Request,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interviews = await list_my_interviews(
        db=db,
        user=current_user,
        upcoming_only=False,
    )

    return templates.TemplateResponse(
        request,
        "interview_list.html",
        context={
            "current_user": current_user,
            "interviews": interviews,
            "search": "",
            "status_filter": "",
            "current_page": 1,
            "per_page": 25,
            "total_count": len(interviews),
            "total_pages": 1,
        },
    )


@router.get("/schedule")
async def interview_schedule_page(
    request: Request,
    application_id: Optional[str] = None,
    current_user: User = Depends(require_role(ROLES_CAN_SCHEDULE)),
    db: AsyncSession = Depends(get_db),
):
    applications = await get_schedulable_applications(db=db, user=current_user)
    interviewers = await get_all_interviewers(db=db)

    parsed_application_id: Optional[int] = None
    if application_id and application_id.strip():
        try:
            parsed_application_id = int(application_id.strip())
        except (ValueError, TypeError):
            parsed_application_id = None

    return templates.TemplateResponse(
        request,
        "interview_schedule.html",
        context={
            "current_user": current_user,
            "applications": applications,
            "interviewers": interviewers,
            "selected_application_id": parsed_application_id,
            "selected_interviewer_id": None,
            "selected_scheduled_at": None,
        },
    )


@router.post("")
async def interview_schedule_submit(
    request: Request,
    application_id: str = Form(...),
    interviewer_id: str = Form(...),
    scheduled_at: str = Form(...),
    current_user: User = Depends(require_role(ROLES_CAN_SCHEDULE)),
    db: AsyncSession = Depends(get_db),
):
    errors: list[str] = []

    try:
        parsed_application_id = int(application_id)
    except (ValueError, TypeError):
        errors.append("Please select a valid application.")
        parsed_application_id = 0

    try:
        parsed_interviewer_id = int(interviewer_id)
    except (ValueError, TypeError):
        errors.append("Please select a valid interviewer.")
        parsed_interviewer_id = 0

    parsed_scheduled_at: Optional[datetime] = None
    if scheduled_at and scheduled_at.strip():
        try:
            parsed_scheduled_at = datetime.fromisoformat(scheduled_at.strip())
        except (ValueError, TypeError):
            errors.append("Please provide a valid date and time.")
    else:
        errors.append("Scheduled date and time is required.")

    if errors:
        applications = await get_schedulable_applications(db=db, user=current_user)
        interviewers = await get_all_interviewers(db=db)
        logger.info(
            "Interview scheduling failed by user '%s': %s",
            current_user.username,
            "; ".join(errors),
        )
        return templates.TemplateResponse(
            request,
            "interview_schedule.html",
            context={
                "current_user": current_user,
                "applications": applications,
                "interviewers": interviewers,
                "selected_application_id": parsed_application_id if parsed_application_id else None,
                "selected_interviewer_id": parsed_interviewer_id if parsed_interviewer_id else None,
                "selected_scheduled_at": scheduled_at if scheduled_at else None,
                "error": "; ".join(errors),
            },
            status_code=400,
        )

    interview, error = await schedule_interview(
        db=db,
        application_id=parsed_application_id,
        interviewer_id=parsed_interviewer_id,
        scheduled_at=parsed_scheduled_at,
        user=current_user,
    )

    if interview is None:
        applications = await get_schedulable_applications(db=db, user=current_user)
        interviewers = await get_all_interviewers(db=db)
        logger.info(
            "Interview scheduling failed by user '%s': %s",
            current_user.username,
            error,
        )
        return templates.TemplateResponse(
            request,
            "interview_schedule.html",
            context={
                "current_user": current_user,
                "applications": applications,
                "interviewers": interviewers,
                "selected_application_id": parsed_application_id,
                "selected_interviewer_id": parsed_interviewer_id,
                "selected_scheduled_at": scheduled_at if scheduled_at else None,
                "error": error or "Failed to schedule interview.",
            },
            status_code=400,
        )

    await log_action(
        db=db,
        action="schedule_interview",
        user_id=current_user.id,
        entity_type="interview",
        entity_id=interview.id,
        details=(
            f"Scheduled interview for application_id={interview.application_id} "
            f"with interviewer_id={interview.interviewer_id} "
            f"at {interview.scheduled_at}"
        ),
    )

    logger.info(
        "Interview scheduled by user '%s': id=%d, application_id=%d, "
        "interviewer_id=%d, scheduled_at=%s",
        current_user.username,
        interview.id,
        interview.application_id,
        interview.interviewer_id,
        interview.scheduled_at,
    )
    return RedirectResponse(url="/interviews", status_code=302)


@router.get("/{interview_id}/feedback")
async def interview_feedback_page(
    request: Request,
    interview_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview = await get_interview_by_id(db, interview_id)

    if interview is None:
        logger.warning(
            "User '%s' attempted to access feedback for non-existent interview id=%d",
            current_user.username,
            interview_id,
        )
        return RedirectResponse(url="/interviews", status_code=302)

    # Determine if the current user can view/submit feedback
    is_interviewer = interview.interviewer_id == current_user.id
    is_admin_or_manager = current_user.role in ["admin", "hiring_manager"]

    if not is_interviewer and not is_admin_or_manager:
        logger.warning(
            "User '%s' (role=%s) denied access to feedback for interview id=%d",
            current_user.username,
            current_user.role,
            interview_id,
        )
        return RedirectResponse(url="/interviews", status_code=302)

    # If feedback already submitted, show in read-only mode
    readonly = interview.rating is not None

    return templates.TemplateResponse(
        request,
        "interview_feedback.html",
        context={
            "current_user": current_user,
            "interview": interview,
            "readonly": readonly,
        },
    )


@router.post("/{interview_id}/feedback")
async def interview_feedback_submit(
    request: Request,
    interview_id: int,
    rating: str = Form(...),
    feedback_notes: str = Form(""),
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    interview = await get_interview_by_id(db, interview_id)

    if interview is None:
        logger.warning(
            "User '%s' attempted to submit feedback for non-existent interview id=%d",
            current_user.username,
            interview_id,
        )
        return RedirectResponse(url="/interviews", status_code=302)

    # Parse rating
    try:
        parsed_rating = int(rating)
    except (ValueError, TypeError):
        logger.info(
            "User '%s' submitted invalid rating for interview id=%d: %s",
            current_user.username,
            interview_id,
            rating,
        )
        return templates.TemplateResponse(
            request,
            "interview_feedback.html",
            context={
                "current_user": current_user,
                "interview": interview,
                "readonly": False,
                "error": "Please provide a valid rating (1-5).",
            },
            status_code=400,
        )

    updated_interview, error = await submit_feedback(
        db=db,
        interview_id=interview_id,
        rating=parsed_rating,
        feedback_notes=feedback_notes if feedback_notes.strip() else None,
        user=current_user,
    )

    if updated_interview is None:
        logger.info(
            "Feedback submission failed by user '%s' for interview id=%d: %s",
            current_user.username,
            interview_id,
            error,
        )
        return templates.TemplateResponse(
            request,
            "interview_feedback.html",
            context={
                "current_user": current_user,
                "interview": interview,
                "readonly": False,
                "error": error or "Failed to submit feedback.",
            },
            status_code=400,
        )

    await log_action(
        db=db,
        action="submit_interview_feedback",
        user_id=current_user.id,
        entity_type="interview",
        entity_id=updated_interview.id,
        details=(
            f"Submitted feedback for interview id={updated_interview.id}: "
            f"rating={updated_interview.rating}, "
            f"application_id={updated_interview.application_id}"
        ),
    )

    logger.info(
        "Feedback submitted by user '%s' for interview id=%d: rating=%d",
        current_user.username,
        updated_interview.id,
        updated_interview.rating,
    )

    # Redirect based on user role
    if current_user.role == "interviewer":
        return RedirectResponse(url="/interviews/my", status_code=302)

    return RedirectResponse(url="/interviews", status_code=302)