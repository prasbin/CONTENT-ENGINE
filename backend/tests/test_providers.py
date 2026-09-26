"""Provider interface and registry tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app.core.errors import ContentEngineError, ProviderNotConfiguredError
from app.providers import (
    PHASE_HINTS,
    ProviderRegistry,
    TranscriptionProvider,
    build_default_registry,
)
from app.storage.local import LocalStorage


class StubTranscriber:
    """Minimal object that satisfies the TranscriptionProvider protocol."""

    def transcribe(self, source_ref: str) -> dict[str, Any]:
        return {"language": "en", "segments": [{"start": 0.0, "end": 1.5, "text": "hi"}]}


def run_transcription(provider: TranscriptionProvider) -> dict[str, Any]:
    return provider.transcribe("source-ref")


def test_protocol_usable_with_stub_implementation() -> None:
    result = run_transcription(StubTranscriber())
    assert result["segments"][0]["text"] == "hi"


def test_default_registry_contains_storage(tmp_path: Path) -> None:
    registry = build_default_registry(storage=LocalStorage(tmp_path))
    assert "storage" in registry
    assert registry.names() == ["storage"]
    storage = registry.get("storage")
    assert isinstance(storage, LocalStorage)


def test_missing_provider_raises_clear_error(tmp_path: Path) -> None:
    registry = build_default_registry(storage=LocalStorage(tmp_path))
    with pytest.raises(ProviderNotConfiguredError) as excinfo:
        registry.get("transcription")
    message = str(excinfo.value)
    assert "transcription" in message
    assert PHASE_HINTS["transcription"] in message
    assert isinstance(excinfo.value, ContentEngineError)
    assert excinfo.value.status_code == 501
    assert excinfo.value.code == "provider_not_configured"


def test_registry_register_and_override() -> None:
    registry = ProviderRegistry()
    registry.register("renderer", object())
    assert "renderer" in registry
    replacement = object()
    registry.register("renderer", replacement)
    assert registry.get("renderer") is replacement


def test_registry_rejects_empty_name() -> None:
    registry = ProviderRegistry()
    with pytest.raises(ValueError):
        registry.register("  ", object())


def test_phase_hint_covers_future_providers() -> None:
    expected = {
        "video_source",
        "transcription",
        "clip_detection",
        "renderer",
        "captions",
        "metadata",
        "publishers",
    }
    assert set(PHASE_HINTS) == expected
