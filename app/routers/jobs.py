import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_login, require_role
from app.models.user import User
from app.services.audit_service import log_action
from app.services.job_service import (
    VALID_JOB_TYPES,
    VALID_STATUSES,
    create_job,
    edit_job,
    get_all_departments,
    get_hiring_managers,
    get_job_by_id,
    list_jobs,
    toggle_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/jobs")
async def jobs_list_page(
    request: Request,
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_login),
):
    jobs = await list_jobs(
        db=db,
        user=current_user,
        search=search,
        status_filter=status,
    )

    return templates.TemplateResponse(
        request,
        "job_list.html",
        context={
            "current_user": current_user,
            "jobs": jobs,
            "search": search,
            "status_filter": status,
        },
    )


@router.get("/jobs/create")
async def job_create_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "hiring_manager", "recruiter"])),
):
    departments = await get_all_departments(db)
    users = await get_hiring_managers(db)

    return templates.TemplateResponse(
        request,
        "job_form.html",
        context={
            "current_user": current_user,
            "job": None,
            "departments": departments,
            "users": users,
            "job_types": VALID_JOB_TYPES,
            "statuses": VALID_STATUSES,
            "errors": None,
        },
    )


@router.post("/jobs")
async def job_create_submit(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    department_id: str = Form(...),
    hiring_manager_id: str = Form(...),
    location: str = Form(...),
    job_type: str = Form(...),
    status: str = Form("Draft"),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "hiring_manager", "recruiter"])),
):
    errors: dict = {}

    try:
        dept_id = int(department_id)
    except (ValueError, TypeError):
        errors["department_id"] = "Please select a valid department."
        dept_id = 0

    try:
        mgr_id = int(hiring_manager_id)
    except (ValueError, TypeError):
        errors["hiring_manager_id"] = "Please select a valid hiring manager."
        mgr_id = 0

    parsed_salary_min: Optional[int] = None
    if salary_min and salary_min.strip():
        try:
            parsed_salary_min = int(salary_min.strip())
        except (ValueError, TypeError):
            errors["salary_min"] = "Minimum salary must be a number."

    parsed_salary_max: Optional[int] = None
    if salary_max and salary_max.strip():
        try:
            parsed_salary_max = int(salary_max.strip())
        except (ValueError, TypeError):
            errors["salary_max"] = "Maximum salary must be a number."

    if errors:
        departments = await get_all_departments(db)
        users = await get_hiring_managers(db)
        return templates.TemplateResponse(
            request,
            "job_form.html",
            context={
                "current_user": current_user,
                "job": None,
                "departments": departments,
                "users": users,
                "job_types": VALID_JOB_TYPES,
                "statuses": VALID_STATUSES,
                "errors": errors,
            },
            status_code=400,
        )

    job, error_message = await create_job(
        db=db,
        title=title,
        description=description,
        department_id=dept_id,
        hiring_manager_id=mgr_id,
        location=location,
        job_type=job_type,
        status=status,
        salary_min=parsed_salary_min,
        salary_max=parsed_salary_max,
        user=current_user,
    )

    if job is None:
        departments = await get_all_departments(db)
        users = await get_hiring_managers(db)
        errors["general"] = error_message or "Failed to create job posting."
        return templates.TemplateResponse(
            request,
            "job_form.html",
            context={
                "current_user": current_user,
                "job": None,
                "departments": departments,
                "users": users,
                "job_types": VALID_JOB_TYPES,
                "statuses": VALID_STATUSES,
                "errors": errors,
            },
            status_code=400,
        )

    await log_action(
        db=db,
        action="create_job",
        user_id=current_user.id,
        entity_type="job_posting",
        entity_id=job.id,
        details=f"Created job posting: {job.title}",
    )

    logger.info(
        "User '%s' created job posting id=%d title='%s'",
        current_user.username,
        job.id,
        job.title,
    )
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=302)


