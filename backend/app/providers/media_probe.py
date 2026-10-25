"""Media probing abstraction.

FFmpeg is NOT installed in the current development environment. This
module therefore has two honest behaviors:

- ``FfprobeMediaProbe`` - real probing via the ffprobe binary (used when
  FFmpeg is installed; subprocess with list arguments, never a shell).
- ``UnavailableMediaProbe`` - raises :class:`MediaProbeUnavailableError`
  instead of pretending a probe succeeded.

There is no fake probe implementation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.errors import InvalidMediaError, MediaProbeUnavailableError

PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class MediaInfo:
    """Result of a successful media probe."""

    duration_seconds: float | None
    width: int | None
    height: int | None
    codec: str | None
    format_name: str | None


class MediaProbe(Protocol):
    """Validates that a file really is decodable media."""

    def probe(self, path: Path) -> MediaInfo: ...


class UnavailableMediaProbe:
    """Probe backend placeholder used when ffprobe cannot be found."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def probe(self, path: Path) -> MediaInfo:
        raise MediaProbeUnavailableError(f"media probe unavailable: {self.reason}")


class FfprobeMediaProbe:
    """Real probe via ffprobe (requires FFmpeg installed on the host)."""

    def __init__(self, executable: str = "ffprobe") -> None:
        self._executable = executable

    def probe(self, path: Path) -> MediaInfo:
        if shutil.which(self._executable) is None and not Path(self._executable).is_file():
            raise MediaProbeUnavailableError(
                f"ffprobe executable not found: '{self._executable}' (install FFmpeg)"
            )
        command = [
            self._executable,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                shell=False,  # list args: no shell injection surface
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise InvalidMediaError("media probe timed out") from exc
        except OSError as exc:
            raise MediaProbeUnavailableError(
                f"could not execute ffprobe: {exc}"
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:300]
            raise InvalidMediaError(f"ffprobe rejected the media: {detail or 'unknown error'}")

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise InvalidMediaError("ffprobe returned unparseable output") from exc
        return _parse_ffprobe(data)


def _parse_ffprobe(data: dict) -> MediaInfo:
    fmt = data.get("format") or {}
    duration = _as_float(fmt.get("duration"))
    format_name = fmt.get("format_name")

    width = height = None
    codec = None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video":
            width = _as_int(stream.get("width"))
            height = _as_int(stream.get("height"))
            codec = stream.get("codec_name")
            break
    if codec is None and data.get("streams"):
        codec = data["streams"][0].get("codec_name")
    return MediaInfo(
        duration_seconds=duration,
        width=width,
        height=height,
        codec=codec,
        format_name=format_name,
    )


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def get_media_probe(executable: str) -> MediaProbe:
    """Return a real ffprobe backend when available, else an honest failure backend."""
    if shutil.which(executable) is not None or Path(executable).is_file():
        return FfprobeMediaProbe(executable)
    return UnavailableMediaProbe(
        f"'{executable}' not found on PATH (install FFmpeg to enable media validation)"
    )
