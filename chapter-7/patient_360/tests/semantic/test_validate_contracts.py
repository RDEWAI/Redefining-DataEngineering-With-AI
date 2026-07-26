"""The semantic model must reconcile against the physical Gold contracts (anti-drift gate)."""

from __future__ import annotations

from patient_360.semantic import Severity, load_model, validate_model
from patient_360.semantic.schema import (
    AggKind,
    Dimension,
    Entity,
    Measure,
    SemanticModel,
)


def test_shipped_model_has_no_critical_or_warning() -> None:
    findings = validate_model(load_model())
    blocking = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.WARNING)]
    assert not blocking, "unexpected blocking findings:\n" + "\n".join(f.format() for f in blocking)


def test_bogus_dimension_column_is_critical() -> None:
    # A real Gold table but a column that does not exist in its contract.
    model = SemanticModel(
        name="broken",
        entities=[Entity(
            name="patient_summary",
            table="unity.gold.patient_summary",
            grain="one row per patient",
            primary_key="patient_id",
            dimensions=[Dimension(name="ghost", column="not_a_real_column", type="string")],
        )],
    )
    findings = validate_model(model)
    assert any(f.code == "SM-COL-MISSING" and f.severity is Severity.CRITICAL for f in findings)


def test_bogus_measure_column_is_critical() -> None:
    model = SemanticModel(
        name="broken",
        entities=[Entity(
            name="patient_summary",
            table="unity.gold.patient_summary",
            grain="one row per patient",
            primary_key="patient_id",
            measures=[Measure(name="x", agg=AggKind.SUM, expr="nonexistent_col")],
        )],
    )
    findings = validate_model(model)
    assert any(f.code == "SM-MEASURE-COL" and f.severity is Severity.CRITICAL for f in findings)


def test_missing_contract_is_critical() -> None:
    model = SemanticModel(
        name="broken",
        entities=[Entity(
            name="ghost_table",
            table="unity.gold.does_not_exist",
            grain="n/a",
            primary_key="id",
        )],
    )
    findings = validate_model(model)
    assert any(
        f.code == "SM-CONTRACT-MISSING" and f.severity is Severity.CRITICAL for f in findings
    )


def test_dangling_metric_measure_is_critical() -> None:
    model = load_model()
    # Point a metric at a measure that is not defined on its entity.
    model.metrics[0].measure = "no_such_measure"
    findings = validate_model(model)
    assert any(f.code == "SM-METRIC-MEASURE" and f.severity is Severity.CRITICAL for f in findings)
