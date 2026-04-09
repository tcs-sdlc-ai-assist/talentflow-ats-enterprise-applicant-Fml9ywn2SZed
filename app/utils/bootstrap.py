import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.security import hash_password

logger = logging.getLogger(__name__)


async def ensure_admin_exists() -> None:
    """Check if a System Admin user exists; if not, create one using config defaults.

    Uses DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD from settings.
    The created user is assigned the 'admin' role.
    """
    from app.models.user import User

    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
            )
            existing_admin = result.scalars().first()

            if existing_admin is not None:
                logger.info(
                    "Admin user '%s' already exists (id=%s). Skipping bootstrap.",
                    existing_admin.username,
                    existing_admin.id,
                )
                return

            admin_user = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                email=f"{settings.DEFAULT_ADMIN_USERNAME}@talentflow.local",
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                full_name="System Administrator",
                role="admin",
                is_active=1,
            )
            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)

            logger.info(
                "Default admin user '%s' created successfully (id=%s, role=%s).",
                admin_user.username,
                admin_user.id,
                admin_user.role,
            )
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to bootstrap default admin user '%s'.",
                settings.DEFAULT_ADMIN_USERNAME,
            )
            raise