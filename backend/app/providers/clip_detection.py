"""Clip detection: selects three distinct, meaningful clip intervals.

This is a genuine heuristic algorithm (no paid AI): it scores transcript
segments by word density, sentence-completeness, and hook strength
(opening words, questions, strong verbs), then greedily picks three
non-overlapping intervals of exactly 20, 30, and 35 seconds that cover
the highest-scoring speech. It refuses to return clips when the source
is too short or lacks enough usable speech.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from itertools import permutations
from typing import Any

from app.core.errors import ContentEngineError

logger = logging.getLogger("content_engine.providers.clip_detection")

TARGET_DURATIONS: tuple[int, ...] = (20, 30, 35)

_HOOK_WORDS = {
    "imagine", "never", "always", "secret", "truth", "mistake", "everyone",
    "nobody", "stop", "wait", "listen", "here", "today", "why", "how",
    "what", "best", "worst", "first", "last", "real", "fake",
}
_STRONG_VERBS = {
    "build", "create", "destroy", "change", "learn", "fail", "win", "lose",
    "start", "quit", "grow", "break", "fix", "fight", "push", "rise",
}
_QUESTION_RE = re.compile(r"\?\s*$")


class ClipDetectionFailed(ContentEngineError):
    code = "clip_detection_failed"
    status_code = 422


@dataclass(frozen=True)
class _ScoredWindow:
    start: float
    end: float
    score: float
    reason: str
    text_preview: str


class HeuristicClipDetector:
    """Concrete ``ClipDetectionProvider`` using transcript heuristics."""

    def __init__(self, *, target_durations: tuple[int, ...] = TARGET_DURATIONS) -> None:
        if len(target_durations) != 3:
            raise ValueError("exactly three target durations are required")
        self._targets = tuple(sorted(target_durations))

    def detect_moments(self, transcript: dict[str, Any]) -> list[dict[str, Any]]:
        segments = transcript.get("segments") or []
        duration = float(transcript.get("duration_seconds") or 0.0)
        if not segments or duration <= 0:
            raise ClipDetectionFailed("transcript has no segments or duration")

        # Need enough source for the longest clip plus a little headroom.
        longest = self._targets[-1]
        if duration < longest + 5:
            raise ClipDetectionFailed(
                f"source is only {duration:.1f}s; need at least {longest + 5}s "
                f"to extract three distinct clips"
            )

        # Build a dense speech timeline (words per second buckets).
        bucket = self._word_buckets(segments, duration)
        if not any(bucket):
            raise ClipDetectionFailed("transcript contains no scored speech")

        chosen = self._select_windows(bucket, duration)
        if chosen is None:
            raise ClipDetectionFailed(
                "could not find three distinct non-overlapping clips of "
                f"{self._targets}; source may be too short or too repetitive"
            )
        labels = ["Hook", "Story", "Payoff"]

        result: list[dict[str, Any]] = []
        # Pair each chosen window with the target duration it was actually
        # selected for BEFORE ordering; pairing after chronological sort
        # would mislabel spans (e.g. a 30s window reported as the 20s clip).
        ordered = sorted(zip(self._targets, chosen, strict=True), key=lambda p: p[1].start)
        for idx, (target, clip) in enumerate(ordered):
            result.append(
                {
                    "index": idx,
                    "label": labels[idx] if idx < len(labels) else f"Clip {idx + 1}",
                    "target_duration": target,
                    "start": round(clip.start, 3),
                    "end": round(clip.end, 3),
                    "reason": clip.reason,
                    "score": round(clip.score, 4),
                    "text_preview": clip.text_preview[:200],
                }
            )
        # Re-index by target duration order (20s, 30s, 35s) for stable UI.
        result.sort(key=lambda c: c["target_duration"])
        for i, clip in enumerate(result):
            clip["index"] = i
        return result

    def _select_windows(self, buckets: list[float], duration: float) -> list[_ScoredWindow] | None:
        """Pick three non-overlapping windows, one per target duration.

        Tries the largest target first (hardest fit), then every other
        ordering, because a purely greedy smallest-first pass can strand
        leftover gaps too small for a later, larger clip. Returns the
        first complete fit, or None when no ordering fits.
        """
        largest_first: tuple[int, ...] = tuple(sorted(self._targets, reverse=True))
        orders = [largest_first] + [o for o in permutations(self._targets) if o != largest_first]
        for order in orders:
            chosen: list[_ScoredWindow] = []
            used: list[tuple[float, float]] = []
            for target in order:
                window = self._best_window(buckets, target, duration, used)
                if window is None:
                    break
                chosen.append(window)
                used.append((window.start, window.end))
            else:
                # Return windows in ascending-target order so callers can
                # pair them positionally with (sorted) target durations.
                by_target = dict(zip(order, chosen, strict=True))
                return [by_target[t] for t in self._targets]
        return None

    @staticmethod
    def _word_buckets(segments: list[dict], duration: float) -> list[float]:
        """Score each 1-second bucket by word density + hook/verb bonuses."""
        buckets = [0.0] * (int(duration) + 1)
        for seg in segments:
            start = float(seg.get("start", 0))
            end = float(seg.get("end", start))
            text = str(seg.get("text", ""))
            words = text.split()
            if not words or end <= start:
                continue
            density = len(words) / max(0.1, end - start)
            bonus = 0.0
            lower = text.lower()
            if any(w in lower for w in _HOOK_WORDS):
                bonus += 1.5
            if any(w in lower for w in _STRONG_VERBS):
                bonus += 1.0
            if _QUESTION_RE.search(text):
                bonus += 0.8
            # Capitalized start = complete sentence (rough proxy).
            if text and text[0].isupper():
                bonus += 0.4
            score = density + bonus
            for sec in range(int(start), min(int(end) + 1, len(buckets))):
                buckets[sec] += score
        return buckets

    @staticmethod
    def _best_window(
        buckets: list[float],
        target: int,
        duration: float,
        used: list[tuple[float, float]],
    ) -> _ScoredWindow | None:
        """Slide a ``target``-second window; pick the highest non-overlapping score."""
        best: _ScoredWindow | None = None
        last_start = max(0.0, duration - target)
        # Step in 0.5s for finer granularity without too much cost.
        step = 0.5
        start = 0.0
        while start <= last_start:
            end = start + target
            if not HeuristicClipDetector._overlaps(start, end, used):
                score = sum(buckets[int(start): int(end)])
                if best is None or score > best.score:
                    text_preview = HeuristicClipDetector._preview(
                        buckets, start, end
                    )
                    reason = HeuristicClipDetector._reason(score, target)
                    best = _ScoredWindow(start, end, score, reason, text_preview)
            start += step
        return best

    @staticmethod
    def _overlaps(s: float, e: float, used: list[tuple[float, float]]) -> bool:
        for us, ue in used:
            if s < ue and e > us:
                return True
        return False

    @staticmethod
    def _preview(buckets: list[float], start: float, end: float) -> str:
        # We don't keep the raw text here; the caller has the transcript.
        # Return a short marker so the worker can fill in the real preview.
        return f"window {start:.1f}-{end:.1f}s"

    @staticmethod
    def _reason(score: float, target: int) -> str:
        if score > target * 8:
            return "High speech density with strong hook language."
        if score > target * 4:
            return "Good sentence completeness and content density."
        return "Steady informative segment."
