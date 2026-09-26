"""Structured logging and secret redaction tests."""

from __future__ import annotations

import io
import json
import logging

from app.core.logging import REDACTED, JsonLogFormatter, RedactingFilter, redact


def test_redact_masks_sensitive_values() -> None:
    cases = [
        ("token=hunter2", "hunter2"),
        ("CE_API_TOKEN: super-secret-value", "super-secret-value"),
        ('{"api_key": "sk-1234567890"}', "sk-1234567890"),
        ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
        ("password = hunter2", "hunter2"),
    ]
    for text, secret in cases:
        output = redact(text)
        assert secret not in output, f"{secret!r} leaked from {text!r}"
        assert REDACTED in output


def test_redact_leaves_benign_text_alone() -> None:
    text = "job queued for https://example.com/video.mp4"
    assert redact(text) == text


def test_json_formatter_outputs_valid_json() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    line = JsonLogFormatter().format(record)
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello world"
    assert "ts" in payload


def test_redacting_filter_scrubs_log_records() -> None:
    logger = logging.getLogger("test.redaction")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("using token=supersecretvalue now")
        logger.warning("password: hunter2 leaked?")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    assert "supersecretvalue" not in output
    assert "hunter2" not in output
    assert output.count(REDACTED) >= 2
    for line in output.strip().splitlines():
        json.loads(line)  # every line must stay valid JSON
