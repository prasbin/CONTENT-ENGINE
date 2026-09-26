"""Simple provider registry used for dependency injection."""

from __future__ import annotations

from app.core.errors import ProviderNotConfiguredError
from app.storage.base import StorageProvider

#: Which development phase will provide each missing provider.
PHASE_HINTS: dict[str, str] = {
    "video_source": "planned for Phase 2",
    "transcription": "planned for Phase 3",
    "clip_detection": "planned for Phase 4",
    "renderer": "planned for Phase 5",
    "captions": "planned for Phase 6",
    "metadata": "planned for Phase 7",
    "publishers": "planned for Phase 8-10",
}


class ProviderRegistry:
    """Name -> provider lookup. Missing providers fail loudly, not silently."""

    def __init__(self) -> None:
        self._providers: dict[str, object] = {}

    def register(self, name: str, provider: object) -> None:
        if not name or not name.strip():
            raise ValueError("provider name must not be empty")
        self._providers[name.strip()] = provider

    def get(self, name: str) -> object:
        try:
            return self._providers[name]
        except KeyError:
            hint = PHASE_HINTS.get(name, "not scheduled yet")
            raise ProviderNotConfiguredError(
                f"provider '{name}' is not configured ({hint})"
            ) from None

    def names(self) -> list[str]:
        return sorted(self._providers)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._providers


def build_default_registry(*, storage: StorageProvider) -> ProviderRegistry:
    """Build the Phase 1 registry (storage only)."""
    registry = ProviderRegistry()
    registry.register("storage", storage)
    return registry
