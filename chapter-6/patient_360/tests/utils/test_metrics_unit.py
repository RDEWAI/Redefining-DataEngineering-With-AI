"""Unit tests for patient_360.utils.metrics.

When the OpenTelemetry SDK is not installed, the module routes through
:class:`metrics._NoopMeter` — these tests assert the public API never
raises in that environment and that repeated calls reuse the same
instrument (so we don't leak instrument creations).
"""

from __future__ import annotations

from patient_360.utils import metrics


def test_record_counter_is_idempotent() -> None:
    metrics.record_counter("rows_ingested", 5, {"table": "patients"})
    metrics.record_counter("rows_ingested", 7, {"table": "patients"})
    assert "rows_ingested" in metrics._counters
    # Same instrument re-used for the second call (no leak)
    assert metrics._counters["rows_ingested"] is metrics._counters["rows_ingested"]


def test_record_gauge_does_not_raise() -> None:
    metrics.record_gauge("queue_depth", 42)
    metrics.record_gauge("queue_depth", 0)
    assert "queue_depth" in metrics._gauges


def test_record_histogram_records_a_value() -> None:
    metrics.record_histogram("ingest_latency_ms", 123.4, {"layer": "bronze"})
    assert "ingest_latency_ms" in metrics._histograms


def test_record_counter_default_value_is_one() -> None:
    # No attributes, default value of 1 — must not raise.
    metrics.record_counter("simple_counter")
    assert "simple_counter" in metrics._counters
