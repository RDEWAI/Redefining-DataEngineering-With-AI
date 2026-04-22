#!/usr/bin/env python3
"""Static validator for the Bronze config-driven ingestion framework.

Checks that the runner/factory/wrapper modules exist and parse, that every
Bronze table listed in LLD §5.1 has a matching `airflow/configs/{table}.yml`,
and that each per-table YAML points to real contract and dq_rules files with
the required keys.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


REQUIRED_MODULES = (
    "ingestion_runner.py",
    "ingestion_factory.py",
    "spark_submit_wrapper.py",
)

REQUIRED_RUNTIME_DEPS = ("pyspark", "delta-spark", "spark-expectations", "pyyaml")
REQUIRED_DEV_DEPS = ("apache-airflow-providers-apache-spark",)

REQUIRED_TEST_MODULES = (
    "test_ingestion_runner.py",
    "test_per_table_configs.py",
    "test_validate_ingestion.py",
)

REQUIRED_YAML_KEYS = (
    "table",
    "source",
    "schema_ref",
    "output_path",
    "empty_input_behavior",
    "dq_rules_table",
)

CRITICAL_EMPTY_FAIL_TABLES = {
    "patients",
    "encounters",
    "allergies",
    "organizations",
    "providers",
    "payers",
}

REQUIRED_METADATA_COLUMNS = {"ds", "_ingested_at", "_source_batch_id"}

LLD_TASK_ROW = re.compile(
    r"`ingest_(?P<table>[a-z_]+)`\s*\|\s*Bronze",
)


@dataclass
class Findings:
    critical: list[str] = field(default_factory=list)
    warning: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def critical_count(self) -> int:
        return len(self.critical)

    def render(self) -> str:
        lines = [f"CRITICAL: {len(self.critical)} issue(s)"]
        for item in self.critical:
            lines.append(f"  - {item}")
        lines.append(f"\nWARNING: {len(self.warning)} issue(s)")
        for item in self.warning:
            lines.append(f"  - {item}")
        lines.append(f"\nINFO: {len(self.info)} item(s)")
        for item in self.info:
            lines.append(f"  - {item}")
        lines.append("")
        lines.append(f"Result: {'FAIL' if self.critical else 'PASS'}")
        return "\n".join(lines)


def extract_bronze_tables_from_lld(lld_path: Path) -> set[str]:
    """Scan the LLD for every `ingest_{table}` row in §5.1 Bronze tasks."""
    text = lld_path.read_text(encoding="utf-8")
    return {m.group("table") for m in LLD_TASK_ROW.finditer(text)}


def check_module_syntax(module_path: Path, findings: Findings) -> None:
    source = module_path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(module_path))
    except SyntaxError as exc:
        findings.critical.append(
            f"{module_path}: python syntax error — {exc.msg} (line {exc.lineno})"
        )
        return

    if not ast.get_docstring(ast.parse(source)):
        findings.info.append(f"{module_path}: missing module-level docstring")

    if re.search(r"(?i)(password|secret|token|api[_-]?key)\s*=\s*['\"]", source):
        findings.critical.append(
            f"{module_path}: possible hardcoded credential (password/secret/token/api_key)"
        )

    # absolute POSIX / Windows path literals are suspect in ingestion code
    for match in re.finditer(r"['\"](/[A-Za-z0-9_./-]+|[A-Z]:\\\\[^'\"]+)['\"]", source):
        literal = match.group(1)
        if literal.startswith("/tmp") or literal.startswith("/dev/null"):
            continue
        findings.critical.append(
            f"{module_path}: absolute filesystem path literal {literal!r}"
        )


def check_yaml_config(
    yaml_path: Path,
    project_root: Path,
    findings: Findings,
) -> str | None:
    """Validate a single `airflow/configs/{table}.yml`. Returns the declared
    `table:` value (lower-cased) so the caller can diff against the LLD."""
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        findings.critical.append(f"{yaml_path}: YAML parse error — {exc}")
        return None

    if not isinstance(data, dict):
        findings.critical.append(f"{yaml_path}: top-level YAML is not a mapping")
        return None

    for key in REQUIRED_YAML_KEYS:
        if key not in data:
            findings.critical.append(f"{yaml_path}: missing required key `{key}`")

    declared_table = str(data.get("table", "")).strip().lower() or None
    if declared_table and declared_table != yaml_path.stem.lower():
        findings.warning.append(
            f"{yaml_path}: `table: {declared_table}` does not match filename `{yaml_path.stem}`"
        )

    behavior = data.get("empty_input_behavior")
    if declared_table in CRITICAL_EMPTY_FAIL_TABLES and behavior != "fail":
        findings.critical.append(
            f"{yaml_path}: critical table `{declared_table}` must set "
            f"empty_input_behavior: fail (got {behavior!r})"
        )
    if behavior is None:
        findings.warning.append(f"{yaml_path}: empty_input_behavior not set explicitly")

    output_path = data.get("output_path")
    if isinstance(output_path, str) and "ds=" in output_path:
        findings.critical.append(
            f"{yaml_path}: output_path embeds `ds=` — must point to the Delta "
            f"table root (runner partitions by ds). Got {output_path!r}"
        )

    declared_metadata = set(data.get("metadata_columns") or ())
    missing_metadata = REQUIRED_METADATA_COLUMNS - declared_metadata
    if missing_metadata:
        findings.critical.append(
            f"{yaml_path}: metadata_columns missing {sorted(missing_metadata)} — "
            f"DQS SE rules reference these names"
        )
    legacy_metadata = {c for c in declared_metadata if c == "ingested_at"}
    if legacy_metadata:
        findings.warning.append(
            f"{yaml_path}: metadata_columns has legacy {sorted(legacy_metadata)} — "
            f"rename to `_ingested_at` to match SE rules"
        )

    for optional_key in ("retries", "timeout_minutes"):
        if optional_key not in data:
            findings.warning.append(f"{yaml_path}: missing `{optional_key}`")

    contract_ref = data.get("schema_ref")
    if isinstance(contract_ref, str):
        contract_path = project_root / contract_ref
        if not contract_path.exists():
            findings.critical.append(
                f"{yaml_path}: schema_ref `{contract_ref}` does not exist at {contract_path}"
            )

    dq_table = data.get("dq_rules_table", declared_table)
    if isinstance(dq_table, str):
        dq_path = project_root / "dq_rules" / f"{dq_table}.yml"
        if not dq_path.exists():
            findings.critical.append(
                f"{yaml_path}: dq_rules/{dq_table}.yml referenced but missing"
            )
        else:
            check_dq_rules_schema(dq_path, findings)

    return declared_table


def check_dq_rules_schema(dq_path: Path, findings: Findings) -> None:
    """Accept either the legacy stub (`table` + `rules`) or the Spark
    Expectations format sourced from `inputs/dqs/.../se-rules/`
    (`product_id` + `dq_env` + `rules`)."""
    try:
        data = yaml.safe_load(dq_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        findings.critical.append(f"{dq_path}: YAML parse error — {exc}")
        return

    if not isinstance(data, dict):
        findings.critical.append(f"{dq_path}: top-level YAML is not a mapping")
        return

    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        findings.critical.append(f"{dq_path}: `rules` must be a non-empty list")
        return

    is_se_format = "product_id" in data and "dq_env" in data
    is_stub_format = "table" in data
    if not (is_se_format or is_stub_format):
        findings.warning.append(
            f"{dq_path}: unrecognized DQ schema (expected SE `product_id`+`dq_env` "
            f"or legacy `table` at top level)"
        )

    if is_se_format:
        dq_env = data.get("dq_env")
        if not isinstance(dq_env, dict) or not dq_env:
            findings.critical.append(f"{dq_path}: `dq_env` must be a non-empty mapping")
        else:
            for env_name in ("DEV", "PROD"):
                if env_name not in dq_env:
                    findings.warning.append(
                        f"{dq_path}: SE rules missing `dq_env.{env_name}` block"
                    )


def check_pyproject_deps(project_root: Path, findings: Findings) -> None:
    """Assert that pyproject.toml declares the Spark/Delta/SE + Airflow-Spark
    dependencies the generated ingestion code requires at runtime."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        findings.critical.append(f"{pyproject}: pyproject.toml missing")
        return

    text = pyproject.read_text(encoding="utf-8")
    for dep in REQUIRED_RUNTIME_DEPS:
        if not re.search(rf'["\']{re.escape(dep)}[\[<>=!~]', text):
            findings.critical.append(
                f"pyproject.toml: runtime dependency `{dep}` missing — the "
                f"ingestion runner will not import without it"
            )
    for dep in REQUIRED_DEV_DEPS:
        if not re.search(rf'["\']{re.escape(dep)}[\[<>=!~]', text):
            findings.warning.append(
                f"pyproject.toml: dev dependency `{dep}` missing — the Airflow "
                f"factory cannot construct SparkSubmitOperator in tests"
            )


