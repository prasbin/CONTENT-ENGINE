"""Test helpers (importable from any test module)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings

TEST_TOKEN = "test-token-abc123"


def build_settings(tmp_path: Path, **overrides: object) -> Settings:
    """Build isolated settings that never read a real .env file."""
    options: dict[str, object] = {
        "_env_file": None,
        "app_env": "testing",
        "ce_database_url": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "ce_storage_path": str(tmp_path / "storage"),
        "ce_api_token": TEST_TOKEN,
        "ce_log_level": "DEBUG",
    }
    options.update(overrides)
    return Settings(**options)  # type: ignore[arg-type]
