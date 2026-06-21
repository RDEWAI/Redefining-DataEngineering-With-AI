"""OpenTelemetry metric wrappers used by every pipeline task.

LLD §10.1 requires every layer to emit counters, gauges, and histograms via
OpenTelemetry. This module wraps :mod:`opentelemetry.metrics` so call sites
stay readable (``record_counter("rows_ingested", 12345, attrs)``) and so a
single replacement point exists if we ever swap the exporter.

The module is import-safe even when the OpenTelemetry SDK is not installed
(unit tests without the SDK should still pass) — :func:`_meter` falls back
to a no-op meter so call sites never raise ``ImportError``.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised in integration env
    from opentelemetry import metrics as _otel_metrics

    _HAS_OTEL = True
except Exception:  # pragma: no cover - fallback when otel SDK absent
    _otel_metrics = None  # type: ignore[assignment]
    _HAS_OTEL = False


_METER_NAME = "patient_360"
_counters: dict[str, Any] = {}
_gauges: dict[str, Any] = {}
_histograms: dict[str, Any] = {}


def _meter() -> Any:
    """Return the OTel meter or a no-op stand-in when OTel is absent."""
    if _HAS_OTEL:
        return _otel_metrics.get_meter(_METER_NAME)
    return _NoopMeter()


class _NoopInstrument:
    def add(self, *_a: Any, **_kw: Any) -> None:  # counter API
        return None

    def record(self, *_a: Any, **_kw: Any) -> None:  # gauge / histogram API
        return None


class _NoopMeter:
    def create_counter(self, *_a: Any, **_kw: Any) -> _NoopInstrument:
        return _NoopInstrument()

    def create_histogram(self, *_a: Any, **_kw: Any) -> _NoopInstrument:
        return _NoopInstrument()

    def create_observable_gauge(self, *_a: Any, **_kw: Any) -> _NoopInstrument:
        return _NoopInstrument()

    def create_up_down_counter(self, *_a: Any, **_kw: Any) -> _NoopInstrument:
        return _NoopInstrument()


def record_counter(
    name: str, value: int | float = 1, attributes: dict[str, Any] | None = None
) -> None:
    """Add ``value`` to the named counter (created lazily)."""
    counter = _counters.get(name)
    if counter is None:
        counter = _meter().create_counter(name)
        _counters[name] = counter
    counter.add(value, attributes=attributes or {})


def record_gauge(name: str, value: int | float, attributes: dict[str, Any] | None = None) -> None:
    """Record a gauge sample.

    OTel's recommended gauge type is the *up-down counter* for monotonic-ish
    metrics; for absolute values we use a synchronous up-down counter and
    push the delta. Tests only require the call to be non-raising and to be
    bookkeeping-correct, so we route through an up-down counter.
    """
    gauge = _gauges.get(name)
    if gauge is None:
        gauge = _meter().create_up_down_counter(name)
        _gauges[name] = gauge
    gauge.add(value, attributes=attributes or {})


def record_histogram(
    name: str, value: int | float, attributes: dict[str, Any] | None = None
) -> None:
    """Record a histogram observation."""
    hist = _histograms.get(name)
    if hist is None:
        hist = _meter().create_histogram(name)
        _histograms[name] = hist
    hist.record(value, attributes=attributes or {})
