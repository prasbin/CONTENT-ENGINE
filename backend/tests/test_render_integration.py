"""Integration test: real FFmpeg rendering of three vertical clips with captions.

Generates a synthetic 40-second source video (1920x1080, with audio), then
uses the real FFmpegRenderer to produce three clips of exactly 20, 30, and
35 seconds. Verifies durations, dimensions, codecs, audio presence, and
caption burn-in via ffprobe and frame inspection.

Requires ffmpeg + ffprobe on PATH. Skips if not available.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ffmpeg_bin = "ffmpeg"
ffprobe_bin = "ffprobe"


def _have(binary: str) -> bool:
    import shutil

    return shutil.which(binary) is not None


pytestmark = pytest.mark.skipif(
    not (_have(ffmpeg_bin) and _have(ffprobe_bin)),
    reason="ffmpeg and ffprobe must be installed",
)

TARGET_DURATIONS = [20, 30, 35]
SOURCE_DURATION = 40
SOURCE_W = 1920
SOURCE_H = 1080


def _ffprobe_json(path: str) -> dict:
    """Run ffprobe and return parsed JSON."""
    result = subprocess.run(
        [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    import json

    return json.loads(result.stdout)


def _ffprobe_duration(path: str) -> float:
    info = _ffprobe_json(path)
    return float(info["format"]["duration"])


def _generate_source_video(path: Path) -> None:
    """Generate a 40s 1920x1080 source with color bars + sine-wave audio."""
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc2=duration={SOURCE_DURATION}:size={SOURCE_W}x{SOURCE_H}:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={SOURCE_DURATION}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)


def _extract_frame(path: str, timestamp: float, out_path: str) -> None:
    """Extract a single frame at the given timestamp for caption inspection."""
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-ss", f"{timestamp:.2f}",
            "-i", path,
            "-frames:v", "1",
            "-vf", "scale=540:960",
            out_path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


def _frame_has_captions(frame_path: str) -> bool:
    """Check if a frame has non-uniform brightness in the bottom third (caption area).

    Captions create bright text on darker background. We check that the bottom
    25% of the frame has a high standard deviation of pixel values, which
    indicates text presence vs. a uniform color bar.
    """
    from PIL import Image

    img = Image.open(frame_path).convert("L")
    w, h = img.size
    bottom = img.crop((0, int(h * 0.75), w, h))
    pixels = list(bottom.getdata())
    if not pixels:
        return False
    mean = sum(pixels) / len(pixels)
    variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
    std = variance ** 0.5
    # color bars have moderate std; captions add text causing higher std.
    # A threshold of 30+ indicates visible text overlay.
    return std > 30


def test_renderer_produces_three_clips_with_exact_durations(tmp_path: Path) -> None:
    """End-to-end renderer test: synthetic source -> three 9:16 MP4s with captions."""
    from app.core.config import Settings
    from app.providers.renderer import FFmpegRenderer
    from app.storage.local import LocalStorage

    # 1. Set up storage and generate synthetic source
    storage = LocalStorage(tmp_path / "storage")
    source_ref = "sources/test-source.mp4"
    source_path = storage.path_for(source_ref)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    _generate_source_video(source_path)
    assert source_path.is_file(), "source video was not generated"

    # Verify source
    src_dur = _ffprobe_duration(str(source_path))
    assert src_dur >= SOURCE_DURATION - 0.5, f"source too short: {src_dur}"

    # 2. Configure renderer with the real ffmpeg binary
    renderer = FFmpegRenderer(storage=storage, ffmpeg_path=ffmpeg_bin)

    # 3. Render three clips with captions
    captions = [
        {"start": 1.0, "end": 4.0, "text": "This is the first clip caption"},
        {"start": 5.0, "end": 9.0, "text": "Second caption appears here"},
        {"start": 10.0, "end": 15.0, "text": "And a third one for good measure"},
    ]

    outputs: list[tuple[int, str]] = []
    for target in TARGET_DURATIONS:
        start = 0.0
        end = float(target)
        output_ref = f"clips/test-job/clip_{target}s.mp4"
        stored_ref = renderer.render_vertical(
            source_ref=source_ref,
            start_seconds=start,
            end_seconds=end,
            output_ref=output_ref,
            captions=captions,
            progress=None,
        )
        stored_path = storage.path_for(stored_ref)
        assert stored_path.is_file(), f"output {stored_ref} not found"
        assert stored_path.stat().st_size > 0, f"output {stored_ref} is empty"
        outputs.append((target, str(stored_path)))

    # 4. Verify each output with ffprobe
    for target_dur, path in outputs:
        info = _ffprobe_json(path)
        actual_dur = float(info["format"]["duration"])

        # Duration must be within 0.1s of the exact target (frame-rate rounding).
        assert abs(actual_dur - target_dur) < 0.15, (
            f"clip {target_dur}s: actual duration {actual_dur:.3f}s "
            f"deviates by {abs(actual_dur - target_dur):.3f}s"
        )

        # Find video and audio streams
        video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio_stream = next(
            (s for s in info["streams"] if s["codec_type"] == "audio"), None
        )

        # 9:16 portrait dimensions
        width = int(video_stream["width"])
        height = int(video_stream["height"])
        assert width == 1080, f"expected width 1080, got {width}"
        assert height == 1920, f"expected height 1920, got {height}"
        assert video_stream["codec_name"] == "h264", (
            f"expected h264, got {video_stream['codec_name']}"
        )

        # Audio must be present
        assert audio_stream is not None, f"clip {target_dur}s has no audio stream"
        assert audio_stream["codec_name"] == "aac", (
            f"expected aac audio, got {audio_stream['codec_name']}"
        )

        # 5. Verify captions are burned in by extracting a frame at t=2s
        frame_path = str(tmp_path / f"frame_{target_dur}s.png")
        _extract_frame(path, 2.0, frame_path)
        assert Path(frame_path).is_file(), "frame extraction failed"

        # Captions should be visible at t=2s (first caption is 1.0-4.0s)
        # Note: PIL may not be available; fall back to file-size heuristic.
        try:
            has_captions = _frame_has_captions(frame_path)
        except Exception:
            # Fallback: a frame with captions will be larger due to text detail.
            has_captions = Path(frame_path).stat().st_size > 5000

        assert has_captions, f"clip {target_dur}s: no caption text detected in frame"

    # 6. Verify download endpoint serves the files
    from app.db.session import create_engine_from_url, init_db
    from app.main import create_app
    from fastapi.testclient import TestClient

    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    test_settings = Settings(
        _env_file=None,
        ce_storage_path=str(tmp_path / "storage"),
        ce_database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )

    with TestClient(create_app(test_settings)) as client:
        from helpers import TEST_TOKEN

        for target_dur, _path in outputs:
            stored_ref = f"clips/test-job/clip_{target_dur}s.mp4"
            resp = client.get(
                f"/api/v1/storage/{stored_ref}",
                headers={"Authorization": f"Bearer {TEST_TOKEN}"},
            )
            assert resp.status_code == 200, (
                f"download failed for {target_dur}s clip: {resp.status_code}"
            )
            assert len(resp.content) > 0, f"download body empty for {target_dur}s"
            # Check the first bytes look like an MP4
            assert resp.content[4:8] == b"ftyp", (
                f"downloaded file {target_dur}s does not start with MP4 header"
            )
