"""Caption provider: extracts transcript cues for a clip's time range.

Phase 6: produces the caption cues (start/end/text relative to the
source) that the renderer burns in. No AI needed — this is straight
transcript slicing.
"""

from __future__ import annotations

from typing import Any


class TranscriptCaptionProvider:
    """Concrete ``CaptionProvider`` that slices transcript segments."""

    def generate_captions(self, transcript: dict[str, Any]) -> dict[str, Any]:
        segments = transcript.get("segments") or []
        cues = [
            {
                "start": float(seg.get("start", 0)),
                "end": float(seg.get("end", 0)),
                "text": str(seg.get("text", "")).strip(),
            }
            for seg in segments
            if str(seg.get("text", "")).strip()
        ]
        return {"cues": cues}

    def burn_in(self, video_ref: str, captions: dict[str, Any], output_ref: str) -> str:
        """Burning is handled by the FFmpeg renderer (it takes cues directly)."""
        raise NotImplementedError("caption burning is performed by the FFmpeg renderer")

    @staticmethod
    def cues_for_clip(
        transcript: dict[str, Any], clip_start: float, clip_end: float
    ) -> list[dict[str, Any]]:
        """Return only the cues that fall within [clip_start, clip_end]."""
        segments = transcript.get("segments") or []
        cues: list[dict[str, Any]] = []
        for seg in segments:
            s = float(seg.get("start", 0))
            e = float(seg.get("end", s))
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            # Keep cues that overlap the clip window.
            if e < clip_start or s > clip_end:
                continue
            cues.append(
                {
                    "start": max(s, clip_start),
                    "end": min(e, clip_end),
                    "text": text,
                }
            )
        return cues
