"""Regression tests for clip detection on full-length transcripts.

The bucket-scoring code path is only reachable with sources long enough
for three clips (>= 85s of usable speech). These tests exercise it with
full-length synthetic transcripts - previously a TypeError
(``[0.0] * int(duration) + 1``) crashed every real run while unit tests
with short transcripts passed, because the short-source guard fired first.
"""

from __future__ import annotations

import pytest
from app.providers.clip_detection import ClipDetectionFailed, HeuristicClipDetector


def _long_transcript(total_seconds: float = 120.0) -> dict:
    """A synthetic but realistic transcript covering ``total_seconds``."""
    sentences = [
        "Imagine never having to edit videos again.",
        "The best way to learn machine learning is by building real projects.",
        "Why do most people fail at their New Year goals?",
        "Here is the truth about consistency that nobody tells you.",
        "I always start my day with a thirty minute workout.",
        "This mistake cost me three months of progress, so listen carefully.",
        "How can you build an audience without posting every single day?",
        "The secret to deep work is removing every possible distraction.",
        "Nobody becomes excellent overnight; everyone compounds small wins.",
        "Stop waiting for motivation and start building systems instead.",
    ]
    segments = []
    t = 0.0
    index = 0
    while t < total_seconds:
        text = sentences[index % len(sentences)]
        duration = 2.5 + (index % 4) * 0.5
        end = min(t + duration, total_seconds)
        segments.append({"start": round(t, 3), "end": round(end, 3), "text": text})
        t = end
        index += 1
    return {"language": "en", "duration_seconds": total_seconds, "segments": segments}


def test_detects_three_exact_non_overlapping_clips() -> None:
    detector = HeuristicClipDetector()
    clips = detector.detect_moments(_long_transcript(120.0))

    assert len(clips) == 3
    assert sorted(c["target_duration"] for c in clips) == [20, 30, 35]
    for clip in clips:
        span = clip["end"] - clip["start"]
        assert span == pytest.approx(clip["target_duration"], abs=1e-6), clip
        assert 0 <= clip["start"] < clip["end"] <= 120.0

    # non-overlapping
    ordered = sorted(clips, key=lambda c: c["start"])
    for first, second in zip(ordered, ordered[1:], strict=False):
        assert first["end"] <= second["start"] + 1e-6


def test_detect_refuses_source_too_short_for_three_clips() -> None:
    detector = HeuristicClipDetector()
    # 50s: passes the 40s headroom guard but cannot fit 20+30+35=85s of
    # non-overlapping clips - must fail honestly, not return garbage.
    with pytest.raises(ClipDetectionFailed):
        detector.detect_moments(_long_transcript(50.0))


def test_detect_refuses_empty_transcript() -> None:
    detector = HeuristicClipDetector()
    with pytest.raises(ClipDetectionFailed):
        detector.detect_moments({"segments": [], "duration_seconds": 0})
