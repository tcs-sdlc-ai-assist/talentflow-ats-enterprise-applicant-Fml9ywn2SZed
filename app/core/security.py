import logging
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

_SESSION_SALT = "session-cookie"


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        logger.warning("Password verification failed due to an unexpected error")
        return False


def create_session_token(data: dict) -> str:
    """Create a signed session token containing the provided data.

    Args:
        data: Dictionary with session payload (e.g. user_id, username, role).

    Returns:
        A URL-safe signed token string.
    """
    return serializer.dumps(data, salt=_SESSION_SALT)


def decode_session_token(token: str, max_age: Optional[int] = None) -> Optional[dict]:
    """Decode and verify a signed session token.

    Args:
        token: The signed token string to decode.
        max_age: Maximum age in seconds. Defaults to settings.SESSION_MAX_AGE.

    Returns:
        The decoded payload dictionary, or None if the token is invalid or expired.
    """
    if max_age is None:
        max_age = settings.SESSION_MAX_AGE
    try:
        data = serializer.loads(token, salt=_SESSION_SALT, max_age=max_age)
        if not isinstance(data, dict):
            logger.warning("Session token payload is not a dict")
            return None
        return data
    except SignatureExpired:
        logger.info("Session token has expired")
        return None
    except BadSignature:
        logger.warning("Session token has an invalid signature")
        return None
    except Exception:
        logger.warning("Unexpected error decoding session token")
        return None