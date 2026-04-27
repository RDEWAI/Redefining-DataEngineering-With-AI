"""Structured logging helper.

Per LLD §10.1 and ``logging-error-handling.md``: standard format,
module-level loggers, no f-strings, no ``print()``.
"""

from __future__ import annotations

import logging
import os

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_configured = False


def _ensure_basic_config() -> None:
    global _configured
    if _configured:
        return
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured stdlib logger for ``name``.

    The first call configures the root logger with the standard
    pipeline format; subsequent calls reuse the existing config.
    """
    if not name:
        raise ValueError("logger name must be a non-empty string")
    _ensure_basic_config()
    return logging.getLogger(name)
