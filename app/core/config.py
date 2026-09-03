"""Application configuration via environment variables (Pydantic Settings)."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me"


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

    # Async SQLAlchemy URL used at runtime by the application. Should point at a
    # NON-owner, non-superuser role so PostgreSQL RLS is enforced (ADR-002).
    database_url: str = Field(
        default="postgresql+asyncpg://hbm_app:hbm_app@localhost:5432/hbm",
    )
    # URL used to run Alembic migrations. Should point at the OWNER role. Falls
    # back to database_url when unset (e.g. single-role local setups).
    migration_database_url: str | None = None
    db_echo: bool = False

    # Auth (ADR-003). Override JWT_SECRET_KEY in every non-local environment.
    jwt_secret_key: str = Field(
        default=DEV_JWT_SECRET,
        description="HS256 signing secret; must be overridden outside local dev.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    access_token_cookie_name: str = "access_token"
    refresh_token_cookie_name: str = "refresh_token"

    # Rate limiting for sensitive auth endpoints (per client IP, per endpoint).
    rate_limit_enabled: bool = True
    rate_limit_backend: str = Field(
        default="memory",
        description="Rate limit store: memory (default) or redis.",
    )
    redis_url: str | None = Field(
        default=None,
        description="Redis URL when rate_limit_backend=redis.",
    )
    auth_rate_limit_max: int = 20
    auth_rate_limit_window_seconds: int = 60

    # CORS — comma-separated origins for the separate Next.js frontend.
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed browser origins (comma-separated in env).",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


def validate_runtime_settings(settings: Settings) -> None:
    """Fail fast when required production settings are missing."""
    if settings.environment in ("local", "ci"):
        return
    if settings.jwt_secret_key == DEV_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a non-default value outside local/ci environments"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
