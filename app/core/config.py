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


@lru_cache
def get_settings() -> Settings:
    return Settings()
