import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_login
from app.models.user import User
from app.services.dashboard_service import get_dashboard_data

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """Role-specific dashboard page.

    Aggregates metrics and data based on the authenticated user's role:
    - Admin/Super Admin/Recruiter: pipeline overview, recent applications, audit logs
    - Hiring Manager: job requisitions, interview status for their jobs
    - Interviewer: upcoming interviews, pending feedback count
    - Viewer: basic stats and browse links

    All authenticated users can access this endpoint.
    """
    dashboard_data = await get_dashboard_data(db=db, user=current_user)

    logger.info(
        "Dashboard rendered for user '%s' (role=%s)",
        current_user.username,
        current_user.role,
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "current_user": current_user,
            "stats": dashboard_data.get("stats", {}),
            "pipeline_stages": dashboard_data.get("pipeline_stages", []),
            "recent_applications": dashboard_data.get("recent_applications", []),
            "recent_audit_logs": dashboard_data.get("recent_audit_logs", []),
            "my_jobs": dashboard_data.get("my_jobs", []),
            "my_interviews": dashboard_data.get("my_interviews", []),
            "upcoming_interviews": dashboard_data.get("upcoming_interviews", []),
            "pending_feedback_count": dashboard_data.get("pending_feedback_count", 0),
        },
    )