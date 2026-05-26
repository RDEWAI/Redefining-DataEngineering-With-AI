"""Validate the Silver layer implementation against the latest approved LLD.

Implements rules R1..R27 from
``chapter-6/developer-plugin/skills/validate-silver/SKILL.md``.

Usage:
    python validate_silver.py --project-root patient_360/
    python validate_silver.py --all <project-roots-glob>
    python validate_silver.py --project-root patient_360/ --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

# Allow running as a standalone script from any CWD
_HERE = Path(__file__).resolve().parent
# skills/validate-silver/scripts/ -> skills/validate-silver/ -> skills/ -> developer-plugin/
_PLUGIN_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))

from silver_gold_utils import (  # noqa: E402
    Findings,
    call_kwargs,
    extract_dms_columns,
    extract_dms_hash_columns,
    extract_lld_silver_tasks,
    extract_metadata_status,
    find_calls,
    first_line,
    imports_name,
    latest_artifact_file,
    latest_version_dir,
    list_literal,
    load_yaml,
    module_docstring,
    parse_python,
    uses_name,
    yaml_byte_diff,
)

SCD2_TABLES = {
    "clinical_patients",
    "reference_organizations",
    "reference_providers",
    "reference_payers",
}
SCD2_MANDATED_COLS = {
    "surrogate_key",
    "natural_key",
    "effective_date",
    "expiry_date",
    "is_current",
    "record_hash",
    "dw_created_at",
    "dw_updated_at",
}


def find_upstream_root(start: Path) -> Path | None:
    """Walk up from start to find chapter-4 sibling directory."""
    here = start.resolve()
    for cand in (here, *here.parents):
        sib = cand.parent / "chapter-4"
        if sib.is_dir() and (sib / "outputs").is_dir():
            return sib
    return None


# ---------------------------------------------------------------------------
# Per-rule checks
# ---------------------------------------------------------------------------


def check_presence(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """R1..R5: every Silver task row must have its 5 files."""
    for task in tasks:
        table = task["module_table"]
        silver_table = _silver_table_name(task)
        files = {
            "R1": project_root / "src/patient_360/silver" / f"transform_{table}.py",
            "R2": project_root / "contracts" / f"{silver_table}.yml",
            "R3": project_root / "contracts" / "dq" / f"{silver_table}.yml",
            "R4": project_root / "dq_rules" / f"{silver_table}.yml",
            "R5": project_root / "tests/silver" / f"test_transform_{table}_unit.py",
        }
        for rule, path in files.items():
            if not path.is_file():
                findings.add(
                    "CRITICAL",
                    rule,
                    f"{path.relative_to(project_root)} missing for table '{table}'",
                )

    # Orphan modules: present in src/ but not in LLD §5.2
    expected = {t["module_table"] for t in tasks if t["module_table"]}
    silver_dir = project_root / "src/patient_360/silver"
    if silver_dir.is_dir():
        for mod in silver_dir.glob("transform_*.py"):
            name = mod.stem.replace("transform_", "")
            if name not in expected:
                findings.add(
                    "WARNING",
                    "R-ORPHAN",
                    f"Module {mod.relative_to(project_root)} not declared in LLD §5.2",
                )


def check_schema_alignment(
    project_root: Path, tasks: list[dict], dms_path: Path | None, findings: Findings
) -> None:
    """R6..R8: contract column set matches DMS §3."""
    if dms_path is None:
        findings.add("INFO", "R6", "DMS not available; skipping schema alignment")
        return
    for task in tasks:
        silver_table = _silver_table_name(task)
        contract_path = project_root / "contracts" / f"{silver_table}.yml"
        contract = load_yaml(contract_path)
        if not isinstance(contract, dict):
            continue  # already flagged by R2
        contract_cols = {
            col["name"]
            for col in (contract.get("schema") or [])
            if isinstance(col, dict) and "name" in col
        }
        dms_cols = set(extract_dms_columns(dms_path, silver_table))
        if not dms_cols:
            findings.add(
                "INFO", "R6", f"DMS §3 column list not found for '{silver_table}'; skipping"
            )
            continue
        missing = dms_cols - contract_cols
        extra = contract_cols - dms_cols
        if missing:
            findings.add(
                "CRITICAL",
                "R6",
                f"{silver_table}: contract missing DMS columns {sorted(missing)}",
            )
        if extra:
            findings.add(
                "WARNING",
                "R6",
                f"{silver_table}: contract has columns not in DMS §3 {sorted(extra)}",
            )
        # R7: SCD2 mandated columns
        if silver_table in SCD2_TABLES:
            scd2_missing = SCD2_MANDATED_COLS - contract_cols
            if scd2_missing:
                findings.add(
                    "WARNING",
                    "R7",
                    f"{silver_table} (SCD2): missing mandated columns {sorted(scd2_missing)}",
                )
        # R8: tags present
        if not contract.get("tags"):
            findings.add("INFO", "R8", f"{silver_table}: contract has no 'tags' field")


def check_scd2_wiring(
    project_root: Path, tasks: list[dict], dms_path: Path | None, findings: Findings
) -> None:
    """R9..R14: SCD2 dim modules wire apply_scd2 correctly."""
    for task in tasks:
        silver_table = _silver_table_name(task)
        if silver_table not in SCD2_TABLES:
            continue
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/silver" / f"transform_{table}.py"
        tree = parse_python(mod_path)
        if tree is None:
            continue  # already flagged by R1

        if not imports_name(tree, "patient_360.utils.scd2.apply_scd2"):
            findings.add("CRITICAL", "R9", f"{table}: missing import of apply_scd2")

        scd2_calls = find_calls(tree, "apply_scd2")
        if not scd2_calls:
            findings.add("CRITICAL", "R10", f"{table}: no apply_scd2(...) invocation found")
            continue
        # R10: kwargs cover target_path + natural_keys + hash_columns + effective_date
        for call in scd2_calls:
            kw = call_kwargs(call)
            required = {"target_path", "natural_keys", "hash_columns", "effective_date"}
            missing_kw = required - set(kw.keys())
            # If passed positionally, allow with a WARNING note
            if missing_kw and len(call.args) >= 5:
                findings.add(
                    "INFO",
                    "R10",
                    f"{table}: apply_scd2 called positionally — kwargs preferred",
                )
            elif missing_kw:
                findings.add(
                    "CRITICAL",
                    "R10",
                    f"{table}: apply_scd2 missing keyword args {sorted(missing_kw)}",
                )

            # R11: hash_columns list literal matches DMS §6
            if dms_path is not None and "hash_columns" in kw:
                lit = list_literal(kw["hash_columns"])
                dms_hash = extract_dms_hash_columns(dms_path, silver_table)
                if lit is not None and dms_hash and set(lit) != set(dms_hash):
                    findings.add(
                        "CRITICAL",
                        "R11",
                        f"{table}: apply_scd2 hash_columns {sorted(lit)} "
                        f"!= DMS §6 {sorted(dms_hash)}",
                    )

        # R12: SCD2 module must NOT call write_silver_delta
        if find_calls(tree, "write_silver_delta"):
            findings.add(
                "CRITICAL",
                "R12",
                f"{table}: SCD2 module also calls write_silver_delta (mutually exclusive)",
            )

        # R13: apply_scd2 line > run_dq line (DQ before write)
        run_dq_calls = find_calls(tree, "run_dq")
        if run_dq_calls and scd2_calls:
            run_dq_line = min(first_line(c) for c in run_dq_calls)
            scd2_line = min(first_line(c) for c in scd2_calls)
            if run_dq_line > scd2_line:
                findings.add(
                    "CRITICAL",
                    "R13",
                    f"{table}: apply_scd2 invoked before run_dq (DQ must precede write)",
                )

        # R14: never call monotonically_increasing_id. Upgraded to CRITICAL
        # to match the SKILL.md — IL-006 is an idempotency-breaking violation,
        # not stylistic noise. Non-deterministic across executors and re-runs.
        if uses_name(tree, "monotonically_increasing_id"):
            findings.add(
                "CRITICAL",
                "R14",
                f"{table}: uses monotonically_increasing_id (non-deterministic; see IL-006). "
                "Use xxhash64(natural_key, effective_date) or max(surrogate_key)+row_number().",
            )


def check_dq_gate(
    project_root: Path,
    tasks: list[dict],
    upstream_root: Path | None,
    findings: Findings,
) -> None:
    """R15..R19: every Silver module gates with run_dq before write."""
    upstream_dqs_dir = None
    if upstream_root is not None:
        dqs_version = latest_version_dir(upstream_root, "dqs")
        if dqs_version is not None:
            upstream_dqs_dir = dqs_version / "se-rules"

    for task in tasks:
        silver_table = _silver_table_name(task)
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/silver" / f"transform_{table}.py"
        tree = parse_python(mod_path)
        if tree is None:
            continue

        run_dq_calls = find_calls(tree, "run_dq")
        if not run_dq_calls:
            findings.add("CRITICAL", "R15", f"{table}: run_dq is not called")
            continue

        # R16: action_if_failed kwarg present
        for call in run_dq_calls:
            kw = call_kwargs(call)
            if "action_if_failed" not in kw:
                findings.add(
                    "CRITICAL",
                    "R16",
                    f"{table}: run_dq missing action_if_failed kwarg",
                )

        # R17: run_dq line < write_silver_delta line (when present)
        write_calls = find_calls(tree, "write_silver_delta")
        if write_calls:
            run_dq_line = min(first_line(c) for c in run_dq_calls)
            write_line = min(first_line(c) for c in write_calls)
            if run_dq_line >= write_line:
                findings.add(
                    "CRITICAL",
                    "R17",
                    f"{table}: run_dq must precede write_silver_delta",
                )

        # R18: dq_rules file matches upstream DQS se-rules
        if upstream_dqs_dir is not None:
            local_yml = project_root / "dq_rules" / f"{silver_table}.yml"
            upstream_yml = upstream_dqs_dir / f"{silver_table}.yaml"
            if upstream_yml.exists() and yaml_byte_diff(local_yml, upstream_yml):
                findings.add(
                    "WARNING",
                    "R18",
                    f"{silver_table}: dq_rules diverged from upstream DQS se-rules",
                )

        # R19: se.with_expectations(...) wraps a no-arg lambda
        _check_se_lambda_wrap(table, tree, findings)


def _check_se_lambda_wrap(table: str, tree: ast.AST, findings: Findings) -> None:
    """R19: ``se.with_expectations(...)`` must wrap its argument in ``lambda: df``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        # Looking for `se.with_expectations(...)(...)` shape — outer call of an inner call
        if (
            isinstance(fn, ast.Call)
            and isinstance(fn.func, ast.Attribute)
            and fn.func.attr == "with_expectations"
        ):
            if not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Lambda) and not arg.args.args):
                findings.add(
                    "CRITICAL",
                    "R19",
                    f"{table}: se.with_expectations(...)(...) inner arg "
                    "must be a no-arg lambda (IL-007)",
                )


