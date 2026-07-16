"""Derived clinical fields enumerated by DRD §5.2.

Each function is pure (no Spark dependency) so the Silver transforms and
unit tests can both reuse them. Spark column expressions live in the
Silver transforms themselves; this module owns the reference Python
implementation that the tests assert against.
"""

from __future__ import annotations

from datetime import date


def age_at_visit(birth_date: date | None, visit_date: date | None) -> int | None:
    """Whole-year age at the visit date.

    Returns ``None`` if either input is missing — caller is responsible for
    deciding whether that should drop the row or pass through as NULL.
    """
    if birth_date is None or visit_date is None:
        return None
    years = visit_date.year - birth_date.year
    if (visit_date.month, visit_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)


def bmi_category(bmi: float | None) -> str | None:
    """WHO adult BMI category. Returns ``None`` for missing input."""
    if bmi is None:
        return None
    if bmi < 18.5:
        return "underweight"
    if bmi < 25.0:
        return "normal"
    if bmi < 30.0:
        return "overweight"
    return "obese"


def encounter_duration_minutes(start_iso: str | None, stop_iso: str | None) -> int | None:
    """Encounter length in whole minutes from ISO 8601 timestamps."""
    if not start_iso or not stop_iso:
        return None
    from datetime import datetime

    start = datetime.fromisoformat(start_iso)
    stop = datetime.fromisoformat(stop_iso)
    delta = stop - start
    return max(int(delta.total_seconds() // 60), 0)
