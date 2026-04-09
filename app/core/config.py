import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    SECRET_KEY: str = "change-me-to-a-random-secret-key-in-production"
    DATABASE_URL: str = "sqlite+aiosqlite:///./talentflow.db"
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    SESSION_MAX_AGE: int = 3600
    DEBUG: bool = False


settings = Settings()