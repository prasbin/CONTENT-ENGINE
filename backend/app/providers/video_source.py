"""YtDlpSourceProvider: validate URL -> download -> verify -> store.

Stage progress mapping (aligned with JobStatus ``downloading``):
10  claimed / starting download
10-70  download percent (raw downloader percent mapped into this window)
70  downloaded and size/extension checks passed
90  media validation passed
100 stored (job completion is persisted by the worker)
"""

from __future__ import annotations

import mimetypes
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from app.core.config import Settings
from app.core.errors import (
    InvalidMediaError,
    InvalidSourceUrlError,
    MediaProbeUnavailableError,
    SourceTooLargeError,
)
from app.providers.base import AcquisitionResult, ProgressCallback
from app.providers.downloader import Downloader
from app.providers.media_probe import MediaProbe
from app.storage.base import StorageProvider

DOWNLOAD_START = 10
DOWNLOAD_END = 70
PROGRESS_DOWNLOADED = 70
PROGRESS_VALIDATED = 90
PROGRESS_STORED = 100

_UUID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")


class YtDlpSourceProvider:
    """Concrete ``VideoSourceProvider`` for Phase 2."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        downloader: Downloader,
        probe: MediaProbe,
        settings: Settings,
    ) -> None:
        self._storage = storage
        self._downloader = downloader
        self._probe = probe
        self._settings = settings

    def acquire(
        self,
        url: str,
        *,
        job_id: str,
        progress: ProgressCallback | None = None,
    ) -> AcquisitionResult:
        self._validate_url(url)
        if not _UUID_PATTERN.match(job_id):
            raise InvalidSourceUrlError("invalid job id for asset path")

        def report(value: int) -> None:
            if progress is not None:
                progress(max(0, min(100, int(value))))

        def map_download(raw_percent: int) -> None:
            span = DOWNLOAD_END - DOWNLOAD_START
            report(DOWNLOAD_START + int(raw_percent * span / 100))

        max_bytes = self._settings.ce_max_source_bytes
        deadline = time.monotonic() + self._settings.ce_download_timeout_seconds
        report(DOWNLOAD_START)

        with tempfile.TemporaryDirectory(prefix="ce-acq-") as tmp:
            dest_dir = Path(tmp)
            download = self._downloader.download(
                url,
                dest_dir,
                max_bytes=max_bytes,
                deadline=deadline,
                progress=map_download,
            )
            report(PROGRESS_DOWNLOADED)

            path = download.path
            size = path.stat().st_size
            if size == 0:
                raise InvalidMediaError("downloaded file is empty")
            if size > max_bytes:
                raise SourceTooLargeError(f"source exceeds the {max_bytes} byte limit")

            ext = path.suffix.lower().lstrip(".")
            if ext not in self._settings.ce_allowed_media_extensions:
                raise InvalidMediaError(f"disallowed media extension '.{ext or 'none'}'")

            duration = download.duration_seconds
            width = height = None
            probed = False
            try:
                info = self._probe.probe(path)
            except MediaProbeUnavailableError:
                if self._settings.ce_require_media_probe:
                    raise
                # probe optional and unavailable: proceed honestly (probed=False)
            else:
                probed = True
                duration = info.duration_seconds if info.duration_seconds is not None else duration
                width = info.width
                height = info.height
            report(PROGRESS_VALIDATED)

            asset_ref = f"sources/{job_id}/source.{ext}"
            stored_ref = self._storage.save_file(asset_ref, path)
            report(PROGRESS_STORED)

        filename = Path(download.filename).name
        filename = "".join(ch for ch in filename if ch.isprintable())[:255] or f"source.{ext}"
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return AcquisitionResult(
            asset_ref=stored_ref,
            source_url=url,
            filename=filename,
            media_type=media_type,
            size_bytes=size,
            duration_seconds=duration,
            width=width,
            height=height,
            probed=probed,
            title=download.title,
            extractor=download.extractor,
        )

    def _validate_url(self, url: str) -> None:
        if not isinstance(url, str) or not url or len(url) > 4096:
            raise InvalidSourceUrlError(
                "source URL must be a non-empty string up to 4096 characters"
            )
        parsed = urlparse(url)
        if parsed.scheme.lower() not in self._settings.ce_allowed_schemes:
            raise InvalidSourceUrlError(
                f"URL scheme '{parsed.scheme or 'none'}' is not allowed "
                f"(allowed: {', '.join(self._settings.ce_allowed_schemes)})"
            )
        if not parsed.hostname:
            raise InvalidSourceUrlError("source URL must include a host")
        if parsed.username is not None or parsed.password is not None:
            raise InvalidSourceUrlError("source URL must not include embedded credentials")


def sanitize_url_for_log(url: str) -> str:
    """Strip query/userinfo/fragment so tokens never reach the logs."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse((parsed.scheme, host, parsed.path, "", "", ""))
