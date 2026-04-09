import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.services.audit_service import get_logs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/audit-log")
async def audit_log_page(
    request: Request,
    page: int = 1,
    search: str = "",
    action_filter: str = "",
    current_user: User = Depends(require_role(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    search_term = search.strip() if search else None
    action_filter_term = action_filter.strip() if action_filter else None

    if page < 1:
        page = 1

    per_page = 25

    result = await get_logs(
        db=db,
        page=page,
        per_page=per_page,
        search=search_term,
        action_filter=action_filter_term,
    )

    return templates.TemplateResponse(
        request,
        "audit_log.html",
        context={
            "current_user": current_user,
            "logs": result["logs"],
            "page": result["page"],
            "per_page": result["per_page"],
            "total_count": result["total_count"],
            "total_pages": result["total_pages"],
            "action_options": result["action_options"],
            "search": search or "",
            "action_filter": action_filter or "",
        },
    )