"""Application configuration via environment variables (Pydantic Settings)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Hospitality Business Management API"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Async SQLAlchemy URL (asyncpg driver). Overridden per environment.
    database_url: str = Field(
        default="postgresql+asyncpg://hbm:hbm@localhost:5432/hbm",
    )
    db_echo: bool = False

    # Auth (ADR-003). Override JWT_SECRET_KEY in every non-local environment.
    jwt_secret_key: str = Field(
        default="dev-only-change-me",
        description="HS256 signing secret; must be overridden outside local dev.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    access_token_cookie_name: str = "access_token"
    refresh_token_cookie_name: str = "refresh_token"


@lru_cache
def get_settings() -> Settings:
    return Settings()
