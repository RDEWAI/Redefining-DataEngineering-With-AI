"""Structured JSON logging configuration for Chapter 2.

This module provides a consistent logging configuration across all modules
with JSON-formatted output for structured log analysis.

Usage:
    from src.agentic.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Processing request", extra={"user_id": "123", "action": "search"})

Environment Variables:
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
    LOG_FORMAT: Log format (json, text). Default: json
    LOG_FILE: Optional file path for log output
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging.

    Formats log records as JSON objects with consistent fields:
    - timestamp: ISO format timestamp in UTC
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - module: Source module name
    - function: Source function name
    - line: Source line number
    - extra: Additional context fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string.

        Args:
            record: The log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
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
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_attrs and not key.startswith("_")
        }
        if extra:
            log_data["extra"] = extra

        return json.dumps(log_data, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter for development.

    Formats log records as readable text with key-value pairs.
    """

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    def __init__(self) -> None:
        """Initialize the text formatter."""
        super().__init__(fmt=self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting operation", extra={"operation": "search"})
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        # Get configuration from environment
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "json").lower()
        log_file = os.getenv("LOG_FILE")

        logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Choose formatter based on format setting
        if log_format == "text":
            formatter: logging.Formatter = TextFormatter()
        else:
            formatter = JSONFormatter()

        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler (optional)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Prevent propagation to root logger
        logger.propagate = False

    return logger


def configure_root_logger() -> None:
    """Configure the root logger for the application.

    This should be called once at application startup to configure
    the root logger with structured JSON logging.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Choose formatter
    if log_format == "text":
        formatter: logging.Formatter = TextFormatter()
    else:
        formatter = JSONFormatter()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# Pre-configured loggers for common modules
def get_library_logger() -> logging.Logger:
    """Get logger for library module."""
    return get_logger("chapter2.library")


def get_llm_logger() -> logging.Logger:
    """Get logger for LLM module."""
    return get_logger("chapter2.llm")


def get_agent_logger() -> logging.Logger:
    """Get logger for agent module."""
    return get_logger("chapter2.agents")


def get_mcp_logger() -> logging.Logger:
    """Get logger for MCP server module."""
    return get_logger("chapter2.mcp")


def get_rag_logger() -> logging.Logger:
    """Get logger for RAG module."""
    return get_logger("chapter2.rag")
