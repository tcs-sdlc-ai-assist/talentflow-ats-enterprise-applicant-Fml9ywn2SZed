import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_login, require_role
from app.models.user import User
from app.services.candidate_service import (
    create_candidate,
    edit_candidate,
    get_candidate_by_id,
    list_candidates,
)
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

ROLES_CAN_MANAGE = ["admin", "recruiter", "hiring_manager"]


@router.get("")
async def candidate_list_page(
    request: Request,
    search: str = "",
    page: int = 1,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    per_page = 20
    if page < 1:
        page = 1

    candidates, total_count = await list_candidates(
        db=db,
        search=search if search else None,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request,
        "candidate_list.html",
        context={
            "current_user": current_user,
            "candidates": candidates,
            "search": search,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    )


@router.get("/create")
async def candidate_create_page(
    request: Request,
    current_user: User = Depends(require_role(ROLES_CAN_MANAGE)),
):
    return templates.TemplateResponse(
        request,
        "candidate_form.html",
        context={
            "current_user": current_user,
            "candidate": None,
        },
    )


@router.post("")
async def candidate_create_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    skills: str = Form(""),
    resume_text: str = Form(""),
    current_user: User = Depends(require_role(ROLES_CAN_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    candidate, error = await create_candidate(
        db=db,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone if phone else None,
        linkedin_url=linkedin_url if linkedin_url else None,
        resume_text=resume_text if resume_text else None,
        skills_csv=skills if skills else None,
    )

    if candidate is None:
        logger.info(
            "Candidate creation failed by user '%s': %s",
            current_user.username,
            error,
        )
        return templates.TemplateResponse(
            request,
            "candidate_form.html",
            context={
                "current_user": current_user,
                "candidate": None,
                "error": error or "Failed to create candidate.",
            },
            status_code=400,
        )

    await log_action(
        db=db,
        action="create_candidate",
        user_id=current_user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        details=f"Created candidate: {candidate.first_name} {candidate.last_name} ({candidate.email})",
    )

    logger.info(
        "Candidate created by user '%s': id=%d, name='%s %s'",
        current_user.username,
        candidate.id,
        candidate.first_name,
        candidate.last_name,
    )
    return RedirectResponse(
        url=f"/candidates/{candidate.id}",
        status_code=302,
    )


@router.get("/{candidate_id}")
async def candidate_detail_page(
    request: Request,
    candidate_id: int,
    current_user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    candidate = await get_candidate_by_id(db, candidate_id)

    if candidate is None:
        return templates.TemplateResponse(
            request,
            "candidate_list.html",
            context={
                "current_user": current_user,
                "candidates": [],
                "search": "",
                "page": 1,
                "per_page": 20,
                "total_count": 0,
                "total_pages": 1,
                "error": "Candidate not found.",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "candidate_detail.html",
        context={
            "current_user": current_user,
            "candidate": candidate,
        },
    )


@router.get("/{candidate_id}/edit")
async def candidate_edit_page(
    request: Request,
    candidate_id: int,
    current_user: User = Depends(require_role(ROLES_CAN_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    candidate = await get_candidate_by_id(db, candidate_id)

    if candidate is None:
        return RedirectResponse(url="/candidates", status_code=302)

    return templates.TemplateResponse(
        request,
        "candidate_form.html",
        context={
            "current_user": current_user,
            "candidate": candidate,
        },
    )


@router.post("/{candidate_id}")
async def candidate_edit_submit(
    request: Request,
    candidate_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    skills: str = Form(""),
    resume_text: str = Form(""),
    current_user: User = Depends(require_role(ROLES_CAN_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    existing = await get_candidate_by_id(db, candidate_id)
    if existing is None:
        return RedirectResponse(url="/candidates", status_code=302)

    candidate, error = await edit_candidate(
        db=db,
        candidate_id=candidate_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone if phone else None,
        linkedin_url=linkedin_url if linkedin_url else None,
        resume_text=resume_text if resume_text else None,
        skills_csv=skills if skills else None,
    )

    if candidate is None:
        logger.info(
            "Candidate edit failed by user '%s' for id=%d: %s",
            current_user.username,
            candidate_id,
            error,
        )
        return templates.TemplateResponse(
            request,
            "candidate_form.html",
            context={
                "current_user": current_user,
                "candidate": existing,
                "error": error or "Failed to update candidate.",
            },
            status_code=400,
        )

    await log_action(
        db=db,
        action="update_candidate",
        user_id=current_user.id,
        entity_type="candidate",
        entity_id=candidate.id,
        details=f"Updated candidate: {candidate.first_name} {candidate.last_name} ({candidate.email})",
    )

    logger.info(
        "Candidate updated by user '%s': id=%d, name='%s %s'",
        current_user.username,
        candidate.id,
        candidate.first_name,
        candidate.last_name,
    )
    return RedirectResponse(
        url=f"/candidates/{candidate.id}",
        status_code=302,
    )