def check_dag_wiring(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """R20..R24: airflow DAG wires silver_dimensions / silver_facts correctly."""
    dag_path = project_root / "airflow/dags/patient360_hourly_v1.py"
    if not dag_path.is_file():
        findings.add("CRITICAL", "R20", f"DAG file missing: {dag_path.relative_to(project_root)}")
        return
    tree = parse_python(dag_path)
    if tree is None:
        findings.add("CRITICAL", "R20", "DAG file has syntax errors")
        return

    # Collect TaskGroup constructions by group_id
    group_tasks: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "TaskGroup"
        ):
            kw = call_kwargs(node)
            gid = kw.get("group_id")
            if isinstance(gid, ast.Constant) and isinstance(gid.value, str):
                group_tasks.setdefault(gid.value, set())

    # Find task_id assignments inside SparkSubmitOperator calls
    operator_count = 0
    python_op_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "SparkSubmitOperator":
                operator_count += 1
            elif node.func.id == "PythonOperator":
                python_op_count += 1

    # Quick coverage check: expected task IDs vs actual task_id literals anywhere in file
    src = dag_path.read_text(encoding="utf-8")
    expected_silver_dim_tasks = {
        f"transform_{t['module_table']}_silver"
        for t in tasks
        if _silver_table_name(t) in SCD2_TABLES
    }
    expected_silver_fact_tasks = {
        f"transform_{t['module_table']}_silver"
        for t in tasks
        if _silver_table_name(t) not in SCD2_TABLES
    }

    missing_dim = {tid for tid in expected_silver_dim_tasks if tid not in src}
    missing_fact = {tid for tid in expected_silver_fact_tasks if tid not in src}
    if missing_dim:
        findings.add("CRITICAL", "R20", f"DAG missing SCD2 dim tasks: {sorted(missing_dim)}")
    if missing_fact:
        findings.add("CRITICAL", "R21", f"DAG missing Silver fact tasks: {sorted(missing_fact)}")

    # R22: dependency edge keywords present in source
    if not all(
        s in src
        for s in [
            "reconciliation_bronze",
            "silver_dimensions",
            "silver_facts",
            "reconciliation_silver",
        ]
    ):
        findings.add(
            "CRITICAL",
            "R22",
            "DAG missing one of: reconciliation_bronze, silver_dimensions, "
            "silver_facts, reconciliation_silver",
        )

    # R23: no PythonOperator allowed for Spark-touching tasks
    # (best-effort: any PythonOperator triggers)
    if python_op_count > 0:
        findings.add(
            "CRITICAL",
            "R23",
            f"DAG declares {python_op_count} PythonOperator(s); "
            "Spark tasks must use SparkSubmitOperator (IL-011)",
        )

    if operator_count == 0:
        findings.add(
            "CRITICAL",
            "R23",
            "DAG declares zero SparkSubmitOperator tasks",
        )


