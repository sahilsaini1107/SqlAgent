"""Structured logging setup.

A single place to configure application logging. In production we emit one JSON object per
line; in development we keep a readable text format. The
current request's trace id is attached to every record via a context variable so logs can be
correlated across the whole request, including each agent node.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar

# Set by the request middleware; read by the formatter. Empty outside a request.
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

_RESERVED = set(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON line, including any extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace_id = trace_id_var.get()
        if trace_id:
            payload["trace_id"] = trace_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Promote any structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Readable single-line format for local development, with the trace id when present."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<8} {record.name} - {record.getMessage()}"
        trace_id = trace_id_var.get()
        return f"{base} [trace_id={trace_id}]" if trace_id else base


def configure_logging(level: str = "info", *, json_logs: bool = False) -> None:
    """Install a single stream handler on the root logger. Idempotent."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if json_logs else TextFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
