"""Environment-driven configuration.

All runtime configuration comes from environment variables (or an optional
local `.env` file, which is git-ignored). No secrets are hard-coded.

Environment variables:
    APP_ENV, CE_HOST, CE_PORT, CE_DATABASE_URL, CE_STORAGE_PATH,
    CE_API_TOKEN, CE_PUBLIC_BASE_URL, CE_CORS_ORIGINS,
    CE_OLLAMA_BASE_URL, CE_LOG_LEVEL
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.paths import default_env_file

AppEnv = Literal["development", "testing", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DEFAULT_CORS_ORIGINS: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

#: 2 GiB default cap on a single source download.
DEFAULT_MAX_SOURCE_BYTES: int = 2 * 1024 * 1024 * 1024
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS: int = 600
DEFAULT_ALLOWED_SCHEMES: tuple[str, ...] = ("http", "https")
DEFAULT_ALLOWED_MEDIA_EXTENSIONS: tuple[str, ...] = (
    "mp4",
    "mov",
    "mkv",
    "webm",
    "m4v",
    "avi",
    "flv",
    "ts",
)
DEFAULT_MAX_ACQUISITION_ATTEMPTS: int = 3


class ConfigurationError(ValueError):
    """Raised when environment configuration is missing or invalid."""


def _split_origins(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("CE_CORS_ORIGINS must be a comma-separated string or a list of origins")


class Settings(BaseSettings):
    """Typed, validated application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        # Absolute path: the project .env is found regardless of CWD.
        env_file=default_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )

    app_env: AppEnv = Field(default="development", validation_alias="APP_ENV")
    ce_host: str = Field(default="127.0.0.1", min_length=1, validation_alias="CE_HOST")
    ce_port: int = Field(default=8000, ge=1, le=65535, validation_alias="CE_PORT")
    ce_database_url: str = Field(
        default="sqlite:///./data/content_engine.db",
        min_length=1,
        validation_alias="CE_DATABASE_URL",
    )
    ce_storage_path: str = Field(
        default="./data/storage", min_length=1, validation_alias="CE_STORAGE_PATH"
    )
    ce_api_token: str | None = Field(default=None, validation_alias="CE_API_TOKEN")
    ce_public_base_url: str | None = Field(default=None, validation_alias="CE_PUBLIC_BASE_URL")
    # NoDecode: accept a plain comma-separated string instead of strict JSON.
    ce_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        validation_alias="CE_CORS_ORIGINS",
    )
    ce_ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="CE_OLLAMA_BASE_URL",
    )
    ce_log_level: LogLevel = Field(default="INFO", validation_alias="CE_LOG_LEVEL")

    # --- Phase 2: video acquisition -------------------------------------
    ce_max_source_bytes: int = Field(
        default=DEFAULT_MAX_SOURCE_BYTES,
        ge=1024,
        validation_alias="CE_MAX_SOURCE_BYTES",
    )
    ce_download_timeout_seconds: int = Field(
        default=DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
        ge=1,
        le=86400,
        validation_alias="CE_DOWNLOAD_TIMEOUT_SECONDS",
    )
    ce_allowed_schemes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_SCHEMES),
        validation_alias="CE_ALLOWED_SCHEMES",
    )
    ce_require_media_probe: bool = Field(
        default=True,
        validation_alias="CE_REQUIRE_MEDIA_PROBE",
    )
    ce_allowed_media_extensions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_MEDIA_EXTENSIONS),
        validation_alias="CE_ALLOWED_MEDIA_EXTENSIONS",
    )
    ce_max_acquisition_attempts: int = Field(
        default=DEFAULT_MAX_ACQUISITION_ATTEMPTS,
        ge=1,
        le=20,
        validation_alias="CE_MAX_ACQUISITION_ATTEMPTS",
    )
    ce_ffprobe_path: str = Field(
        default="ffprobe",
        min_length=1,
        validation_alias="CE_FFPROBE_PATH",
    )

    @field_validator("ce_cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        return _split_origins(value)

    @field_validator("ce_allowed_schemes", mode="before")
    @classmethod
    def _parse_allowed_schemes(cls, value: object) -> list[str]:
        schemes = _split_origins(value)
        normalized = []
        for scheme in schemes:
            scheme = scheme.lower().strip()
            # Only network schemes may ever reach the downloader: this
            # blocks file://, javascript:, data:, etc. at the config layer.
            if scheme not in ("http", "https"):
                raise ValueError(
                    f"unsupported URL scheme '{scheme}' (only http and https are allowed)"
                )
            normalized.append(scheme)
        if not normalized:
            raise ValueError("CE_ALLOWED_SCHEMES must contain at least one scheme")
        return normalized

    @field_validator("ce_allowed_media_extensions", mode="before")
    @classmethod
    def _parse_allowed_extensions(cls, value: object) -> list[str]:
        extensions = _split_origins(value)
        normalized = []
        for ext in extensions:
            ext = ext.lower().lstrip(".")
            if not ext.isalnum():
                raise ValueError(f"invalid media extension '{ext}'")
            normalized.append(ext)
        if not normalized:
            raise ValueError("CE_ALLOWED_MEDIA_EXTENSIONS must contain at least one extension")
        return normalized

    @field_validator("ce_public_base_url", "ce_ollama_base_url")
    @classmethod
    def _http_urls_only(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("must be an http:// or https:// URL")
        return value.rstrip("/")

    @field_validator("ce_api_token")
    @classmethod
    def _strip_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip()
        return token or None

    @classmethod
    def load(cls) -> Settings:
        """Load settings, translating validation errors into clear messages."""
        try:
            return cls()
        except ValidationError as exc:
            aliases = {
                name: str(field.validation_alias or name)
                for name, field in cls.model_fields.items()
            }
            details = []
            for err in exc.errors():
                loc = err.get("loc", ())
                field_name = str(loc[0]) if loc else "settings"
                details.append(
                    f"{aliases.get(field_name, field_name)}: {err.get('msg', 'invalid')}"
                )
            raise ConfigurationError("invalid configuration -> " + "; ".join(details)) from exc

    @property
    def auth_enabled(self) -> bool:
        return self.ce_api_token is not None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return list(self.ce_cors_origins)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings.load()


def clear_settings_cache() -> None:
    """Clear the cached settings (used by tests)."""
    get_settings.cache_clear()