def check_traceability(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """R25..R27: docstrings cite LLD/STM/DMS/DQS; contract paths resolve."""
    for task in tasks:
        silver_table = _silver_table_name(task)
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/silver" / f"transform_{table}.py"
        tree = parse_python(mod_path)
        if tree is not None:
            doc = module_docstring(tree) or ""
            for needle, rule_id in (
                ("LLD: §5.2", "R25"),
                ("STM:", "R25"),
                ("DMS:", "R25"),
                ("DQS:", "R25"),
            ):
                if needle not in doc:
                    findings.add("WARNING", rule_id, f"{table}: docstring missing '{needle}'")
                    break

        # R26, R27: contract path pointers resolve
        contract_path = project_root / "contracts" / f"{silver_table}.yml"
        contract = load_yaml(contract_path)
        if isinstance(contract, dict):
            ddl_path = contract.get("ddl_path")
            dq_path = contract.get("dq_path")
            if isinstance(ddl_path, str) and not (project_root / ddl_path).is_file():
                findings.add(
                    "INFO", "R26", f"{silver_table}: ddl_path -> {ddl_path} does not exist"
                )
            if isinstance(dq_path, str) and not (project_root / dq_path).is_file():
                findings.add("INFO", "R27", f"{silver_table}: dq_path -> {dq_path} does not exist")


def _silver_table_name(task: dict) -> str:
    """Resolve the silver-table name from the LLD task row (contract column)."""
    # contracts/<silver_table>.yml — strip leading "contracts/" and ".yml"
    contract = task.get("contract_path", "").replace("`", "").strip()
    if contract.startswith("contracts/"):
        contract = contract[len("contracts/") :]
    if contract.endswith(".yml"):
        contract = contract[: -len(".yml")]
    return contract


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def validate_project(project_root: Path) -> Findings:
    findings = Findings()
    upstream_root = find_upstream_root(project_root)

    lld_path = None
    dms_path = None
    if upstream_root is not None:
        lld_ver = latest_version_dir(upstream_root, "lld")
        dms_ver = latest_version_dir(upstream_root, "dms")
        if lld_ver:
            lld_path = latest_artifact_file(lld_ver, "LLD")
        if dms_ver:
            dms_path = latest_artifact_file(dms_ver, "DMS")

    if lld_path is None:
        findings.add(
            "CRITICAL", "PRE", "Could not locate latest LLD under chapter-4/outputs/lld/v*/"
        )
        return findings

    # Phase 0: approval gate is INFO-only here
    status = extract_metadata_status(lld_path)
    if status and status.lower() != "approved":
        findings.add(
            "INFO", "PRE", f"LLD status is '{status}' (not Approved) — findings advisory only"
        )

    tasks = extract_lld_silver_tasks(lld_path)
    if not tasks:
        findings.add("CRITICAL", "PRE", "No Silver task rows parsed from LLD §5.2")
        return findings

    check_presence(project_root, tasks, findings)
    check_schema_alignment(project_root, tasks, dms_path, findings)
    check_scd2_wiring(project_root, tasks, dms_path, findings)
    check_dq_gate(project_root, tasks, upstream_root, findings)
    check_dag_wiring(project_root, tasks, findings)
    check_traceability(project_root, tasks, findings)

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, help="Path to patient_360/ project root")
    parser.add_argument("--all", type=Path, help="Glob of project roots (for CI)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.project_root:
        targets.append(args.project_root.resolve())
    if args.all:
        for p in Path(args.all).glob("patient_360"):
            if p.is_dir():
                targets.append(p.resolve())
    if not targets:
        parser.error("Provide --project-root or --all")

    exit_code = 0
    aggregated: dict[str, dict] = {}
    for target in targets:
        findings = validate_project(target)
        label = str(target)
        if args.format == "json":
            aggregated[label] = findings.to_json()
        else:
            print(findings.render(project_label=label))
            print()
        if findings.critical_count():
            exit_code = 1
    if args.format == "json":
        print(json.dumps(aggregated, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
