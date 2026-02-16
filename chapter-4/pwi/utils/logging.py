"""Structured logging utilities for Planning with Intent.

This module provides JSON-formatted structured logging with support for
contextual information like session IDs, agent names, and operation details.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info
        if record.pathname:
            log_entry["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from the record
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key
            not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
                "message",
            }
        }
        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str)


class PrettyFormatter(logging.Formatter):
    """Human-readable formatter for console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: The log record to format.

        Returns:
            Colored formatted log string.
        """
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET

        # Build base message
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = f"{color}{record.levelname:8}{reset}"
        name = f"\033[90m{record.name}\033[0m"

        # Format message
        message = record.getMessage()

        # Add extra context if present
        extra_parts = []
        for key in ("session_id", "agent", "operation"):
            if hasattr(record, key):
                extra_parts.append(f"{key}={getattr(record, key)}")

        context = f" [{', '.join(extra_parts)}]" if extra_parts else ""

        formatted = f"{timestamp} {level} {name}{context}: {message}"

        # Add exception info
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure logging for the PWI application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, output structured JSON logs.
        log_file: Optional file path to write logs to.
    """
    root_logger = logging.getLogger("pwi")
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, level.upper()))

    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(PrettyFormatter())

    root_logger.addHandler(console_handler)

    # File handler (always JSON for machine parsing)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Capture all levels in file
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Args:
        name: Logger name, typically __name__ of the module.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(f"pwi.{name}")


class LogContext:
    """Context manager for adding contextual information to logs."""

    def __init__(
        self,
        logger: logging.Logger,
        **context: Any,
    ) -> None:
        """Initialize log context.

        Args:
            logger: The logger to add context to.
            **context: Key-value pairs to add to all logs.
        """
        self.logger = logger
        self.context = context
        self._old_factory: Any = None

    def __enter__(self) -> LogContext:
        """Enter the context, adding fields to log records."""
        old_factory = logging.getLogRecordFactory()
        self._old_factory = old_factory
        context = self.context

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = old_factory(*args, **kwargs)
            for key, value in context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit the context, restoring the original factory."""
        if self._old_factory is not None:
            logging.setLogRecordFactory(self._old_factory)


# Convenience functions for structured logging
def log_agent_start(
    logger: logging.Logger,
    agent_name: str,
    session_id: str,
) -> None:
    """Log agent execution start.

    Args:
        logger: Logger instance.
        agent_name: Name of the agent starting.
        session_id: Current session ID.
    """
    logger.info(
        "Agent starting",
        extra={"agent": agent_name, "session_id": session_id, "operation": "start"},
    )


def log_agent_complete(
    logger: logging.Logger,
    agent_name: str,
    session_id: str,
    tokens_used: int,
    cost_usd: float | None = None,
) -> None:
    """Log agent execution completion.

    Args:
        logger: Logger instance.
        agent_name: Name of the agent.
        session_id: Current session ID.
        tokens_used: Number of tokens consumed.
        cost_usd: Estimated cost in USD.
    """
    logger.info(
        "Agent completed",
        extra={
            "agent": agent_name,
            "session_id": session_id,
            "operation": "complete",
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        },
    )


def log_agent_error(
    logger: logging.Logger,
    agent_name: str,
    session_id: str,
    error: str,
) -> None:
    """Log agent execution error.

    Args:
        logger: Logger instance.
        agent_name: Name of the agent.
        session_id: Current session ID.
        error: Error message.
    """
    logger.error(
        "Agent failed",
        extra={
            "agent": agent_name,
            "session_id": session_id,
            "operation": "error",
            "error": error,
        },
    )


def log_workflow_event(
    logger: logging.Logger,
    session_id: str,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a workflow event.

    Args:
        logger: Logger instance.
        session_id: Current session ID.
        event: Event name (e.g., "state_transition", "review_approved").
        details: Additional event details.
    """
    extra: dict[str, Any] = {
        "session_id": session_id,
        "operation": event,
    }
    if details:
        extra.update(details)

    logger.info(f"Workflow event: {event}", extra=extra)
