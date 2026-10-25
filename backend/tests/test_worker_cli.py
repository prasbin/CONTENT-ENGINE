"""Tests for worker CLI script execution."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_worker_cli_help() -> None:
    script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "worker.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "run" in res.stdout
    assert "recover" in res.stdout


def test_worker_cli_recover_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "worker.py"

    res = subprocess.run(
        [sys.executable, str(script_path), "recover"],
        env={**__import__("os").environ, "CE_DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Requeued 0 downloading job(s)" in res.stdout
