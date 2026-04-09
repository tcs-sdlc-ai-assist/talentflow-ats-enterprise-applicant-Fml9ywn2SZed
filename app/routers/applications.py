import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_login, require_role
from app.models.user import User
from app.services.application_service import (
    VALID_STAGES,
    create_application,
    get_application_by_id,
    get_kanban_board,
    list_applications,
    update_stage,
)
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

ROLES_CAN_MANAGE = ["admin", "recruiter", "hiring_manager"]


@router.get("")
async def application_list_page(
    request: Request,
    search: str = "",
    stage: str = "",
    job_id: Optional[str] = None,
    page: int = 1,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    per_page = 25
    if page < 1:
        page = 1

    parsed_job_id: Optional[int] = None
    if job_id and job_id.strip():
        try:
            parsed_job_id = int(job_id.strip())
        except (ValueError, TypeError):
            parsed_job_id = None

    applications, total_count = await list_applications(
        db=db,
        search=search if search else None,
        stage_filter=stage if stage else None,
        job_id=parsed_job_id,
        page=page,
        per_page=per_page,
        user=current_user,
    )

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request,
        "application_list.html",
        context={
            "current_user": current_user,
            "applications": applications,
            "search": search,
            "stage_filter": stage,
            "job_id": job_id or "",
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "valid_stages": VALID_STAGES,
        },
    )


@router.get("/kanban")
async def kanban_board_page(
    request: Request,
    job_id: Optional[str] = None,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    parsed_job_id: Optional[int] = None
    if job_id and job_id.strip():
        try:
            parsed_job_id = int(job_id.strip())
        except (ValueError, TypeError):
            parsed_job_id = None

    kanban_data = await get_kanban_board(
        db=db,
        job_id=parsed_job_id,
        user=current_user,
    )

    return templates.TemplateResponse(
        request,
        "kanban.html",
        context={
            "current_user": current_user,
            "board": kanban_data["board"],
            "jobs": kanban_data["jobs"],
            "total_applications": kanban_data["total_applications"],
            "selected_job_id": kanban_data["selected_job_id"],
        },
    )


@router.post("/create")
async def application_create_submit(
    request: Request,
    candidate_id: str = Form(...),
    job_id: str = Form(...),
    stage: str = Form("Applied"),
    current_user: User = Depends(require_role(ROLES_CAN_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    errors: list[str] = []

    try:
        parsed_candidate_id = int(candidate_id)
    except (ValueError, TypeError):
        errors.append("Please select a valid candidate.")
        parsed_candidate_id = 0

    try:
        parsed_job_id = int(job_id)
    except (ValueError, TypeError):
        errors.append("Please select a valid job posting.")
        parsed_job_id = 0

    if errors:
        logger.info(
            "Application creation failed by user '%s': %s",
            current_user.username,
            "; ".join(errors),
        )
        return RedirectResponse(url="/applications/kanban", status_code=302)

    application, error = await create_application(
        db=db,
        candidate_id=parsed_candidate_id,
        job_id=parsed_job_id,
        stage=stage if stage else "Applied",
        user=current_user,
    )

    if application is None:
        logger.info(
            "Application creation failed by user '%s': %s",
            current_user.username,
            error,
        )
        return RedirectResponse(url="/applications/kanban", status_code=302)

    await log_action(
        db=db,
        action="create_application",
        user_id=current_user.id,
        entity_type="application",
        entity_id=application.id,
        details=(
            f"Created application for candidate_id={application.candidate_id} "
            f"to job_id={application.job_id} with stage '{application.stage}'"
        ),
    )

    logger.info(
        "Application created by user '%s': id=%d, candidate_id=%d, job_id=%d, stage='%s'",
        current_user.username,
        application.id,
        application.candidate_id,
        application.job_id,
        application.stage,
    )
    return RedirectResponse(url="/applications/kanban", status_code=302)


@router.post("/{application_id}/stage")
async def application_stage_update(
    request: Request,
    application_id: int,
    stage: str = Form(...),
    current_user: User = Depends(require_role(ROLES_CAN_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    existing = await get_application_by_id(db, application_id)
    if existing is None:
        logger.warning(
            "User '%s' attempted to update stage for non-existent application id=%d",
            current_user.username,
            application_id,
        )
        return RedirectResponse(url="/applications/kanban", status_code=302)

    old_stage = existing.stage

    application, error = await update_stage(
        db=db,
        application_id=application_id,
        new_stage=stage,
        user=current_user,
    )

    if application is None:
        logger.warning(
            "User '%s' failed to update stage for application id=%d: %s",
            current_user.username,
            application_id,
            error,
        )
        return RedirectResponse(url="/applications/kanban", status_code=302)

    await log_action(
        db=db,
        action="update_application_stage",
        user_id=current_user.id,
        entity_type="application",
        entity_id=application.id,
        details=(
            f"Changed application stage from '{old_stage}' to '{application.stage}' "
            f"(candidate_id={application.candidate_id}, job_id={application.job_id})"
        ),
    )

    logger.info(
        "User '%s' changed application id=%d stage: '%s' -> '%s'",
        current_user.username,
        application.id,
        old_stage,
        application.stage,
    )

    referer = request.headers.get("referer", "")
    if "/kanban" in referer:
        job_filter = ""
        if "job_id=" in referer:
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(referer)
                params = urllib.parse.parse_qs(parsed.query)
                if "job_id" in params and params["job_id"][0]:
                    job_filter = f"?job_id={params['job_id'][0]}"
            except Exception:
                pass
        return RedirectResponse(
            url=f"/applications/kanban{job_filter}",
            status_code=302,
        )

    return RedirectResponse(url="/applications/kanban", status_code=302)