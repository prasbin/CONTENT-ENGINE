"""Downloader abstraction: yt-dlp behind a small injectable protocol.

yt-dlp is used through its Python API only - never through a shell.
The protocol exists so tests can inject fakes without touching the
network.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yt_dlp

from app.core.errors import (
    DownloadFailedError,
    DownloadTimeoutError,
    SourceTooLargeError,
)
from app.providers.base import ProgressCallback


@dataclass(frozen=True)
class DownloadResult:
    """A completed download in a caller-owned temporary directory."""

    path: Path
    filename: str
    title: str | None
    extractor: str | None
    duration_seconds: float | None


class Downloader(Protocol):
    def download(
        self,
        url: str,
        dest_dir: Path,
        *,
        max_bytes: int,
        deadline: float,
        progress: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download ``url`` into ``dest_dir``.

        ``deadline`` is an absolute ``time.monotonic()`` value; ``progress``
        receives raw 0-100 values for the download step only (the caller
        maps them into its own stage range). Raises
        :class:`DownloadTimeoutError` / :class:`DownloadFailedError` /
        :class:`SourceTooLargeError`.
        """
        ...


class YtDlpDownloader:
    """Real downloader backed by yt-dlp (Python API, no shell)."""

    def download(
        self,
        url: str,
        dest_dir: Path,
        *,
        max_bytes: int,
        deadline: float,
        progress: ProgressCallback | None = None,
    ) -> DownloadResult:
        state = {"timed_out": False, "last_percent": None, "too_large": False}

        def _hook(dict_info: dict) -> None:
            if time.monotonic() > deadline:
                state["timed_out"] = True
                raise DownloadTimeoutError("download exceeded the configured time budget")
            if dict_info.get("status") != "downloading":
                return
            total = dict_info.get("total_bytes") or dict_info.get("total_bytes_estimate")
            downloaded = dict_info.get("downloaded_bytes")
            if not total or downloaded is None or not progress:
                return
            percent = int(downloaded / total * 100)
            percent = max(0, min(100, percent))
            if percent != state["last_percent"]:
                state["last_percent"] = percent
                progress(percent)

        options: dict = {
            "outtmpl": str(dest_dir / "source.%(ext)s"),
            "format": "best[ext=mp4]/best",
            "max_filesize": int(max_bytes),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "socket_timeout": 15,
            "retries": 2,
            "continuedl": False,
            "progress_hooks": [_hook],
        }

        info: dict = {}
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                extracted = ydl.extract_info(url, download=True)
                if isinstance(extracted, dict):
                    info = extracted
        except (DownloadTimeoutError, DownloadFailedError, SourceTooLargeError):
            raise
        except Exception as exc:  # yt-dlp raises many types; classify honestly
            if state["timed_out"]:
                raise DownloadTimeoutError("download exceeded the configured time budget") from exc
            message = str(exc)
            lowered = message.lower()
            if "timed out" in lowered or "timeout" in lowered:
                raise DownloadTimeoutError(f"download timed out: {message[:200]}") from exc
            if "filesize" in lowered or "max-filesize" in lowered:
                raise SourceTooLargeError(
                    f"source exceeds the {max_bytes} byte limit"
                ) from exc
            raise DownloadFailedError(f"download failed: {message[:300]}") from exc

        path = _locate_output(info, dest_dir)
        size = path.stat().st_size
        if size == 0:
            raise DownloadFailedError("downloader produced an empty file")
        if size > max_bytes:
            raise SourceTooLargeError(f"source exceeds the {max_bytes} byte limit")

        duration = info.get("duration")
        try:
            duration = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration = None
        return DownloadResult(
            path=path,
            filename=path.name,
            title=info.get("title") or None,
            extractor=info.get("extractor_key") or info.get("extractor") or None,
            duration_seconds=duration,
        )


def _locate_output(info: dict, dest_dir: Path) -> Path:
    candidates: list[Path] = []
    for key in ("filepath", "_filename"):
        value = info.get(key)
        if isinstance(value, str) and value:
            candidate = Path(value)
            if candidate.is_file():
                return candidate
    for entry in dest_dir.iterdir():
        if entry.is_file() and not entry.name.endswith(".part"):
            candidates.append(entry)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise DownloadFailedError("downloader produced no output file")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]
