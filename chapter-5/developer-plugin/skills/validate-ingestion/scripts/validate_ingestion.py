#!/usr/bin/env python3
"""Static validator for the Bronze config-driven ingestion framework.

Checks that the runner/factory/wrapper modules exist and parse, that every
Bronze table listed in LLD §5.1 has a matching `airflow/configs/{table}.yml`,
and that each per-table YAML points to real contract and dq_rules files with
the required keys.

The validator is project-agnostic. When run without ``--project-root`` it
auto-discovers the workspace via ``status_rollup.py --mode discover`` and
uses the cookiecutter-style layout: ``src/{project_name}/bronze/`` and
``airflow/configs/``. The fail-on-empty table set is derived from the
per-table YAMLs themselves — any config that declares
``empty_input_behavior: fail`` is added to the critical set.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
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

REQUIRED_METADATA_COLUMNS = {"ds", "_ingested_at", "_source_batch_id"}

LLD_TASK_ROW = re.compile(
    r"`ingest_(?P<table>[a-z_]+)`\s*\|\s*Bronze",
)


def _load_discovery_module() -> object | None:
    """Import ``status_rollup`` from the sibling ``validate-stories`` skill.

    The helper lives at
    ``<plugin-root>/skills/validate-stories/scripts/status_rollup.py`` — this
    validator lives at
    ``<plugin-root>/skills/validate-ingestion/scripts/validate_ingestion.py``.
    Compute the path relatively so the import works regardless of where the
    plugin is installed.
    """
    here = Path(__file__).resolve()
    helper = here.parent.parent.parent / "validate-stories" / "scripts" / "status_rollup.py"
    if not helper.exists():
        return None
    module_name = "_rdewai_status_rollup"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, helper)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        return None
    return module


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


def derive_project_name(project_root: Path) -> str:
    """Resolve the importable package name from the cookiecutter ``src/<name>/``.

    Folder name is authoritative: pyproject ``project.name`` may use hyphens
    (``sample-mart``) while the importable folder uses underscores
    (``sample_mart``). The ingestion code imports by folder name, so we use
    that.
    """
    src = project_root / "src"
    if not src.is_dir():
        raise FileNotFoundError(
            f"{project_root}: src/ directory missing — not a cookiecutter project root"
        )
    pkgs = [p for p in sorted(src.iterdir()) if p.is_dir() and not p.name.startswith(".")]
    if not pkgs:
        raise FileNotFoundError(f"{src}: no package directories found")
    # Prefer the package whose name matches the project folder (cookiecutter default).
    matching = [p for p in pkgs if p.name == project_root.name]
    return (matching[0] if matching else pkgs[0]).name


def derive_fail_on_empty_tables(configs_dir: Path) -> set[str]:
    """Tables whose per-table YAML declares ``empty_input_behavior: fail``.

    Parsed before the per-table validation runs so we can cross-reference
    when a table's declared behavior is missing or drifts from the filename.
    """
    critical: set[str] = set()
    if not configs_dir.is_dir():
        return critical
    for yaml_path in sorted(configs_dir.glob("*.yml")):
        if yaml_path.stem == "table_name" or yaml_path.stem.startswith("_"):
            continue
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("empty_input_behavior", "")).strip().lower() == "fail":
            table = str(data.get("table", yaml_path.stem)).strip().lower()
            critical.add(table)
    return critical


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
        findings.critical.append(f"{module_path}: absolute filesystem path literal {literal!r}")


def check_yaml_config(
    yaml_path: Path,
    project_root: Path,
    fail_on_empty_tables: set[str],
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
    if declared_table in fail_on_empty_tables and behavior != "fail":
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
            findings.critical.append(f"{yaml_path}: dq_rules/{dq_table}.yml referenced but missing")
        else:
            check_dq_rules_schema(dq_path, findings)

    return declared_table


def check_dq_rules_schema(dq_path: Path, findings: Findings) -> None:
    """Accept either the legacy stub (`table` + `rules`) or the Spark
    Expectations format sourced from `outputs/dqs/.../se-rules/`
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


