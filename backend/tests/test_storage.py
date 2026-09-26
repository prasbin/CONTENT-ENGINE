"""LocalStorage abstraction tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.errors import NotFoundError, StoragePathError
from app.storage.base import StorageProvider
from app.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "store")


def test_save_read_exists_delete_round_trip(storage: LocalStorage) -> None:
    name = storage.save("jobs/abc/clip.mp4", b"\x00\x01binary-data")
    assert name == "jobs/abc/clip.mp4"
    assert storage.exists("jobs/abc/clip.mp4") is True
    assert storage.read("jobs/abc/clip.mp4") == b"\x00\x01binary-data"

    storage.delete("jobs/abc/clip.mp4")
    assert storage.exists("jobs/abc/clip.mp4") is False

    with pytest.raises(NotFoundError):
        storage.read("jobs/abc/clip.mp4")
    with pytest.raises(NotFoundError):
        storage.delete("jobs/abc/clip.mp4")


def test_path_for_stays_under_root(storage: LocalStorage) -> None:
    path = storage.path_for("renders/out.mp4")
    assert path.is_absolute()
    assert "renders" in path.parts
    assert str(storage.root.resolve()) in str(path)


@pytest.mark.parametrize(
    "bad_name",
    [
        "../evil.mp4",
        "jobs/../../evil.mp4",
        "/etc/passwd",
        "C:/Windows/system.ini",
        "",
        "   ",
    ],
)
def test_unsafe_names_rejected(storage: LocalStorage, bad_name: str) -> None:
    with pytest.raises(StoragePathError):
        storage.save(bad_name, b"data")
    with pytest.raises(StoragePathError):
        storage.read(bad_name)


def test_backslash_traversal_rejected(storage: LocalStorage) -> None:
    with pytest.raises(StoragePathError):
        storage.save("..\\evil.mp4", b"data")


def test_storage_root_cannot_be_empty() -> None:
    with pytest.raises(ValueError):
        LocalStorage("   ")


def test_protocol_usable_with_local_storage(storage: LocalStorage) -> None:
    def store_bytes(provider: StorageProvider, name: str, data: bytes) -> str:
        return provider.save(name, data)

    stored = store_bytes(storage, "protocol/check.bin", b"ok")
    assert storage.read(stored) == b"ok"
