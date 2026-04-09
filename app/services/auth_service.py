import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)
from app.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_ROLE = "interviewer"


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> Optional[User]:
    """Authenticate a user by username and password.

    Args:
        db: Async database session.
        username: The username to look up.
        password: The plain-text password to verify.

    Returns:
        The User object if credentials are valid, None otherwise.
    """
    try:
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalars().first()

        if user is None:
            logger.info("Login attempt for non-existent user: %s", username)
            return None

        if not user.is_active:
            logger.info("Login attempt for inactive user: %s", username)
            return None

        if not verify_password(password, user.hashed_password):
            logger.info("Invalid password for user: %s", username)
            return None

        logger.info("User authenticated successfully: %s", username)
        return user
    except Exception:
        logger.exception("Error during authentication for user: %s", username)
        return None


async def register_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
) -> tuple[Optional[User], Optional[str]]:
    """Register a new user account.

    Args:
        db: Async database session.
        username: Desired username (3-32 chars).
        email: User email address.
        password: Plain-text password (min 8 chars).
        full_name: Optional full name.
        role: Optional role override. Defaults to 'interviewer'.

    Returns:
        A tuple of (User, None) on success, or (None, error_message) on failure.
    """
    if not username or len(username.strip()) < 3:
        return None, "Username must be at least 3 characters."

    if len(username.strip()) > 32:
        return None, "Username must be at most 32 characters."

    if not email or "@" not in email:
        return None, "A valid email address is required."

    if not password or len(password) < 8:
        return None, "Password must be at least 8 characters."

    username = username.strip()
    email = email.strip().lower()

    try:
        existing_username = await db.execute(
            select(User).where(User.username == username)
        )
        if existing_username.scalars().first() is not None:
            logger.info("Registration failed: username '%s' already exists", username)
            return None, "Username already exists."

        existing_email = await db.execute(
            select(User).where(User.email == email)
        )
        if existing_email.scalars().first() is not None:
            logger.info("Registration failed: email '%s' already exists", email)
            return None, "Email already exists."

        hashed = hash_password(password)
        user_role = role if role else DEFAULT_ROLE

        user = User(
            username=username,
            email=email,
            hashed_password=hashed,
            full_name=full_name,
            role=user_role,
            is_active=1,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        logger.info(
            "User registered successfully: %s (role=%s)", username, user_role
        )
        return user, None
    except Exception:
        logger.exception("Error during registration for user: %s", username)
        return None, "An unexpected error occurred during registration."


def create_session_for_user(user: User) -> str:
    """Create a signed session token for the given user.

    Args:
        user: The authenticated User object.

    Returns:
        A signed session token string.
    """
    data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
    }
    token = create_session_token(data)
    logger.info("Session token created for user: %s", user.username)
    return token


def validate_session(token: str) -> Optional[dict]:
    """Validate a session token and return the payload.

    Args:
        token: The signed session token string.

    Returns:
        The decoded payload dict with user_id, username, role, or None if invalid.
    """
    data = decode_session_token(token)
    if data is None:
        return None

    required_keys = {"user_id", "username", "role"}
    if not required_keys.issubset(data.keys()):
        logger.warning("Session token missing required keys: %s", data.keys())
        return None

    return data


async def get_user_by_id(
    db: AsyncSession,
    user_id: int,
) -> Optional[User]:
    """Fetch a user by their ID.

    Args:
        db: Async database session.
        user_id: The user's primary key.

    Returns:
        The User object if found and active, None otherwise.
    """
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()
        if user is None:
            return None
        if not user.is_active:
            logger.info("Fetched inactive user by id: %d", user_id)
            return None
        return user
    except Exception:
        logger.exception("Error fetching user by id: %d", user_id)
        return None


async def get_current_user_from_session(
    db: AsyncSession,
    token: Optional[str],
) -> Optional[User]:
    """Resolve the current user from a session token.

    Validates the token, then fetches the user from the database.

    Args:
        db: Async database session.
        token: The session cookie value, or None.

    Returns:
        The User object if the session is valid and user exists, None otherwise.
    """
    if not token:
        return None

    session_data = validate_session(token)
    if session_data is None:
        return None

    user_id = session_data.get("user_id")
    if user_id is None:
        return None

    return await get_user_by_id(db, user_id)


async def ensure_default_admin(
    db: AsyncSession,
    admin_username: str,
    admin_password: str,
    admin_email: Optional[str] = None,
) -> None:
    """Ensure a default admin user exists in the database.

    Creates the admin user if it does not already exist.

    Args:
        db: Async database session.
        admin_username: The admin username from settings.
        admin_password: The admin password from settings.
        admin_email: Optional admin email. Defaults to admin_username@talentflow.local.
    """
    try:
        result = await db.execute(
            select(User).where(User.username == admin_username)
        )
        existing = result.scalars().first()

        if existing is not None:
            logger.info("Default admin user '%s' already exists.", admin_username)
            return

        if not admin_email:
            admin_email = f"{admin_username}@talentflow.local"

        hashed = hash_password(admin_password)
        admin_user = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hashed,
            full_name="System Administrator",
            role="admin",
            is_active=1,
        )
        db.add(admin_user)
        await db.commit()

        logger.info(
            "Default admin user '%s' created successfully.", admin_username
        )
    except Exception:
        logger.exception("Error ensuring default admin user exists.")
        await db.rollback()