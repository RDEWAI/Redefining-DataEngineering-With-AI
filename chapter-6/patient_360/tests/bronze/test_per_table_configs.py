"""STORY-02-003 -- Bronze per-table ingestion YAML configs contract tests.

Asserts the 13 ``airflow/configs/<table>.yml`` files satisfy every
acceptance criterion in the story:

* AC1 -- exactly 13 files exist (one per LLD §5.1 Bronze task)
* AC2 -- the six critical tables declare ``empty_input_behavior: fail``
* AC3 -- every config declares
  ``output_table: <catalog>.<schema>.synthea_<stem>`` resolved from the
  ``catalog_bronze_catalog_name`` / ``catalog_bronze_schema`` keys
  (defaults ``unity`` / ``bronze`` per LLD §7.1)
* AC4 -- each YAML's ``dq_rules_table`` resolves to ``dq_rules/<table>.yml``
  on disk (LLD §2.3 convention-based discovery)

These are pure YAML / filesystem checks -- no Spark required.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "airflow" / "configs"
DQ_RULES_DIR = PROJECT_ROOT / "dq_rules"
CONTRACTS_DIR = PROJECT_ROOT / "contracts"

# LLD §5.1 Bronze task list (filename stems, sans .yml).
LLD_BRONZE_STEMS: tuple[str, ...] = (
    "patients",
    "encounters",
    "conditions",
    "medications",
    "observations",
    "allergies",
    "immunizations",
    "procedures",
    "claims",
    "careplans",
    "organizations",
    "providers",
    "payers",
)

# LLD §5.1 -- six tables flagged `fail` (patients, encounters, allergies,
# organizations, providers, payers). Critical for downstream / FK joins.
CRITICAL_FAIL_STEMS: frozenset[str] = frozenset(
    {"patients", "encounters", "allergies", "organizations", "providers", "payers"}
)


def _config_files() -> list[Path]:
    return sorted(CONFIGS_DIR.glob("*.yml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------------------
# AC1 -- 13 files exist, one per LLD §5.1 Bronze task
# ---------------------------------------------------------------------------
def test_ac1_exactly_thirteen_configs_exist() -> None:
    files = _config_files()
    assert len(files) == 13, (
        f"Expected 13 per-table configs in {CONFIGS_DIR}, found {len(files)}: "
        f"{[f.name for f in files]}"
    )


def test_ac1_filename_stems_match_lld_bronze_tasks() -> None:
    actual = {p.stem for p in _config_files()}
    expected = set(LLD_BRONZE_STEMS)
    missing = expected - actual
    extra = actual - expected
    assert not missing and not extra, (
        f"Config stems do not match LLD §5.1. missing={sorted(missing)} "
        f"extra={sorted(extra)}"
    )


# ---------------------------------------------------------------------------
# AC2 -- critical tables declare empty_input_behavior: fail
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("stem", sorted(CRITICAL_FAIL_STEMS))
def test_ac2_critical_table_empty_input_is_fail(stem: str) -> None:
    cfg = _load(CONFIGS_DIR / f"{stem}.yml")
    assert cfg.get("empty_input_behavior") == "fail", (
        f"{stem}.yml: critical table must declare empty_input_behavior=fail "
        f"per LLD §5.1, got {cfg.get('empty_input_behavior')!r}"
    )


def test_ac2_exactly_six_configs_use_fail() -> None:
    fail_stems = {
        p.stem
        for p in _config_files()
        if _load(p).get("empty_input_behavior") == "fail"
    }
    assert fail_stems == CRITICAL_FAIL_STEMS, (
        f"Expected exactly the 6 LLD §5.1 critical tables to use fail. "
        f"Actual fail set: {sorted(fail_stems)}"
    )


def test_ac2_non_critical_tables_default_to_write_empty() -> None:
    non_critical = set(LLD_BRONZE_STEMS) - CRITICAL_FAIL_STEMS
    for stem in non_critical:
        cfg = _load(CONFIGS_DIR / f"{stem}.yml")
        assert cfg.get("empty_input_behavior") == "write_empty", (
            f"{stem}.yml: non-critical table should default to write_empty, "
            f"got {cfg.get('empty_input_behavior')!r}"
        )


# ---------------------------------------------------------------------------
# AC3 -- output_table resolves from catalog_bronze_* keys to unity.bronze.*
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", _config_files(), ids=lambda p: p.stem)
def test_ac3_output_table_matches_catalog_schema_table(path: Path) -> None:
    cfg = _load(path)
    catalog = cfg.get("catalog_bronze_catalog_name")
    schema = cfg.get("catalog_bronze_schema")
    table = cfg.get("table")
    output_table = cfg.get("output_table")

    assert catalog == "unity", (
        f"{path.name}: catalog_bronze_catalog_name must default to 'unity' "
        f"per LLD §7.1, got {catalog!r}"
    )
    assert schema == "bronze", (
        f"{path.name}: catalog_bronze_schema must default to 'bronze' "
        f"per LLD §7.1, got {schema!r}"
    )
    assert table == f"synthea_{path.stem}", (
        f"{path.name}: table must be 'synthea_{path.stem}', got {table!r}"
    )
    assert output_table == f"{catalog}.{schema}.{table}", (
        f"{path.name}: output_table must equal "
        f"'{catalog}.{schema}.{table}', got {output_table!r}"
    )
    assert output_table.startswith("unity.bronze."), (
        f"{path.name}: output_table must be UC-managed under unity.bronze.*"
    )


# ---------------------------------------------------------------------------
# AC4 -- dq_rules_table resolves to dq_rules/<table>.yml on disk
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", _config_files(), ids=lambda p: p.stem)
def test_ac4_dq_rules_table_resolves_to_existing_file(path: Path) -> None:
    cfg = _load(path)
    dq_rules_table = cfg.get("dq_rules_table")
    assert dq_rules_table == cfg.get("table"), (
        f"{path.name}: dq_rules_table must equal the Bronze table name "
        f"({cfg.get('table')!r}), got {dq_rules_table!r}"
    )
    target = DQ_RULES_DIR / f"{dq_rules_table}.yml"
    assert target.is_file(), (
        f"{path.name}: dq_rules_table={dq_rules_table!r} but "
        f"{target.relative_to(PROJECT_ROOT)} does not exist on disk"
    )


# ---------------------------------------------------------------------------
# Bonus structural checks -- referenced contract exists, required keys present
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", _config_files(), ids=lambda p: p.stem)
def test_referenced_contract_exists(path: Path) -> None:
    cfg = _load(path)
    schema_ref = cfg.get("schema_ref")
    assert schema_ref, f"{path.name}: schema_ref is required"
    target = PROJECT_ROOT / schema_ref
    assert target.is_file(), (
        f"{path.name}: schema_ref points to {schema_ref!r} but that file "
        "does not exist"
    )


REQUIRED_KEYS: tuple[str, ...] = (
    "table",
    "layer",
    "source",
    "schema_ref",
    "output_table",
    "catalog_bronze_catalog_name",
    "catalog_bronze_schema",
    "metadata_columns",
    "empty_input_behavior",
    "dq_rules_table",
    "dq_rules_dir",
    "se_action_if_failed",
    "quarantine_path",
    "timeout_minutes",
    "retries",
    "retry_delay_seconds",
)


@pytest.mark.parametrize("path", _config_files(), ids=lambda p: p.stem)
def test_required_keys_present(path: Path) -> None:
    cfg = _load(path)
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    assert not missing, f"{path.name}: missing required keys {missing}"


@pytest.mark.parametrize("path", _config_files(), ids=lambda p: p.stem)
def test_metadata_columns_match_runner_contract(path: Path) -> None:
    cfg = _load(path)
    assert cfg.get("metadata_columns") == ["ds", "_ingested_at", "_source_batch_id"], (
        f"{path.name}: metadata_columns must match the LLD §2.3 / runner "
        f"contract ['ds', '_ingested_at', '_source_batch_id']"
    )
