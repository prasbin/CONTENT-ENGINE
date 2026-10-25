"""Storage abstraction.

``StorageProvider`` is the contract; ``LocalStorage`` is the Phase 1
implementation. S3/MinIO/etc. implementations can replace it later
without touching callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageProvider(Protocol):
    """Binary object storage keyed by relative object names."""

    def save(self, name: str, data: bytes) -> str:
        """Store bytes under ``name``; returns the canonical object name."""
        ...

    def save_file(self, name: str, source_path: Path) -> str:
        """Copy a local file into storage without loading it into memory.

        Used for large artifacts (source videos). ``source_path`` is a
        trusted temporary path, never a user-supplied one.
        """
        ...

    def read(self, name: str) -> bytes:
        """Return stored bytes."""
        ...

    def exists(self, name: str) -> bool:
        """Return True when the object exists."""
        ...

    def delete(self, name: str) -> None:
        """Remove the object; raises NotFoundError when missing."""
        ...

    def path_for(self, name: str) -> Path:
        """Local filesystem path for the object (local/sidecar storage only)."""
        ...
