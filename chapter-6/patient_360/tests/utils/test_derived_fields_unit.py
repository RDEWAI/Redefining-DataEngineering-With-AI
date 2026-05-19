"""Unit tests for patient_360.utils.derived_fields (DRD §5.2)."""

from __future__ import annotations

from datetime import date

from patient_360.utils.derived_fields import (
    age_at_visit,
    bmi_category,
    encounter_duration_minutes,
)


class TestAgeAtVisit:
    def test_simple_age(self) -> None:
        assert age_at_visit(date(1990, 1, 1), date(2025, 6, 1)) == 35

    def test_birthday_not_yet_reached_subtracts_one(self) -> None:
        assert age_at_visit(date(1990, 12, 31), date(2025, 1, 1)) == 34

    def test_exact_birthday(self) -> None:
        assert age_at_visit(date(1990, 5, 10), date(2025, 5, 10)) == 35

    def test_missing_inputs_return_none(self) -> None:
        assert age_at_visit(None, date(2025, 1, 1)) is None
        assert age_at_visit(date(2000, 1, 1), None) is None

    def test_future_birth_clamps_at_zero(self) -> None:
        assert age_at_visit(date(2030, 1, 1), date(2025, 1, 1)) == 0


class TestBmiCategory:
    def test_underweight(self) -> None:
        assert bmi_category(17.0) == "underweight"

    def test_normal(self) -> None:
        assert bmi_category(22.0) == "normal"

    def test_overweight(self) -> None:
        assert bmi_category(27.0) == "overweight"

    def test_obese(self) -> None:
        assert bmi_category(31.0) == "obese"

    def test_missing_returns_none(self) -> None:
        assert bmi_category(None) is None


class TestEncounterDuration:
    def test_simple_duration(self) -> None:
        assert encounter_duration_minutes(
            "2026-01-01T10:00:00", "2026-01-01T10:45:00"
        ) == 45

    def test_zero_duration(self) -> None:
        assert encounter_duration_minutes(
            "2026-01-01T10:00:00", "2026-01-01T10:00:00"
        ) == 0

    def test_missing_returns_none(self) -> None:
        assert encounter_duration_minutes(None, "2026-01-01T10:00:00") is None
        assert encounter_duration_minutes("2026-01-01T10:00:00", None) is None
