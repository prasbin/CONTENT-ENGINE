"""REAL-MEDIA verification: real speech -> real whisper -> real clip detection.

Generates genuine spoken audio with the Windows SAPI speech synthesizer
(free, offline, built into Windows), transcribes it with the actual
``FasterWhisperProvider`` (tiny/int8/CPU, the production default), and
runs the actual ``HeuristicClipDetector`` on the real transcript.
Skipped - never faked - when the environment cannot support it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="speech fixture uses Windows SAPI"
)

#: ~250 words of varied spoken content -> roughly 100-120s of audio,
#: enough for three non-overlapping clips (20+30+35 = 85s required).
SPOKEN_TEXT = (
    "Welcome back to the channel. Today we are going to talk about building "
    "artificial intelligence systems that actually work in the real world. "
    "Imagine never having to edit videos by hand again. "
    "The best way to learn machine learning is by building real projects. "
    "Why do most people fail at their New Year goals? "
    "Here is the truth about consistency that nobody tells you. "
    "I always start my day with a thirty minute workout. "
    "This mistake cost me three months of progress, so listen carefully. "
    "How can you build an audience without posting every single day? "
    "The secret to deep work is removing every possible distraction. "
    "Nobody becomes excellent overnight, everyone compounds small wins. "
    "Stop waiting for motivation and start building systems instead. "
    "The first principle is simple: never fake your results. "
    "Always measure what you ship, because honest metrics build trust. "
    "What is the worst advice you have ever heard about startups? "
    "The last thing you need is another tool that does not solve a problem. "
    "First, understand the customer. Second, build the smallest useful thing. "
    "Real growth comes from listening, learning, and improving every week. "
    "Most creators underestimate the power of a strong opening sentence. "
    "Your hook has to earn the next three seconds, nothing more. "
    "Context keeps people watching; curiosity keeps them to the end. "
    "Dead air is the silent killer of retention on short video. "
    "Practice editing until your cuts feel invisible to the viewer. "
    "Every great channel started with exactly zero subscribers. "
    "Focus on one niche, one format, and one promise to your audience. "
    "Measure retention at thirty seconds; that single number teaches you everything."
)


def _has_faster_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


requires_whisper = pytest.mark.skipif(
    not _has_faster_whisper(), reason="faster-whisper not installed"
)


def _generate_speech_wav(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    ps_script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.SetOutputToWaveFile('{target.as_posix()}');"
        f"$s.Speak('{SPOKEN_TEXT}');"
        "$s.Dispose();"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0 or not target.is_file():
        raise RuntimeError(f"SAPI speech generation failed: {completed.stderr[:300]}")


@pytest.fixture(scope="module")
def real_transcript(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Real audio through the real provider; returns the real transcript."""
    if not _has_faster_whisper():
        pytest.skip("faster-whisper not installed")

    from app.providers.transcription import FasterWhisperProvider
    from app.storage.local import LocalStorage

    root = tmp_path_factory.mktemp("real-pipeline")
    wav = root / "speech.wav"
    try:
        _generate_speech_wav(wav)
    except Exception as exc:
        pytest.skip(f"Windows speech synthesis unavailable: {exc}")

    storage = LocalStorage(root / "store")
    ref = storage.save("sources/real/source.wav", wav.read_bytes())
    provider = FasterWhisperProvider(storage=storage, model_size="tiny")
    try:
        return provider.transcribe(ref)
    except Exception as exc:  # model download failed (offline first run)
        pytest.skip(f"whisper model unavailable (offline?): {exc}")


def test_real_transcript_has_expected_content(real_transcript: dict) -> None:
    assert real_transcript["language"] == "en"
    joined = " ".join(s["text"] for s in real_transcript["segments"]).lower()
    assert "artificial intelligence" in joined, joined[:300]
    assert real_transcript["duration_seconds"] >= 60.0


def test_real_transcript_yields_three_exact_clips(real_transcript: dict) -> None:
    from app.providers.clip_detection import HeuristicClipDetector

    detector = HeuristicClipDetector()
    clips = detector.detect_moments(real_transcript)

    assert len(clips) == 3
    assert sorted(c["target_duration"] for c in clips) == [20, 30, 35]
    for clip in clips:
        assert clip["end"] - clip["start"] == pytest.approx(
            clip["target_duration"], abs=1e-6
        )
    ordered = sorted(clips, key=lambda c: c["start"])
    for first, second in zip(ordered, ordered[1:], strict=False):
        assert first["end"] <= second["start"] + 1e-6
