"""Structural validation of the pydantic semantic-model types."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from patient_360.semantic.schema import (
    AggKind,
    Dimension,
    Entity,
    Measure,
    SemanticModel,
)


def _entity(**overrides: object) -> Entity:
    base: dict[str, object] = {
        "name": "t",
        "table": "unity.gold.t",
        "grain": "one row per thing",
        "primary_key": "id",
        "dimensions": [Dimension(name="id", column="id", type="string")],
    }
    base.update(overrides)
    return Entity(**base)  # type: ignore[arg-type]


def test_measure_to_sql_variants() -> None:
    assert Measure(name="c", agg=AggKind.COUNT).to_sql() == "COUNT(*)"
    distinct = Measure(name="d", agg=AggKind.COUNT_DISTINCT, expr="pid")
    assert distinct.to_sql() == "COUNT(DISTINCT pid)"
    assert Measure(name="s", agg=AggKind.SUM, expr="cost").to_sql() == "SUM(cost)"
    custom = Measure(name="r", agg=AggKind.CUSTOM, expr="AVG(CASE WHEN x THEN 1 ELSE 0 END)")
    assert custom.to_sql() == "AVG(CASE WHEN x THEN 1 ELSE 0 END)"


def test_non_count_measure_requires_expr() -> None:
    with pytest.raises(ValidationError):
        Measure(name="s", agg=AggKind.SUM)


def test_duplicate_dimension_names_rejected() -> None:
    with pytest.raises(ValidationError):
        _entity(dimensions=[
            Dimension(name="a", column="x"),
            Dimension(name="a", column="y"),
        ])


def test_unknown_key_rejected() -> None:
    with pytest.raises(ValidationError):
        Dimension(name="a", column="x", typo=True)  # type: ignore[call-arg]


def test_model_requires_at_least_one_entity() -> None:
    with pytest.raises(ValidationError):
        SemanticModel(name="m", entities=[])


def test_model_lookup_helpers() -> None:
    model = SemanticModel(name="m", entities=[_entity()])
    assert model.entity("t") is not None
    assert model.entity_by_table("unity.gold.t") is not None
    assert model.tables() == ["unity.gold.t"]
