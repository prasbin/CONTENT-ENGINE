"""Provider interfaces and registry."""

from app.providers.base import (
    AcquisitionResult,
    CaptionProvider,
    ClipDetectionProvider,
    MetadataProvider,
    ProgressCallback,
    Publisher,
    Renderer,
    TranscriptionProvider,
    VideoSourceProvider,
)
from app.providers.media_probe import MediaInfo, MediaProbe, get_media_probe
from app.providers.registry import PHASE_HINTS, ProviderRegistry, build_default_registry
from app.providers.video_source import YtDlpSourceProvider

__all__ = [
    "PHASE_HINTS",
    "AcquisitionResult",
    "CaptionProvider",
    "ClipDetectionProvider",
    "MediaInfo",
    "MediaProbe",
    "MetadataProvider",
    "ProgressCallback",
    "ProviderRegistry",
    "Publisher",
    "Renderer",
    "TranscriptionProvider",
    "VideoSourceProvider",
    "YtDlpSourceProvider",
    "build_default_registry",
    "get_media_probe",
]