def check_contract_config(
    contract_path: Path,
    project_root: Path,
    findings: Findings,
) -> None:
    """Validate a single ``contracts/{table}.yml``.

    Cross-checks the pointers declared in the contract (``ddl_path``,
    ``dq_path``) against files actually present on disk, and flags runtime
    metadata columns that have leaked into the business schema declaration.
    Per LLD §2.3 the contract is the authoritative *business* schema —
    runtime metadata (``ds``, ``_ingested_at``, ``_source_batch_id``) is
    added by the ingestion runner and must not be declared here.
    """
    try:
        data = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        findings.critical.append(f"{contract_path}: YAML parse error — {exc}")
        return

    if not isinstance(data, dict):
        findings.critical.append(f"{contract_path}: top-level YAML is not a mapping")
        return

    for pointer_key in ("ddl_path", "dq_path"):
        pointer = data.get(pointer_key)
        if not isinstance(pointer, str) or not pointer:
            findings.critical.append(f"{contract_path}: `{pointer_key}` missing or not a string")
            continue
        target = project_root / pointer
        if not target.exists():
            findings.critical.append(
                f"{contract_path}: {pointer_key} `{pointer}` does not exist (resolved to {target})"
            )

    raw_columns = data.get("columns")
    if isinstance(raw_columns, list):
        columns = raw_columns
    else:
        nested = data.get("schema")
        nested_cols = nested.get("columns") if isinstance(nested, dict) else None
        columns = nested_cols if isinstance(nested_cols, list) else []
    declared_names = {
        col.get("name") for col in columns if isinstance(col, dict) and col.get("name")
    }
    leaked = REQUIRED_METADATA_COLUMNS & declared_names
    for col in sorted(leaked):
        findings.warning.append(
            f"{contract_path}: schema.columns lists runtime metadata column "
            f"`{col}` — metadata is added by ingestion_runner and must not be "
            f"declared in the business contract (LLD §2.3)"
        )


def _soft_import_regex(project_name: str) -> re.Pattern[str]:
    return re.compile(
        r"try:\s*\n"
        rf"\s*from\s+{re.escape(project_name)}\.utils\s+import\s+se_runner[^\n]*\n"
        r"(?:\s*[^\n]*\n){0,6}?"
        r"\s*except\s+ImportError",
    )


