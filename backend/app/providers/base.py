"""Provider interfaces for the content pipeline.

Each interface is a structural contract (typing.Protocol) so that real
implementations can be added phase by phase and swapped via dependency
injection without changing callers. No heavyweight AI/media dependencies
are required to use these interfaces.
"""

from __future__ import annotations

from typing import Any, Protocol


class VideoSourceProvider(Protocol):
    """Acquires the source video for a job (Phase 2)."""

    def acquire(self, url: str) -> str:
        """Download/resolve ``url``; returns a local source reference."""
        ...


class TranscriptionProvider(Protocol):
    """Speech-to-text with timestamps (Phase 3)."""

    def transcribe(self, source_ref: str) -> dict[str, Any]:
        """Return ``{"language": ..., "segments": [{"start", "end", "text"}]}``."""
        ...


class ClipDetectionProvider(Protocol):
    """Finds strong short-video moments in a transcript (Phase 4)."""

    def detect_moments(self, transcript: dict[str, Any]) -> list[dict[str, Any]]:
        """Return candidate moments with ``start``, ``end``, ``reason``, ``score``."""
        ...


class Renderer(Protocol):
    """Renders vertical 9:16 shorts from a source video (Phase 5)."""

    def render_vertical(
        self,
        source_ref: str,
        start_seconds: float,
        end_seconds: float,
        output_ref: str,
    ) -> str:
        """Render the segment; returns the output reference."""
        ...


class CaptionProvider(Protocol):
    """Generates and burns in captions (Phase 6)."""

    def generate_captions(self, transcript: dict[str, Any]) -> dict[str, Any]:
        """Return styled, timestamped caption cues."""
        ...

    def burn_in(self, video_ref: str, captions: dict[str, Any], output_ref: str) -> str:
        """Burn captions into the video; returns the output reference."""
        ...


class MetadataProvider(Protocol):
    """Generates title/description/hashtags (Phase 7)."""

    def generate(self, transcript: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
        """Return ``{"title": ..., "description": ..., "hashtags": [...]}``."""
        ...


class Publisher(Protocol):
    """Publishes an approved clip through an official platform API (Phase 8+)."""

    platform: str

    def publish(self, video_ref: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Publish and return the platform result (id/url)."""
        ...
