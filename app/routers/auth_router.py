import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.auth_service import (
    authenticate_user,
    create_session_for_user,
    register_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/login")
async def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        context={"current_user": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, username, password)
    if user is None:
        logger.info("Failed login attempt for username: %s", username)
        return templates.TemplateResponse(
            request,
            "login.html",
            context={
                "current_user": None,
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=400,
        )

    session_token = create_session_for_user(user)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=3600,
        path="/",
    )
    logger.info("User '%s' logged in successfully.", user.username)
    return response


@router.get("/register")
async def register_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "register.html",
        context={"current_user": None},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    errors: list[str] = []

    if not username or len(username.strip()) < 3:
        errors.append("Username must be at least 3 characters.")
    if not email or "@" not in email:
        errors.append("A valid email address is required.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request,
            "register.html",
            context={
                "current_user": None,
                "errors": errors,
                "username": username,
                "email": email,
            },
            status_code=400,
        )

    user, error_message = await register_user(
        db=db,
        username=username.strip(),
        email=email.strip().lower(),
        password=password,
    )

    if user is None:
        logger.info("Registration failed for username '%s': %s", username, error_message)
        return templates.TemplateResponse(
            request,
            "register.html",
            context={
                "current_user": None,
                "error": error_message or "Registration failed. Please try again.",
                "username": username,
                "email": email,
            },
            status_code=400,
        )

    session_token = create_session_for_user(user)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=3600,
        path="/",
    )
    logger.info("User '%s' registered and logged in successfully.", user.username)
    return response


@router.post("/logout")
async def logout(
    request: Request,
):
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(
        key="session",
        path="/",
    )
    logger.info("User logged out.")
    return response