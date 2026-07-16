"""Structured JSON logging for pipeline tasks.

Per LLD §10.1, every log line must carry ``pipeline_run_id``, ``task_id``,
and ``ds`` so logs from concurrent runs can be correlated downstream.
The formatter emits one JSON object per line — friendly to log aggregators
(Loki, Datadog) and to the ``jq``-based local dev workflow.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON.

    Reserved extras (``pipeline_run_id``, ``task_id``, ``ds``) are surfaced as
    top-level keys; any additional ``extra=`` dict on the call site is merged
    in under the same record.
    """

    _RESERVED = {"pipeline_run_id", "task_id", "ds"}

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - matches stdlib API
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Surface reserved correlation fields when present on the record.
        for key in self._RESERVED:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        # Merge ad-hoc extras attached via the LogRecord's __dict__.
        for key, value in record.__dict__.items():
            if key in payload or key.startswith("_"):
                continue
            if key in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            }:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Install :class:`JsonFormatter` on the root logger.

    Idempotent — calling multiple times replaces the existing handler so
    test setups can reconfigure without leaking handlers across runs.
    """
    root = logging.getLogger()
    # Strip any pre-existing handlers so a re-run installs a single JSON sink.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(
    name: str,
    *,
    pipeline_run_id: str | None = None,
    task_id: str | None = None,
    ds: str | None = None,
) -> logging.LoggerAdapter:
    """Return a :class:`LoggerAdapter` pre-bound with correlation fields.

    The adapter ensures every emitted record carries ``pipeline_run_id``,
    ``task_id``, and ``ds`` without callers having to thread them through
    every ``logger.info(..., extra=...)`` call.
    """
    base = logging.getLogger(name)
    extras = {
        "pipeline_run_id": pipeline_run_id,
        "task_id": task_id,
        "ds": ds,
    }
    return logging.LoggerAdapter(base, extras)
