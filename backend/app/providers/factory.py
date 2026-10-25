"""Single construction path for providers (used by API app and worker)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.downloader import YtDlpDownloader
from app.providers.media_probe import get_media_probe
from app.providers.video_source import YtDlpSourceProvider
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
