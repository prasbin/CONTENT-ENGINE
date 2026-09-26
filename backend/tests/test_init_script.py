"""Tests for scripts/init_db.py (explicit database initialization)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from app.core.paths import PROJECT_ROOT
from app.db.session import create_engine_from_url
from sqlalchemy import inspect as sa_inspect

SCRIPT = PROJECT_ROOT / "scripts" / "init_db.py"


def _run(env_extra: dict[str, str], cwd: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **env_extra}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=120,
    )


@pytest.mark.parametrize("from_project_root", [True, False], ids=["from-root", "from-elsewhere"])
def test_init_db_script_creates_database(tmp_path, from_project_root: bool) -> None:
    db_path = tmp_path / "cli.db"
    cwd = str(PROJECT_ROOT) if from_project_root else str(tmp_path)
    result = _run(
        {"CE_DATABASE_URL": f"sqlite:///{db_path.as_posix()}", "APP_ENV": "testing"},
        cwd=cwd,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert db_path.is_file()
    assert "Database initialized" in result.stdout
    assert "jobs" in result.stdout

    engine = create_engine_from_url(f"sqlite:///{db_path.as_posix()}")
    try:
        assert "jobs" in sa_inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_init_db_script_reports_invalid_config(tmp_path) -> None:
    result = _run({"CE_PORT": "0"}, cwd=str(tmp_path))
    assert result.returncode == 1
    assert "ERROR" in result.stderr
    assert "CE_PORT" in result.stderr
