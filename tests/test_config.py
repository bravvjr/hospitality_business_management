"""Unit tests for application settings validation."""
import pytest

from app.core.config import DEV_JWT_SECRET, Settings, validate_runtime_settings


@pytest.mark.unit
def test_validate_runtime_settings_allows_local_default_secret():
    validate_runtime_settings(Settings(environment="local", jwt_secret_key=DEV_JWT_SECRET))


@pytest.mark.unit
def test_validate_runtime_settings_rejects_default_secret_in_production():
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_runtime_settings(Settings(environment="production", jwt_secret_key=DEV_JWT_SECRET))


@pytest.mark.unit
def test_cors_origins_parsed_from_comma_separated_env():
    settings = Settings(cors_origins="http://localhost:3000, https://app.example.com")
    assert settings.cors_origins == ["http://localhost:3000", "https://app.example.com"]
