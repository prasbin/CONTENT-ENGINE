"""Filesystem anchors for the project.

All relative paths (``.env``, SQLite files, storage directories) resolve
against the repository root instead of the current working directory, so
behavior is identical whether the server is started from the project
root, from ``backend/``, or by a Linux service manager.
"""

from __future__ import annotations

from pathlib import Path

#: Repository root: backend/app/core/paths.py -> three levels up.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]


def default_env_file() -> Path:
    """Absolute path of the project's ``.env`` file (may not exist yet)."""
    return PROJECT_ROOT / ".env"


def project_path(path: str | Path) -> Path:
    """Resolve ``path`` against the repository root.

    Absolute paths (and ``~``) are expanded and returned unchanged;
    relative paths are anchored at :data:`PROJECT_ROOT`.
    """
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()
