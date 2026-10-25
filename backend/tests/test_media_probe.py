"""Tests for media probe abstractions."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.errors import MediaProbeUnavailableError
from app.providers.media_probe import (
    FfprobeMediaProbe,
    UnavailableMediaProbe,
    _parse_ffprobe,
    get_media_probe,
)


def test_unavailable_media_probe_raises() -> None:
    probe = UnavailableMediaProbe("ffprobe not installed")
    with pytest.raises(MediaProbeUnavailableError) as exc:
        probe.probe(Path("dummy.mp4"))
    assert "ffprobe not installed" in str(exc.value)


def test_parse_ffprobe_valid() -> None:
    data = {
        "format": {"duration": "12.34", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        "streams": [
            {"codec_type": "video", "width": 1080, "height": 1920, "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    info = _parse_ffprobe(data)
    assert info.duration_seconds == 12.34
    assert info.width == 1080
    assert info.height == 1920
    assert info.codec == "h264"
    assert info.format_name == "mov,mp4,m4a,3gp,3g2,mj2"


def test_ffprobe_missing_binary(tmp_path: Path) -> None:
    dummy_file = tmp_path / "video.mp4"
    dummy_file.write_bytes(b"data")
    probe = FfprobeMediaProbe(executable="nonexistent-ffprobe-binary-xyz")
    with pytest.raises(MediaProbeUnavailableError):
        probe.probe(dummy_file)


def test_get_media_probe_factory(tmp_path: Path) -> None:
    probe = get_media_probe("nonexistent-binary-12345")
    assert isinstance(probe, UnavailableMediaProbe)
