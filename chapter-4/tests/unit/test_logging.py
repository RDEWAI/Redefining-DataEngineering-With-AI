"""Tests for the structured logging module."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from pwi.utils.logging import (
    JSONFormatter,
    LogContext,
    PrettyFormatter,
    get_logger,
    log_agent_complete,
    log_agent_error,
    log_agent_start,
    log_workflow_event,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_basic_record(self) -> None:
        """Test formatting a basic log record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert parsed["location"]["file"] == "test.py"
        assert parsed["location"]["line"] == 10

    def test_format_with_extra_fields(self) -> None:
        """Test formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.session_id = "test-session-123"
        record.agent = "data_analyst"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "extra" in parsed
        assert parsed["extra"]["session_id"] == "test-session-123"
        assert parsed["extra"]["agent"] == "data_analyst"

    def test_format_with_exception(self) -> None:
        """Test formatting with exception info."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "Test error" in parsed["exception"]


class TestPrettyFormatter:
    """Tests for PrettyFormatter class."""

    def test_format_info_level(self) -> None:
        """Test formatting INFO level record."""
        formatter = PrettyFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        assert "INFO" in output
        assert "test.logger" in output
        assert "Test message" in output

    def test_format_with_context(self) -> None:
        """Test formatting with contextual fields."""
        formatter = PrettyFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.session_id = "test-123"
        record.agent = "data_analyst"

        output = formatter.format(record)
        assert "session_id=test-123" in output
        assert "agent=data_analyst" in output


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_default_logging(self) -> None:
        """Test default logging setup."""
        setup_logging()
        logger = get_logger("test")
        assert logger.name == "pwi.test"

    def test_setup_debug_level(self) -> None:
        """Test debug level setup."""
        setup_logging(level="DEBUG")
        root_logger = logging.getLogger("pwi")
        assert root_logger.level == logging.DEBUG

    def test_setup_json_output(self) -> None:
        """Test JSON output mode."""
        setup_logging(json_output=True)
        root_logger = logging.getLogger("pwi")
        # Check that at least one handler uses JSONFormatter
        has_json_formatter = any(
            isinstance(h.formatter, JSONFormatter) for h in root_logger.handlers
        )
        assert has_json_formatter


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_name(self) -> None:
        """Test getting a logger with a name."""
        logger = get_logger("mymodule")
        assert logger.name == "pwi.mymodule"

    def test_get_logger_nested_name(self) -> None:
        """Test getting a logger with nested name."""
        logger = get_logger("workflow.orchestrator")
        assert logger.name == "pwi.workflow.orchestrator"


class TestLogContext:
    """Tests for LogContext class."""

    def test_log_context_adds_fields(self) -> None:
        """Test that LogContext adds fields to log records."""
        setup_logging()
        logger = get_logger("test_context")

        # Capture log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        with LogContext(logger, session_id="ctx-123", agent="test_agent"):
            logger.info("Test message in context")

        output = stream.getvalue()
        parsed = json.loads(output)

        assert parsed["extra"]["session_id"] == "ctx-123"
        assert parsed["extra"]["agent"] == "test_agent"


class TestConvenienceFunctions:
    """Tests for logging convenience functions."""

    def setup_method(self) -> None:
        """Set up test logging."""
        setup_logging(level="DEBUG")
        self.logger = get_logger("test_convenience")

        # Capture log output
        self.stream = StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def test_log_agent_start(self) -> None:
        """Test log_agent_start function."""
        log_agent_start(self.logger, "data_analyst", "session-123")

        output = self.stream.getvalue()
        parsed = json.loads(output)

        assert parsed["message"] == "Agent starting"
        assert parsed["extra"]["agent"] == "data_analyst"
        assert parsed["extra"]["session_id"] == "session-123"
        assert parsed["extra"]["operation"] == "start"

    def test_log_agent_complete(self) -> None:
        """Test log_agent_complete function."""
        log_agent_complete(
            self.logger,
            "data_analyst",
            "session-123",
            tokens_used=1500,
            cost_usd=0.015,
        )

        output = self.stream.getvalue()
        parsed = json.loads(output)

        assert parsed["message"] == "Agent completed"
        assert parsed["extra"]["agent"] == "data_analyst"
        assert parsed["extra"]["tokens_used"] == 1500
        assert parsed["extra"]["cost_usd"] == 0.015

    def test_log_agent_error(self) -> None:
        """Test log_agent_error function."""
        log_agent_error(
            self.logger,
            "data_analyst",
            "session-123",
            "API timeout",
        )

        output = self.stream.getvalue()
        parsed = json.loads(output)

        assert parsed["message"] == "Agent failed"
        assert parsed["extra"]["error"] == "API timeout"
        assert parsed["level"] == "ERROR"

    def test_log_workflow_event(self) -> None:
        """Test log_workflow_event function."""
        log_workflow_event(
            self.logger,
            "session-123",
            "state_transition",
            {"from_state": "running", "to_state": "review"},
        )

        output = self.stream.getvalue()
        parsed = json.loads(output)

        assert "state_transition" in parsed["message"]
        assert parsed["extra"]["from_state"] == "running"
        assert parsed["extra"]["to_state"] == "review"
