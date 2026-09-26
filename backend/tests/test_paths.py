"""Path resolution tests: everything anchors at the repository root."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core import paths as paths_module
from app.core.paths import PROJECT_ROOT, default_env_file, project_path
from app.main import create_app
from helpers import build_settings


def test_project_root_is_repository_root() -> None:
    assert (PROJECT_ROOT / "backend" / "app").is_dir()
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_default_env_file_is_absolute() -> None:
    env_file = default_env_file()
    assert env_file.is_absolute()
    assert env_file.name == ".env"
    assert env_file.parent == PROJECT_ROOT


def test_paths_are_cwd_independent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_env_file() == PROJECT_ROOT / ".env"
    assert project_path("data/x.db") == (PROJECT_ROOT / "data" / "x.db").resolve()
    assert project_path("./data") == (PROJECT_ROOT / "data").resolve()


def test_project_path_keeps_absolute_paths(tmp_path: Path) -> None:
    absolute = tmp_path / "sub" / "file.db"
    assert project_path(absolute) == absolute
    assert project_path(str(absolute)) == absolute


def test_project_path_respects_monkeypatched_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths_module, "PROJECT_ROOT", tmp_path)
    assert project_path("data") == (tmp_path / "data").resolve()
    assert default_env_file() == tmp_path / ".env"


def test_project_root_env_file_is_loaded_regardless_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Behavioral check: a project-root .env is read even from another CWD."""
    from app.core.config import Settings

    env_file = default_env_file()
    if env_file.exists():
        pytest.skip(".env already exists on this machine; skipping destructive test")
    monkeypatch.delenv("CE_PORT", raising=False)
    monkeypatch.chdir(tmp_path)
    env_file.write_text("CE_PORT=7777\n", encoding="utf-8")
    try:
        assert Settings().ce_port == 7777
    finally:
        env_file.unlink(missing_ok=True)


def test_storage_root_resolved_against_project_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths_module, "PROJECT_ROOT", tmp_path)
    settings = build_settings(tmp_path, ce_storage_path="./data/storage")
    app = create_app(settings)
    assert app.state.storage.root == (tmp_path / "data" / "storage").resolve()
