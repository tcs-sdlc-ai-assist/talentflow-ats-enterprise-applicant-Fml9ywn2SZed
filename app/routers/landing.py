import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.job_service import get_open_jobs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["landing"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/")
async def landing_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> Response:
    """Public landing page displaying published job listings and login CTA.

    No authentication required. Guests can view all published jobs.
    Authenticated users see the same page with navigation context.
    """
    try:
        jobs = await get_open_jobs(db)
    except Exception:
        logger.exception("Failed to fetch published jobs for landing page")
        jobs = []

    departments_seen: dict[str, bool] = {}
    locations_seen: dict[str, bool] = {}

    for job in jobs:
        if job.department and job.department.name:
            departments_seen[job.department.name] = True
        if job.location:
            locations_seen[job.location] = True

    departments = list(departments_seen.keys())
    locations = list(locations_seen.keys())

    return templates.TemplateResponse(
        request,
        "landing.html",
        context={
            "current_user": current_user,
            "jobs": jobs,
            "departments": departments,
            "locations": locations,
        },
    )