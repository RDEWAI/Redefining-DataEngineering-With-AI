"""Lightweight metrics emitter.

Per LLD §10.1: emits structured metric records to the configured logger
or — when an OpenTelemetry exporter is configured — to the OTel SDK.
"""

from __future__ import annotations

import json
from typing import Any

from .logging_config import get_logger

_logger = get_logger("patient_360.metrics")


def emit_metric(name: str, value: float | int, tags: dict[str, Any] | None = None) -> None:
    """Emit a metric record.

    Parameters
    ----------
    name:
        Dotted metric name (e.g. ``bronze.rows_ingested``).
    value:
        Numeric value (``float`` or ``int``).
    tags:
        Optional key/value tags.

    Notes
    -----
    The default backend is JSON-formatted INFO log lines so operators can
    grep for ``METRIC`` in stdout. Real-time metrics shipping (OTel) is
    layered on top of this function in production.
    """
    if not name:
        raise ValueError("metric name must be non-empty")
    payload: dict[str, Any] = {"metric": name, "value": value, "tags": tags or {}}
    _logger.info("METRIC %s", json.dumps(payload, sort_keys=True))
