"""Tests for YtDlpSourceProvider, URL validation, and downloader fakes."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.errors import (
    InvalidMediaError,
    InvalidSourceUrlError,
    SourceTooLargeError,
)
from app.providers.downloader import DownloadResult
from app.providers.media_probe import MediaInfo
from app.providers.video_source import YtDlpSourceProvider, sanitize_url_for_log
from app.storage.local import LocalStorage


class FakeDownloader:
    def __init__(self, result: DownloadResult | Exception) -> None:
        self._result = result
        self.called_url: str | None = None

    def download(
        self,
        url: str,
        dest_dir: Path,
        *,
        max_bytes: int,
        deadline: float,
        progress=None,
    ) -> DownloadResult:
        self.called_url = url
        if progress:
            progress(50)
            progress(100)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class FakeProbe:
    def __init__(self, info: MediaInfo | Exception) -> None:
        self._info = info

    def probe(self, path: Path) -> MediaInfo:
        if isinstance(self._info, Exception):
            raise self._info
        return self._info


def test_sanitize_url_for_log() -> None:
    raw = "https://user:secret@youtube.com/watch?v=123#fragment"
    assert sanitize_url_for_log(raw) == "https://youtube.com/watch"


def test_url_validation_rejections(tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    storage = LocalStorage(tmp_path)
    provider = YtDlpSourceProvider(
        storage=storage,
        downloader=FakeDownloader(DownloadResult(tmp_path, "f.mp4", "t", "e", 10.0)),
        probe=FakeProbe(MediaInfo(10.0, 1080, 1920, "h264", "mp4")),
        settings=settings,
    )

    with pytest.raises(InvalidSourceUrlError):
        provider.acquire(
            "ftp://example.com/video.mp4",
            job_id="00000000-0000-0000-0000-000000000001",
        )

    with pytest.raises(InvalidSourceUrlError):
        provider.acquire(
            "https://user:pass@example.com/video.mp4",
            job_id="00000000-0000-0000-0000-000000000001",
        )

    with pytest.raises(InvalidSourceUrlError):
        provider.acquire(
            "not-a-url",
            job_id="00000000-0000-0000-0000-000000000001",
        )


def test_acquisition_success_flow(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, ce_require_media_probe=True)
    storage_root = tmp_path / "store"
    storage_root.mkdir()
    storage = LocalStorage(storage_root)

    media_file = tmp_path / "source.mp4"
    media_file.write_bytes(b"VALID-MP4-BYTES")

    download_res = DownloadResult(
        path=media_file,
        filename="source.mp4",
        title="Test Video",
        extractor="youtube",
        duration_seconds=15.0,
    )
    probe_info = MediaInfo(15.0, 1080, 1920, "h264", "mp4")

    provider = YtDlpSourceProvider(
        storage=storage,
        downloader=FakeDownloader(download_res),
        probe=FakeProbe(probe_info),
        settings=settings,
    )

    progress_calls = []
    job_uuid = "12345678-1234-1234-1234-123456789012"
    result = provider.acquire(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        job_id=job_uuid,
        progress=lambda p: progress_calls.append(p),
    )

    assert result.asset_ref == f"sources/{job_uuid}/source.mp4"
    assert result.filename == "source.mp4"
    assert result.probed is True
    assert result.duration_seconds == 15.0
    assert storage.read(result.asset_ref) == b"VALID-MP4-BYTES"
    assert len(progress_calls) > 0


def test_acquisition_too_large(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, ce_max_source_bytes=1024)
    storage = LocalStorage(tmp_path / "store")

    media_file = tmp_path / "big.mp4"
    media_file.write_bytes(b"X" * 2000)  # 2000 bytes > 1024

    provider = YtDlpSourceProvider(
        storage=storage,
        downloader=FakeDownloader(DownloadResult(media_file, "big.mp4", "t", "e", 10.0)),
        probe=FakeProbe(MediaInfo(10.0, 1080, 1920, "h264", "mp4")),
        settings=settings,
    )

    with pytest.raises(SourceTooLargeError):
        provider.acquire(
            "https://youtube.com/watch?v=abc",
            job_id="12345678-1234-1234-1234-123456789012",
        )


def test_acquisition_invalid_extension(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, ce_allowed_media_extensions=["mp4"])
    storage = LocalStorage(tmp_path / "store")

    media_file = tmp_path / "source.txt"
    media_file.write_bytes(b"not a video")

    provider = YtDlpSourceProvider(
        storage=storage,
        downloader=FakeDownloader(DownloadResult(media_file, "source.txt", "t", "e", 10.0)),
        probe=FakeProbe(MediaInfo(10.0, 1080, 1920, "h264", "txt")),
        settings=settings,
    )

    with pytest.raises(InvalidMediaError):
        provider.acquire(
            "https://youtube.com/watch?v=abc",
            job_id="12345678-1234-1234-1234-123456789012",
        )
