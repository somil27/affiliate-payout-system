"""Structured JSON logging setup."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in {
                "args", "msg", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "taskName",
                "message",
            }:
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # Tame noisy libraries.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
