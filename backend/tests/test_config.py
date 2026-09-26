"""Configuration loading and validation tests."""

from __future__ import annotations

import pytest
from app.core.config import (
    DEFAULT_CORS_ORIGINS,
    ConfigurationError,
    Settings,
    clear_settings_cache,
    get_settings,
)

ENV_VARS = (
    "APP_ENV",
    "CE_HOST",
    "CE_PORT",
    "CE_DATABASE_URL",
    "CE_STORAGE_PATH",
    "CE_API_TOKEN",
    "CE_PUBLIC_BASE_URL",
    "CE_CORS_ORIGINS",
    "CE_OLLAMA_BASE_URL",
    "CE_LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def test_defaults_load_without_env() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.ce_host == "127.0.0.1"
    assert settings.ce_port == 8000
    assert settings.ce_database_url == "sqlite:///./data/content_engine.db"
    assert settings.ce_storage_path == "./data/storage"
    assert settings.ce_cors_origins == list(DEFAULT_CORS_ORIGINS)
    assert settings.ce_log_level == "INFO"
    assert settings.auth_enabled is False


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("CE_PORT", "9090")
    monkeypatch.setenv("CE_API_TOKEN", "  super-secret  ")
    monkeypatch.setenv("CE_LOG_LEVEL", "WARNING")

    settings = Settings.load()

    assert settings.app_env == "staging"
    assert settings.ce_port == 9090
    assert settings.ce_api_token == "super-secret"
    assert settings.ce_log_level == "WARNING"
    assert settings.auth_enabled is True
    assert settings.is_production is False


def test_invalid_port_fails_with_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_PORT", "0")
    with pytest.raises(ConfigurationError) as excinfo:
        Settings.load()
    message = str(excinfo.value)
    assert "CE_PORT" in message
    assert "invalid configuration" in message


def test_invalid_app_env_fails_with_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "productionn")
    with pytest.raises(ConfigurationError) as excinfo:
        Settings.load()
    assert "APP_ENV" in str(excinfo.value)


def test_invalid_url_fails_with_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_OLLAMA_BASE_URL", "ftp://models.local")
    with pytest.raises(ConfigurationError) as excinfo:
        Settings.load()
    assert "CE_OLLAMA_BASE_URL" in str(excinfo.value)


def test_cors_origins_accept_comma_separated_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CE_CORS_ORIGINS", "http://a.example, http://b.example")
    settings = Settings(_env_file=None)
    assert settings.ce_cors_origins == ["http://a.example", "http://b.example"]
    assert settings.cors_origin_list == ["http://a.example", "http://b.example"]


def test_production_url_property(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    assert Settings(_env_file=None).is_production is True


def test_get_settings_is_cached() -> None:
    clear_settings_cache()
    first = get_settings()
    second = get_settings()
    assert first is second
    clear_settings_cache()
    assert get_settings() is not first
