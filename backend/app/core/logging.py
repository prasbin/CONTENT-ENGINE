"""Structured logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

REDACTED = "***REDACTED***"

_HANDLER_NAME = "content_engine_stdout"

# Matches `token=abc`, `"api_key": "x"`, `Authorization: Bearer y`,
# `CE_API_TOKEN: z` - i.e. any identifier containing a sensitive word.
_SENSITIVE_PATTERN = re.compile(
    r"(?i)([A-Za-z0-9_.\-]*(?:token|password|passwd|secret|api[_-]?key|authorization|bearer)"
    r"[A-Za-z0-9_.\-]*)"
    r"([\"']?\s*[:=]\s*|\s+)"
    r"(\"[^\"]*\"|'[^']*'|(?:bearer\s+)?[^\s,;}\])]+)"
)


def redact(text: str) -> str:
    """Mask values assigned to sensitive-looking keys."""
    return _SENSITIVE_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        text,
    )


class RedactingFilter(logging.Filter):
    """Redacts sensitive values from log records before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line - easy to ship to any log aggregator."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Install a single redacting stdout handler on the root logger."""
    root = logging.getLogger()
    root.setLevel(level)

    existing = logging.getHandlerByName(_HANDLER_NAME)
    if existing is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name(_HANDLER_NAME)
        handler.addFilter(RedactingFilter())
        handler.setFormatter(
            JsonLogFormatter()
            if json_logs
            else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
    else:
        existing.setLevel(level)
