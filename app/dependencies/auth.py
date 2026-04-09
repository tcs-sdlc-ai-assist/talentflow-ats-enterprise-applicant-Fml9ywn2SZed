import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_session_token
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Read the session cookie, validate it, and return the User or None."""
    session_cookie = request.cookies.get("session")
    if not session_cookie:
        return None

    payload = decode_session_token(session_cookie)
    if payload is None:
        return None

    user_id = payload.get("user_id")
    if user_id is None:
        logger.warning("Session token missing user_id")
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("Session references non-existent user_id=%s", user_id)
        return None

    if not user.is_active:
        logger.info("Session references inactive user_id=%s", user_id)
        return None

    return user


async def require_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that raises 401 if the user is not authenticated."""
    user = await get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_role(allowed_roles: list[str]) -> Callable:
    """Factory that returns a dependency checking the user has one of the allowed roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(["admin"]))])
        async def admin_page(): ...

    Or as a parameter dependency:
        async def handler(user: User = Depends(require_role(["admin", "recruiter"]))):
            ...
    """

    async def _role_checker(
        request: Request,
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user = await get_current_user(request, db)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if user.role not in allowed_roles:
            logger.warning(
                "User %s (role=%s) denied access; allowed roles: %s",
                user.username,
                user.role,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return user

    return _role_checker