def check_soft_import_removed(
    project_root: Path,
    project_name: str,
    findings: Findings,
) -> None:
    """Enforce LLD §8.5 — once ``se_runner.py`` ships the soft-import
    ``try/except ImportError`` bootstrap block in ``ingestion_runner.py``
    MUST be removed. Ingestion must fail closed if SE is unavailable post
    implementation; a missing import is a deployment error, not a graceful
    degradation.
    """
    runner_path = project_root / "src" / project_name / "bronze" / "ingestion_runner.py"
    if not runner_path.exists():
        # Missing runner is already flagged by check_module_syntax upstream.
        return

    source = runner_path.read_text(encoding="utf-8")
    has_soft_import = bool(_soft_import_regex(project_name).search(source))
    if not has_soft_import:
        return

    se_runner_path = project_root / "src" / project_name / "utils" / "se_runner.py"
    if se_runner_path.exists():
        findings.critical.append(
            f"{runner_path}: soft-import bootstrap `try/except ImportError` "
            f"around `se_runner` must be removed — `se_runner.py` is shipped, "
            f"ingestion must fail closed (LLD §8.5)"
        )
    else:
        findings.info.append(
            f"{runner_path}: soft-import bootstrap present; se_runner.py not "
            f"yet implemented (expected during bootstrap mode, LLD §8.5)"
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
    it. We check presence (not coverage) to keep this step static and cheap.

    Accepts either ``test_<name>.py`` or ``test_<name>_unit.py`` — both are
    in active use across the codebase. We match by stem prefix so a project
    can pick either convention without tripping the validator.
    """
    tests_dir = project_root / "tests" / "bronze"
    if not tests_dir.is_dir():
        findings.critical.append(f"{tests_dir}: tests/bronze directory missing")
        return
    present_stems = {p.stem for p in tests_dir.glob("test_*.py")}
    for test_module in REQUIRED_TEST_MODULES:
        base = Path(test_module).stem  # e.g. "test_ingestion_runner"
        if base in present_stems or f"{base}_unit" in present_stems:
            continue
        findings.critical.append(
            f"{tests_dir / test_module}: required test module missing — "
            f"ingestion code must ship with unit tests "
            f"(also accepted: {base}_unit.py)"
        )


def resolve_lld_path(workspace_root: Path) -> Path | None:
    """Find the latest LLD markdown under ``{workspace_root}/outputs/lld/v*/``.

    Prefers a file named ``LLD-*.md`` in the highest-numbered ``v*/`` directory.
    Returns ``None`` when no LLD is found — the caller decides whether that is
    fatal.
    """
    lld_root = workspace_root / "outputs" / "lld"
    if not lld_root.is_dir():
        return None
    versions = sorted(
        (p for p in lld_root.glob("v*") if p.is_dir()),
        key=lambda p: p.name,
    )
    for v in reversed(versions):
        matches = sorted(v.glob("LLD-*.md")) or sorted(v.glob("*.md"))
        if matches:
            return matches[0]
    return None


def validate(project_root: Path, project_name: str, lld_path: Path) -> Findings:
    findings = Findings()

    bronze_dir = project_root / "src" / project_name / "bronze"
    configs_dir = project_root / "airflow" / "configs"

    fail_on_empty_tables = derive_fail_on_empty_tables(configs_dir)

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

    yaml_files = sorted(
        p
        for p in configs_dir.glob("*.yml")
        if p.stem != "table_name" and not p.stem.startswith("_")
    )
    declared_tables: set[str] = set()
    for yaml_path in yaml_files:
        declared = check_yaml_config(yaml_path, project_root, fail_on_empty_tables, findings)
        if declared:
            declared_tables.add(declared)
            if declared == "table_name" or declared.startswith("_"):
                continue
            contract_path = project_root / "contracts" / f"{declared}.yml"
            if contract_path.exists():
                check_contract_config(contract_path, project_root, findings)

    check_soft_import_removed(project_root, project_name, findings)

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
        help=(
            "Path to the cookiecutter project root (contains src/, airflow/, "
            "contracts/, dq_rules/). Defaults to workspace auto-discovery."
        ),
    )
    parser.add_argument(
        "--project-name",
        help=(
            "Importable package name under src/<name>/. Defaults to the "
            "folder name discovered inside --project-root/src/."
        ),
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Override the workspace root used for discovery.",
    )
    parser.add_argument(
        "--lld",
        type=Path,
        help=(
            "Path to the approved LLD markdown. Defaults to the latest "
            "LLD-*.md under {workspace_root}/outputs/lld/v*/."
        ),
    )
    args = parser.parse_args()

    project_root = args.project_root
    project_name = args.project_name
    lld_path = args.lld

    need_discovery = project_root is None or lld_path is None or args.workspace_root is not None
    workspace_root: Path | None = args.workspace_root

    if need_discovery:
        rollup = _load_discovery_module()
        if rollup is None:
            print(
                "error: could not locate status_rollup.py for workspace discovery; "
                "pass --project-root and --lld explicitly",
                file=sys.stderr,
            )
            return 2
        try:
            ws = rollup.discover_workspace(
                start=Path.cwd(),
                workspace_root_override=args.workspace_root,
                project_name_override=args.project_name,
            )
        except Exception as exc:  # DiscoveryError + any I/O failure
            print(f"error: workspace discovery failed — {exc}", file=sys.stderr)
            return 2
        workspace_root = ws.workspace_root
        if project_root is None:
            project_root = ws.project_root
        if project_name is None:
            project_name = ws.project_name

    if project_root is None:
        print("error: --project-root is required when discovery is disabled", file=sys.stderr)
        return 2
    if not project_root.is_dir():
        print(f"error: --project-root {project_root} is not a directory", file=sys.stderr)
        return 2

    if project_name is None:
        try:
            project_name = derive_project_name(project_root)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if lld_path is None:
        if workspace_root is None:
            print(
                "error: --lld is required (could not infer a workspace root to search)",
                file=sys.stderr,
            )
            return 2
        lld_path = resolve_lld_path(workspace_root)
        if lld_path is None:
            print(
                f"error: no LLD markdown found under {workspace_root}/outputs/lld/v*/ "
                f"— pass --lld explicitly",
                file=sys.stderr,
            )
            return 2

    if not lld_path.is_file():
        print(f"error: --lld {lld_path} is not a file", file=sys.stderr)
        return 2

    findings = validate(project_root, project_name, lld_path)
    print(findings.render())
    return 1 if findings.critical_count() else 0


if __name__ == "__main__":
    sys.exit(main())
