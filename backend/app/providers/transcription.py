"""Transcription provider: faster-whisper (CPU, genuinely free).

Uses faster-whisper with PyAV for audio decoding, so no FFmpeg *binary*
is required for transcription itself. The ``tiny`` model downloads from
the HuggingFace Hub on first use (cached under ~/.cache) — no API key,
no paid inference.

The provider implements :class:`app.providers.base.TranscriptionProvider`
and returns ``{"language": ..., "segments": [{"start","end","text"}]}``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.errors import ContentEngineError
from app.providers.base import ProgressCallback
from app.storage.base import StorageProvider

logger = logging.getLogger("content_engine.providers.transcription")


class TranscriptionError(ContentEngineError):
    code = "transcription_failed"
    status_code = 502


class FasterWhisperProvider:
    """Concrete ``TranscriptionProvider`` backed by faster-whisper."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        model_size: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
    ) -> None:
        self._storage = storage
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._model = None  # lazily loaded so import-time stays cheap

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info("loading whisper model '%s' on %s", self._model_size, self._device)
            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
        return self._model

    def transcribe(
        self,
        source_ref: str,
        *,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Transcribe the stored source video; returns timestamped segments."""
        path = self._storage.path_for(source_ref)
        if not Path(path).is_file():
            raise TranscriptionError(f"source asset '{source_ref}' not found in storage")

        model = self._get_model()
        try:
            if progress:
                progress(10)
            segments_iter, info = model.transcribe(
                str(path),
                language=self._language,
                vad_filter=True,
                beam_size=5,
            )
            if progress:
                progress(50)

            segments: list[dict[str, Any]] = []
            for seg in segments_iter:
                text = (seg.text or "").strip()
                if not text:
                    continue
                segments.append(
                    {"start": round(seg.start, 3), "end": round(seg.end, 3), "text": text}
                )
            if progress:
                progress(100)
        except Exception as exc:
            raise TranscriptionError(f"transcription failed: {exc}") from exc

        if not segments:
            raise TranscriptionError("transcription produced no speech segments")

        return {
            "language": info.language if info and info.language else (self._language or "unknown"),
            "language_probability": (
                float(info.language_probability) if info and info.language_probability else None
            ),
            "segments": segments,
            "duration_seconds": (
                float(info.duration) if info and info.duration else segments[-1]["end"]
            ),
        }
