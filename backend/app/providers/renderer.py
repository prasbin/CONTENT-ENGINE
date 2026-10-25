"""Video rendering + caption burning via FFmpeg (Phase 5–6).

This module talks to the real ``ffmpeg`` binary through subprocess with
list arguments (never a shell). When FFmpeg is not installed it raises
:class:`RendererUnavailable` instead of producing fake output.

Rendering plan for each clip:
- Trim the source to [start, end] with exact duration.
- Scale and crop to 1080x1920 (9:16). For horizontal sources, crop the
  center column; for vertical sources, scale to fit.
- Re-encode H.264 + AAC.
- Burn in caption cues (from the transcript) as styled subtitles.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.core.errors import ContentEngineError
from app.providers.base import ProgressCallback
from app.storage.base import StorageProvider

logger = logging.getLogger("content_engine.providers.renderer")

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
RENDER_TIMEOUT_SECONDS = 1800


class RendererUnavailable(ContentEngineError):
    code = "renderer_unavailable"
    status_code = 501


class RenderError(ContentEngineError):
    code = "render_failed"
    status_code = 502


class FFmpegRenderer:
    """Concrete ``Renderer`` backed by the FFmpeg binary."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        self._storage = storage
        self._ffmpeg_path = ffmpeg_path

    def _check_binary(self) -> None:
        if shutil.which(self._ffmpeg_path) is None and not Path(self._ffmpeg_path).is_file():
            raise RendererUnavailable(
                f"ffmpeg executable not found: '{self._ffmpeg_path}' "
                "(install FFmpeg to enable rendering)"
            )

    def render_vertical(
        self,
        source_ref: str,
        start_seconds: float,
        end_seconds: float,
        output_ref: str,
        *,
        captions: list[dict[str, Any]] | None = None,
        progress: ProgressCallback | None = None,
    ) -> str:
        self._check_binary()
        source_path = self._storage.path_for(source_ref)
        if not Path(source_path).is_file():
            raise RenderError(f"source asset '{source_ref}' not found in storage")

        duration = max(0.1, end_seconds - start_seconds)
        if progress:
            progress(10)

        with tempfile.TemporaryDirectory(prefix="ce-render-") as tmp:
            tmp_dir = Path(tmp)
            output_path = tmp_dir / "clip.mp4"
            ass_path = tmp_dir / "captions.ass" if captions else None
            if captions and ass_path:
                ass_path.write_text(_build_ass(captions, start_seconds), encoding="utf-8")

            command = _build_render_command(
                ffmpeg=self._ffmpeg_path,
                source=str(source_path),
                start=start_seconds,
                duration=duration,
                output=str(output_path),
                ass_path=str(ass_path) if ass_path else None,
            )
            if progress:
                progress(30)

            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=RENDER_TIMEOUT_SECONDS,
                    shell=False,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RenderError("render timed out") from exc
            except OSError as exc:
                raise RendererUnavailable(f"could not execute ffmpeg: {exc}") from exc

            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()[:500]
                raise RenderError(f"ffmpeg failed: {detail or 'unknown error'}")
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise RenderError("ffmpeg produced no output file")
            if progress:
                progress(90)

            stored = self._storage.save_file(output_ref, output_path)
            if progress:
                progress(100)
            return stored


def _build_render_command(
    *,
    ffmpeg: str,
    source: str,
    start: float,
    duration: float,
    output: str,
    ass_path: str | None,
) -> list[str]:
    """Build the FFmpeg argument list for vertical 9:16 + captions."""
    cmd: list[str] = [
        ffmpeg,
        "-y",
        "-ss", f"{start:.3f}",
        "-i", source,
        "-t", f"{duration:.3f}",
    ]
    vf = f"crop=ih*9/16:ih,scale={TARGET_WIDTH}:{TARGET_HEIGHT}:flags=lanczos"
    if ass_path:
        vf = f"{vf},ass={ass_path}"
    cmd += ["-vf", vf]
    cmd += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
        "-movflags", "+faststart",
        output,
    ]
    return cmd


def _build_ass(captions: list[dict[str, Any]], clip_start: float) -> str:
    """Build an ASS subtitle file with timestamps relative to clip start."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, "
        "Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
        "Style: Default, Arial, 72, &H00FFFFFF, &H80000000, 1, 0, 1, 4, 1, 2, 60, 60, 200\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for cap in captions:
        rel_start = max(0.0, float(cap["start"]) - clip_start)
        rel_end = max(rel_start + 0.3, float(cap["end"]) - clip_start)
        text = str(cap.get("text", "")).replace("\n", " ").replace("\r", " ")
        lines.append(
            f"Dialogue: 0,{_ass_time(rel_start)},{_ass_time(rel_end)},"
            f"Default,,0,0,0,,{text}\n"
        )
    return "".join(lines)


def _ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp H:MM:SS.cc."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"
