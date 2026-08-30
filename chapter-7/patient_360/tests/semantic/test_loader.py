"""Load the shipped semantic/ directory into a SemanticModel."""

from __future__ import annotations

from patient_360.semantic import load_model

_EXPECTED_TABLES = {
    "unity.gold.patient_summary",
    "unity.gold.patient_clinical_history",
    "unity.gold.patient_billing_summary",
}


def test_loads_three_gold_entities() -> None:
    model = load_model()
    assert {e.table for e in model.entities} == _EXPECTED_TABLES


def test_relationships_and_metrics_present() -> None:
    model = load_model()
    assert len(model.relationships) == 3
    assert model.metrics, "expected named business metrics in the manifest"
    assert model.verified_queries, "expected verified example queries"


def test_known_measure_resolves() -> None:
    model = load_model()
    billing = model.entity_by_table("unity.gold.patient_billing_summary")
    assert billing is not None
    encounter_count = billing.measure("encounter_count")
    assert encounter_count is not None
    # Billing must count encounters with DISTINCT to survive claim fan-out.
    assert encounter_count.to_sql() == "COUNT(DISTINCT encounter_id)"


def test_glossary_maps_coded_values() -> None:
    model = load_model()
    assert model.glossary.get("married") == "marital_status = 'M'"
