"""Local filesystem storage implementation."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from app.core.errors import NotFoundError, StoragePathError

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


class LocalStorage:
    """Stores objects under a configured root directory.

    All names are treated as relative POSIX paths. Absolute paths,
    drive letters, and ``..`` segments are rejected to prevent path
    traversal outside the storage root.
    """

    def __init__(self, root: str | Path) -> None:
        if not str(root).strip():
            raise ValueError("storage root must not be empty")
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, name: str) -> Path:
        if not name or not name.strip():
            raise StoragePathError("storage object name must not be empty")
        name = name.strip().replace("\\", "/")
        if name.startswith("/") or _WINDOWS_DRIVE.match(name):
            raise StoragePathError("absolute paths are not allowed in storage names")
        pure = PurePosixPath(name)
        if ".." in pure.parts:
            raise StoragePathError("path traversal ('..') is not allowed in storage names")
        root = self._root.resolve()
        target = (root / Path(*pure.parts)).resolve()
        if not target.is_relative_to(root):
            raise StoragePathError("storage name resolves outside the storage root")
        return target

    @staticmethod
    def _canonical(target: Path, root: Path) -> str:
        return target.relative_to(root).as_posix()

    def save(self, name: str, data: bytes) -> str:
        target = self._resolve(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self._canonical(target, self._root.resolve())

    def read(self, name: str) -> bytes:
        target = self._resolve(name)
        if not target.is_file():
            raise NotFoundError(f"storage object '{name}' not found")
        return target.read_bytes()

    def exists(self, name: str) -> bool:
        return self._resolve(name).is_file()

    def delete(self, name: str) -> None:
        target = self._resolve(name)
        if not target.is_file():
            raise NotFoundError(f"storage object '{name}' not found")
        target.unlink()

    def path_for(self, name: str) -> Path:
        return self._resolve(name)
