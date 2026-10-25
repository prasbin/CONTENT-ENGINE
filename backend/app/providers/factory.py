"""Single construction path for providers (used by API app and worker)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.captions import TranscriptCaptionProvider
from app.providers.clip_detection import HeuristicClipDetector
from app.providers.downloader import YtDlpDownloader
from app.providers.media_probe import get_media_probe
from app.providers.renderer import FFmpegRenderer
from app.providers.transcription import FasterWhisperProvider
from app.providers.video_source import YtDlpSourceProvider
from app.services.jobs import JobService
from app.storage.local import LocalStorage


def build_storage(settings: Settings) -> LocalStorage:
    from app.core.paths import project_path

    return LocalStorage(project_path(settings.ce_storage_path))


def build_video_source_provider(
    settings: Settings,
    storage: LocalStorage,
) -> YtDlpSourceProvider:
    return YtDlpSourceProvider(
        storage=storage,
        downloader=YtDlpDownloader(),
        probe=get_media_probe(settings.ce_ffprobe_path),
        settings=settings,
    )


def build_transcriber(settings: Settings, storage: LocalStorage) -> FasterWhisperProvider:
    return FasterWhisperProvider(
        storage=storage,
        model_size=settings.ce_whisper_model,
        device=settings.ce_whisper_device,
        compute_type=settings.ce_whisper_compute_type,
    )


def build_clip_detector() -> HeuristicClipDetector:
    return HeuristicClipDetector()


def build_captioner() -> TranscriptCaptionProvider:
    return TranscriptCaptionProvider()


def build_renderer(settings: Settings, storage: LocalStorage) -> FFmpegRenderer:
    return FFmpegRenderer(storage=storage, ffmpeg_path=settings.ce_ffmpeg_path)


def build_pipeline_worker(
    settings: Settings,
    job_service: JobService,
    storage: LocalStorage,
):
    from app.workers.pipeline import PipelineWorker

    return PipelineWorker(
        job_service=job_service,
        transcriber=build_transcriber(settings, storage),
        clip_detector=build_clip_detector(),
        captioner=build_captioner(),
        renderer=build_renderer(settings, storage),
        settings=settings,
    )