@router.get("/jobs/{job_id}")
async def job_detail_page(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_login),
):
    job = await get_job_by_id(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    return templates.TemplateResponse(
        request,
        "job_detail.html",
        context={
            "current_user": current_user,
            "job": job,
        },
    )


@router.get("/jobs/{job_id}/edit")
async def job_edit_page(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "hiring_manager", "recruiter"])),
):
    job = await get_job_by_id(db, job_id)
    if job is None:
        return RedirectResponse(url="/jobs", status_code=302)

    if current_user.role == "hiring_manager" and job.hiring_manager_id != current_user.id:
        return RedirectResponse(url="/jobs", status_code=302)

    departments = await get_all_departments(db)
    users = await get_hiring_managers(db)

    return templates.TemplateResponse(
        request,
        "job_form.html",
        context={
            "current_user": current_user,
            "job": job,
            "departments": departments,
            "users": users,
            "job_types": VALID_JOB_TYPES,
            "statuses": VALID_STATUSES,
            "errors": None,
        },
    )


@router.post("/jobs/{job_id}")
async def job_edit_submit(
    request: Request,
    job_id: int,
    title: str = Form(...),
    description: str = Form(...),
    department_id: str = Form(...),
    hiring_manager_id: str = Form(...),
    location: str = Form(...),
    job_type: str = Form(...),
    status: str = Form("Draft"),
    salary_min: Optional[str] = Form(None),
    salary_max: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "hiring_manager", "recruiter"])),
):
    errors: dict = {}

    try:
        dept_id = int(department_id)
    except (ValueError, TypeError):
        errors["department_id"] = "Please select a valid department."
        dept_id = None

    try:
        mgr_id = int(hiring_manager_id)
    except (ValueError, TypeError):
        errors["hiring_manager_id"] = "Please select a valid hiring manager."
        mgr_id = None

    parsed_salary_min: Optional[int] = None
    if salary_min and salary_min.strip():
        try:
            parsed_salary_min = int(salary_min.strip())
        except (ValueError, TypeError):
            errors["salary_min"] = "Minimum salary must be a number."

    parsed_salary_max: Optional[int] = None
    if salary_max and salary_max.strip():
        try:
            parsed_salary_max = int(salary_max.strip())
        except (ValueError, TypeError):
            errors["salary_max"] = "Maximum salary must be a number."

    if errors:
        job = await get_job_by_id(db, job_id)
        departments = await get_all_departments(db)
        users = await get_hiring_managers(db)
        return templates.TemplateResponse(
            request,
            "job_form.html",
            context={
                "current_user": current_user,
                "job": job,
                "departments": departments,
                "users": users,
                "job_types": VALID_JOB_TYPES,
                "statuses": VALID_STATUSES,
                "errors": errors,
            },
            status_code=400,
        )

    job, error_message = await edit_job(
        db=db,
        job_id=job_id,
        title=title,
        description=description,
        department_id=dept_id,
        hiring_manager_id=mgr_id,
        location=location,
        job_type=job_type,
        status=status,
        salary_min=parsed_salary_min,
        salary_max=parsed_salary_max,
        user=current_user,
    )

    if job is None:
        existing_job = await get_job_by_id(db, job_id)
        departments = await get_all_departments(db)
        users = await get_hiring_managers(db)
        errors["general"] = error_message or "Failed to update job posting."
        return templates.TemplateResponse(
            request,
            "job_form.html",
            context={
                "current_user": current_user,
                "job": existing_job,
                "departments": departments,
                "users": users,
                "job_types": VALID_JOB_TYPES,
                "statuses": VALID_STATUSES,
                "errors": errors,
            },
            status_code=400,
        )

    await log_action(
        db=db,
        action="update_job",
        user_id=current_user.id,
        entity_type="job_posting",
        entity_id=job.id,
        details=f"Updated job posting: {job.title}",
    )

    logger.info(
        "User '%s' updated job posting id=%d title='%s'",
        current_user.username,
        job.id,
        job.title,
    )
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=302)


@router.post("/jobs/{job_id}/status")
async def job_status_update(
    request: Request,
    job_id: int,
    status: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "hiring_manager", "recruiter"])),
):
    job, error_message = await toggle_status(
        db=db,
        job_id=job_id,
        new_status=status,
        user=current_user,
    )

    if job is None:
        logger.warning(
            "User '%s' failed to update status for job id=%d: %s",
            current_user.username,
            job_id,
            error_message,
        )
        return RedirectResponse(url="/jobs", status_code=302)

    await log_action(
        db=db,
        action="update_job_status",
        user_id=current_user.id,
        entity_type="job_posting",
        entity_id=job.id,
        details=f"Changed job status to: {job.status}",
    )

    logger.info(
        "User '%s' changed job id=%d status to '%s'",
        current_user.username,
        job.id,
        job.status,
    )
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=302)