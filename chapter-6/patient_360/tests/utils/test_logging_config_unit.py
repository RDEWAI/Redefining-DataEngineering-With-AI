"""Unit tests for patient_360.utils.logging_config."""

from __future__ import annotations

import json
import logging

from patient_360.utils.logging_config import (
    JsonFormatter,
    configure_logging,
    get_logger,
)


def test_json_formatter_emits_required_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.pipeline_run_id = "run-1"
    record.task_id = "task-1"
    record.ds = "2026-05-11"
    payload = json.loads(formatter.format(record))
    assert payload["message"] == "hello"
    assert payload["pipeline_run_id"] == "run-1"
    assert payload["task_id"] == "task-1"
    assert payload["ds"] == "2026-05-11"
    assert payload["level"] == "INFO"


def test_configure_logging_emits_json_to_stdout(capsys) -> None:
    configure_logging(level=logging.INFO)
    log = logging.getLogger("test")
    log.info("a thing happened", extra={"pipeline_run_id": "r", "task_id": "t", "ds": "d"})
    captured = capsys.readouterr().out.strip().splitlines()
    payload = json.loads(captured[-1])
    assert payload["pipeline_run_id"] == "r"
    assert payload["task_id"] == "t"
    assert payload["ds"] == "d"


def test_get_logger_binds_correlation_fields(capsys) -> None:
    configure_logging(level=logging.INFO)
    log = get_logger("scoped", pipeline_run_id="r2", task_id="t2", ds="2026-05-11")
    log.info("scoped event")
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["pipeline_run_id"] == "r2"
    assert payload["task_id"] == "t2"
    assert payload["ds"] == "2026-05-11"


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    handler_count_after_first = len(logging.getLogger().handlers)
    configure_logging()
    handler_count_after_second = len(logging.getLogger().handlers)
    assert handler_count_after_first == handler_count_after_second == 1


def test_json_formatter_includes_exception_info() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="x",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="oops",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert "ValueError: boom" in payload["exc"]
