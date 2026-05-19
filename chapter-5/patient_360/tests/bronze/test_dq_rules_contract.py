"""STORY-02-005 -- Bronze per-table SE rule YAML contract tests.

Pure YAML / filesystem checks against ``patient_360/dq_rules/*.yml``. No
Spark required. Mirrors :mod:`test_configs_contract` but enforces the
Spark Expectations schema synced from
``chapter-4/outputs/dqs/v2/se-rules/se-rules-synthea-<table>.yaml``.

Acceptance criteria covered:

* AC1 -- exactly 13 ``dq_rules/synthea_<table>.yml`` files exist (per
  LLD §5.1 Bronze task list / DQS §2).
* AC2 -- each YAML has >=1 ``row_dq`` and >=1 ``agg_dq`` rule
  (DQS §2-3).
* AC3 -- the six critical-table YAMLs (patients, encounters, allergies,
  organizations, providers, payers) declare ``action_if_failed: fail``
  on at least one rule (LLD §5.4 fail-closed default).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DQ_RULES_DIR = PROJECT_ROOT / "dq_rules"

# LLD §5.1 Bronze task list — synced one-to-one with the per-table
# airflow/configs/<stem>.yml files. Mirrors test_configs_contract.
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

EXPECTED_TABLE_NAMES: tuple[str, ...] = tuple(f"synthea_{s}" for s in LLD_BRONZE_STEMS)

# LLD §5.4 critical-table fail-closed set.
CRITICAL_FAIL_STEMS: frozenset[str] = frozenset(
    {"patients", "encounters", "allergies", "organizations", "providers", "payers"}
)

REQUIRED_SE_KEYS: tuple[str, ...] = ("product_id", "dq_env", "rules")
REQUIRED_DQ_ENV_KEYS: tuple[str, ...] = ("DEV", "QA", "PROD")
REQUIRED_RULE_KEYS: tuple[str, ...] = (
    "rule",
    "rule_type",
    "expectation",
    "action_if_failed",
    "tag",
    "description",
)


def _rule_files() -> list[Path]:
    return sorted(DQ_RULES_DIR.glob("*.yml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------------------
# AC1 -- 13 files exist, one per LLD §5.1 Bronze task
# ---------------------------------------------------------------------------
def test_ac1_exactly_thirteen_rule_files_exist() -> None:
    files = _rule_files()
    assert len(files) == 13, (
        f"Expected 13 per-table rule YAMLs in {DQ_RULES_DIR}, "
        f"found {len(files)}: {[f.name for f in files]}"
    )


def test_ac1_filename_stems_match_bronze_table_names() -> None:
    actual = {p.stem for p in _rule_files()}
    expected = set(EXPECTED_TABLE_NAMES)
    missing = expected - actual
    extra = actual - expected
    assert not missing and not extra, (
        f"Rule stems do not match LLD §5.1. missing={sorted(missing)} "
        f"extra={sorted(extra)}"
    )


# ---------------------------------------------------------------------------
# Schema basics — SE 2.6+ envelope must be parseable
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", _rule_files(), ids=lambda p: p.stem)
def test_required_se_keys_present(path: Path) -> None:
    cfg = _load(path)
    missing = [k for k in REQUIRED_SE_KEYS if k not in cfg]
    assert not missing, f"{path.name}: missing required SE keys {missing}"


@pytest.mark.parametrize("path", _rule_files(), ids=lambda p: p.stem)
def test_dq_env_block_has_three_envs(path: Path) -> None:
    cfg = _load(path)
    dq_env = cfg.get("dq_env") or {}
    missing = [k for k in REQUIRED_DQ_ENV_KEYS if k not in dq_env]
    assert not missing, f"{path.name}: dq_env missing envs {missing}"


@pytest.mark.parametrize("path", _rule_files(), ids=lambda p: p.stem)
def test_product_id_matches_dqs(path: Path) -> None:
    cfg = _load(path)
    assert cfg.get("product_id") == "patient-360", (
        f"{path.name}: product_id must be 'patient-360' "
        f"(matches DQS §2 product), got {cfg.get('product_id')!r}"
    )


# ---------------------------------------------------------------------------
# AC2 -- each YAML has >=1 row_dq and >=1 agg_dq rule
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", _rule_files(), ids=lambda p: p.stem)
def test_ac2_at_least_one_row_dq_and_agg_dq(path: Path) -> None:
    cfg = _load(path)
    rules = cfg.get("rules") or []
    row_dq = [r for r in rules if r.get("rule_type") == "row_dq"]
    agg_dq = [r for r in rules if r.get("rule_type") == "agg_dq"]
    assert row_dq, f"{path.name}: must declare at least one row_dq rule (DQS §2)"
    assert agg_dq, f"{path.name}: must declare at least one agg_dq rule (DQS §3)"


@pytest.mark.parametrize("path", _rule_files(), ids=lambda p: p.stem)
def test_each_rule_has_required_keys(path: Path) -> None:
    cfg = _load(path)
    rules = cfg.get("rules") or []
    for rule in rules:
        missing = [k for k in REQUIRED_RULE_KEYS if k not in rule]
        assert not missing, (
            f"{path.name}: rule {rule.get('rule')!r} missing keys {missing}"
        )


# ---------------------------------------------------------------------------
# AC3 -- critical tables declare action_if_failed: fail on >=1 rule
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("stem", sorted(CRITICAL_FAIL_STEMS))
def test_ac3_critical_tables_have_fail_action(stem: str) -> None:
    cfg = _load(DQ_RULES_DIR / f"synthea_{stem}.yml")
    rules = cfg.get("rules") or []
    fail_rules = [r for r in rules if r.get("action_if_failed") == "fail"]
    assert fail_rules, (
        f"synthea_{stem}.yml: critical table must declare at least one "
        f"rule with action_if_failed=fail per LLD §5.4"
    )