def check_test_modules(project_root: Path, findings: Findings) -> None:
    """Every generated bronze module must have a test module shipped alongside
    it. We check presence (not coverage) to keep this step static and cheap."""
    tests_dir = project_root / "tests" / "bronze"
    if not tests_dir.is_dir():
        findings.critical.append(f"{tests_dir}: tests/bronze directory missing")
        return
    for test_module in REQUIRED_TEST_MODULES:
        test_path = tests_dir / test_module
        if not test_path.exists():
            findings.critical.append(
                f"{test_path}: required test module missing — ingestion code must "
                f"ship with unit tests"
            )


def validate(project_root: Path, lld_path: Path) -> Findings:
    findings = Findings()

    bronze_dir = project_root / "src" / "patient_360" / "bronze"
    configs_dir = project_root / "airflow" / "configs"

    check_pyproject_deps(project_root, findings)
    check_test_modules(project_root, findings)

    for module_name in REQUIRED_MODULES:
        module_path = bronze_dir / module_name
        if not module_path.exists():
            findings.critical.append(f"{module_path}: required module missing")
            continue
        check_module_syntax(module_path, findings)

    if not configs_dir.is_dir():
        findings.critical.append(f"{configs_dir}: airflow/configs directory missing")
        return findings

    yaml_files = sorted(p for p in configs_dir.glob("*.yml") if p.stem != "table_name")
    declared_tables: set[str] = set()
    for yaml_path in yaml_files:
        declared = check_yaml_config(yaml_path, project_root, findings)
        if declared:
            declared_tables.add(declared)

    lld_tables = extract_bronze_tables_from_lld(lld_path)
    missing = lld_tables - declared_tables
    extra = declared_tables - lld_tables

    for table in sorted(missing):
        findings.critical.append(
            f"airflow/configs/{table}.yml: LLD §5.1 lists ingest_{table} but no config exists"
        )
    for table in sorted(extra):
        findings.warning.append(
            f"airflow/configs/{table}.yml: declared in configs but no matching row in LLD §5.1"
        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Path to the patient_360 project root (contains src/, airflow/, contracts/, dq_rules/).",
    )
    parser.add_argument(
        "--lld",
        type=Path,
        required=True,
        help="Path to the approved LLD markdown file.",
    )
    args = parser.parse_args()

    if not args.project_root.is_dir():
        print(f"error: --project-root {args.project_root} is not a directory", file=sys.stderr)
        return 2
    if not args.lld.is_file():
        print(f"error: --lld {args.lld} is not a file", file=sys.stderr)
        return 2

    findings = validate(args.project_root, args.lld)
    print(findings.render())
    return 1 if findings.critical_count() else 0


if __name__ == "__main__":
    sys.exit(main())
