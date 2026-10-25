"""Tests for StorageProvider.save_file."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.errors import NotFoundError
from app.storage.local import LocalStorage


def test_save_file_success(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    storage = LocalStorage(storage_root)

    src = tmp_path / "incoming.mp4"
    src.write_bytes(b"FAKE-VIDEO-BYTES-12345")

    canonical = storage.save_file("sources/job-1/source.mp4", src)
    assert canonical == "sources/job-1/source.mp4"
    assert storage.read("sources/job-1/source.mp4") == b"FAKE-VIDEO-BYTES-12345"


def test_save_file_not_found(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    missing = tmp_path / "does_not_exist.mp4"
    with pytest.raises(NotFoundError):
        storage.save_file("sources/job-1/source.mp4", missing)
