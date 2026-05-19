"""Validate the Gold layer implementation against the latest approved LLD.

Implements rules G1..G22 from
``chapter-6/developer-plugin/skills/validate-gold/SKILL.md``.

Usage:
    python validate_gold.py --project-root patient_360/
    python validate_gold.py --all <project-roots-glob>
    python validate_gold.py --project-root patient_360/ --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# skills/validate-gold/scripts/ -> skills/validate-gold/ -> skills/ -> developer-plugin/
_PLUGIN_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))

from silver_gold_utils import (  # noqa: E402
    Findings,
    call_kwargs,
    extract_dms_columns,
    extract_lld_gold_tasks,
    extract_metadata_status,
    find_calls,
    first_line,
    imports_name,
    latest_artifact_file,
    latest_version_dir,
    load_yaml,
    module_docstring,
    parse_python,
    yaml_byte_diff,
)

SCD2_TABLES = {
    "clinical_patients",
    "reference_organizations",
    "reference_providers",
    "reference_payers",
}


def find_upstream_root(start: Path) -> Path | None:
    here = start.resolve()
    for cand in (here, *here.parents):
        sib = cand.parent / "chapter-4"
        if sib.is_dir() and (sib / "outputs").is_dir():
            return sib
    return None


# ---------------------------------------------------------------------------


def _gold_table_name(task: dict) -> str:
    contract = task.get("contract_path", "").replace("`", "").strip()
    if contract.startswith("contracts/"):
        contract = contract[len("contracts/"):]
    if contract.endswith(".yml"):
        contract = contract[: -len(".yml")]
    return contract


def check_presence(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    for task in tasks:
        table = task["module_table"]
        gold_table = _gold_table_name(task)
        files = {
            "G1": project_root / "src/patient_360/gold" / f"build_{table}.py",
            "G2": project_root / "contracts" / f"{gold_table}.yml",
            "G3": project_root / "contracts" / "dq" / f"{gold_table}.yml",
            "G4": project_root / "dq_rules" / f"{gold_table}.yml",
            "G5": project_root / "tests/gold" / f"test_build_{table}_unit.py",
        }
        for rule, path in files.items():
            if not path.is_file():
                findings.add("CRITICAL", rule, f"{path.relative_to(project_root)} missing for table '{table}'")

    expected = {t["module_table"] for t in tasks if t["module_table"]}
    gold_dir = project_root / "src/patient_360/gold"
    if gold_dir.is_dir():
        for mod in gold_dir.glob("build_*.py"):
            name = mod.stem.replace("build_", "")
            if name not in expected:
                findings.add(
                    "WARNING",
                    "G-ORPHAN",
                    f"Module {mod.relative_to(project_root)} not declared in LLD §5.3",
                )


def check_schema_alignment(
    project_root: Path, tasks: list[dict], dms_path: Path | None, findings: Findings
) -> None:
    if dms_path is None:
        findings.add("INFO", "G6", "DMS not available; skipping schema alignment")
        return
    for task in tasks:
        gold_table = _gold_table_name(task)
        contract = load_yaml(project_root / "contracts" / f"{gold_table}.yml")
        if not isinstance(contract, dict):
            continue
        contract_cols = {col["name"] for col in (contract.get("schema") or []) if isinstance(col, dict) and "name" in col}
        dms_cols = set(extract_dms_columns(dms_path, gold_table))
        if not dms_cols:
            findings.add("INFO", "G6", f"DMS §4 column list not found for '{gold_table}'; skipping")
            continue
        missing = dms_cols - contract_cols
        extra = contract_cols - dms_cols
        if missing:
            findings.add("CRITICAL", "G6", f"{gold_table}: contract missing DMS columns {sorted(missing)}")
        if extra:
            findings.add("WARNING", "G6", f"{gold_table}: contract has columns not in DMS §4 {sorted(extra)}")
        if not contract.get("tags"):
            findings.add("INFO", "G7", f"{gold_table}: contract has no 'tags' field")


def check_scd2_read_pattern(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """G8..G10: every SCD2 dim read MUST filter is_current=True; no apply_scd2 import."""
    for task in tasks:
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/gold" / f"build_{table}.py"
        tree = parse_python(mod_path)
        if tree is None:
            continue

        # G10: must NOT import apply_scd2
        if imports_name(tree, "patient_360.utils.scd2.apply_scd2"):
            findings.add(
                "CRITICAL",
                "G10",
                f"{table}: Gold builder imports apply_scd2 — Gold never performs SCD2 writes",
            )

        # G8/G9: every read_silver_delta(table=<scd2_table>) must be followed by .filter(F.col("is_current") == True)
        # Heuristic — find each read_silver_delta call and its parent .filter() Attribute
        src = mod_path.read_text(encoding="utf-8")
        for scd2 in SCD2_TABLES:
            # Look for `read_silver_delta(spark, table="<scd2>"` pattern in source text
            if f'table="{scd2}"' not in src and f"table='{scd2}'" not in src:
                continue
            # Now look for is_current filter near the read
            if 'is_current' not in src:
                findings.add(
                    "CRITICAL",
                    "G8",
                    f"{table}: reads SCD2 '{scd2}' but no is_current filter detected",
                )
                continue
            # G9: ensure the form is `F.col("is_current") == True` (heuristic)
            if 'F.col("is_current") == True' not in src and "F.col('is_current') == True" not in src:
                findings.add(
                    "WARNING",
                    "G9",
                    f"{table}: SCD2 '{scd2}' is_current filter present but not in F.col(...) == True form",
                )


def check_dq_gate(
    project_root: Path,
    tasks: list[dict],
    upstream_root: Path | None,
    findings: Findings,
) -> None:
    """G11..G15: every Gold builder gates with run_dq before write; default fail."""
    upstream_dqs_dir = None
    if upstream_root is not None:
        dqs_version = latest_version_dir(upstream_root, "dqs")
        if dqs_version is not None:
            upstream_dqs_dir = dqs_version / "se-rules"

    for task in tasks:
        gold_table = _gold_table_name(task)
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/gold" / f"build_{table}.py"
        tree = parse_python(mod_path)
        if tree is None:
            continue

        run_dq_calls = find_calls(tree, "run_dq")
        if not run_dq_calls:
            findings.add("CRITICAL", "G11", f"{table}: run_dq not called")
            continue

        # G12: action_if_failed="fail" (table-level default)
        for call in run_dq_calls:
            kw = call_kwargs(call)
            action = kw.get("action_if_failed")
            if isinstance(action, ast.Constant) and isinstance(action.value, str):
                if action.value != "fail":
                    findings.add(
                        "CRITICAL",
                        "G12",
                        f"{table}: run_dq action_if_failed='{action.value}' (Gold default must be 'fail')",
                    )
            elif "action_if_failed" not in kw:
                findings.add("CRITICAL", "G12", f"{table}: run_dq missing action_if_failed kwarg")

        # G13: run_dq before write_gold_delta
        write_calls = find_calls(tree, "write_gold_delta")
        if write_calls:
            if min(first_line(c) for c in run_dq_calls) >= min(first_line(c) for c in write_calls):
                findings.add(
                    "CRITICAL",
                    "G13",
                    f"{table}: run_dq must precede write_gold_delta",
                )

        # G14: dq_rules matches upstream
        if upstream_dqs_dir is not None:
            local_yml = project_root / "dq_rules" / f"{gold_table}.yml"
            upstream_yml = upstream_dqs_dir / f"{gold_table}.yaml"
            if upstream_yml.exists() and yaml_byte_diff(local_yml, upstream_yml):
                findings.add(
                    "WARNING",
                    "G14",
                    f"{gold_table}: dq_rules diverged from upstream DQS se-rules",
                )

        # G15: SE with_expectations lambda wrap
        _check_se_lambda_wrap(table, tree, findings)


def _check_se_lambda_wrap(table: str, tree: ast.AST, findings: Findings) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Call) and isinstance(fn.func, ast.Attribute) and fn.func.attr == "with_expectations":
            if not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Lambda) and not arg.args.args):
                findings.add(
                    "CRITICAL",
                    "G15",
                    f"{table}: se.with_expectations(...)(...) inner arg must be a no-arg lambda (IL-007)",
                )


def check_join_correctness(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """G16..G17: builder reads every LLD §5.3 Input and joins them.

    The STM Silver-to-Gold sheet lives in an .xlsx (not parsed here); we
    enforce the lighter LLD Inputs check and flag missing reads.
    """
    for task in tasks:
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/gold" / f"build_{table}.py"
        if not mod_path.is_file():
            continue
        src = mod_path.read_text(encoding="utf-8")

        # G17: every input named in LLD §5.3 Inputs column appears as a read_silver_delta call
        # task["inputs"] is a comma-separated list of backticked silver table names
        raw_inputs = task.get("inputs", "")
        # Extract `name` tokens in backticks
        import re

        input_tables = re.findall(r"`([^`]+)`", raw_inputs)
        for it in input_tables:
            base = it.split()[0]
            if base and base not in src:
                findings.add(
                    "WARNING",
                    "G17",
                    f"{table}: LLD §5.3 input '{base}' not read in builder",
                )

        # G16 is STM-driven and best-effort here: count .join() calls and note if zero
        tree = parse_python(mod_path)
        if tree is not None and not find_calls(tree, "join"):
            findings.add(
                "WARNING",
                "G16",
                f"{table}: no .join() calls detected; verify against STM Silver-to-Gold sheet",
            )


def check_dag_wiring(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """G18..G20."""
    dag_path = project_root / "airflow/dags/patient360_hourly_v1.py"
    if not dag_path.is_file():
        findings.add("CRITICAL", "G18", f"DAG file missing: {dag_path.relative_to(project_root)}")
        return
    src = dag_path.read_text(encoding="utf-8")
    tree = parse_python(dag_path)
    if tree is None:
        findings.add("CRITICAL", "G18", "DAG file has syntax errors")
        return

    expected_tasks = {t["task_id"] for t in tasks if t["task_id"]}
    missing = {tid for tid in expected_tasks if tid not in src}
    if missing:
        findings.add("CRITICAL", "G18", f"DAG missing Gold tasks: {sorted(missing)}")

    if not all(s in src for s in ["reconciliation_silver", "gold_build", "reconciliation_gold"]):
        findings.add(
            "CRITICAL",
            "G19",
            "DAG missing one of: reconciliation_silver, gold_build, reconciliation_gold",
        )

    python_op_count = 0
    spark_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "PythonOperator":
                python_op_count += 1
            elif node.func.id == "SparkSubmitOperator":
                spark_count += 1
    if python_op_count > 0:
        findings.add(
            "CRITICAL",
            "G20",
            f"DAG declares {python_op_count} PythonOperator(s); Gold tasks must use SparkSubmitOperator (IL-011)",
        )
    if spark_count == 0:
        findings.add("CRITICAL", "G20", "DAG declares zero SparkSubmitOperator tasks")


def check_traceability(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """G21..G22."""
    for task in tasks:
        gold_table = _gold_table_name(task)
        table = task["module_table"]
        mod_path = project_root / "src/patient_360/gold" / f"build_{table}.py"
        tree = parse_python(mod_path)
        if tree is not None:
            doc = module_docstring(tree) or ""
            for needle in ("LLD: §5.3", "STM:", "DMS:", "DQS:"):
                if needle not in doc:
                    findings.add("WARNING", "G21", f"{table}: docstring missing '{needle}'")
                    break

        contract = load_yaml(project_root / "contracts" / f"{gold_table}.yml")
        if isinstance(contract, dict):
            ddl_path = contract.get("ddl_path")
            dq_path = contract.get("dq_path")
            if isinstance(ddl_path, str) and not (project_root / ddl_path).is_file():
                findings.add("INFO", "G22", f"{gold_table}: ddl_path -> {ddl_path} does not exist")
            if isinstance(dq_path, str) and not (project_root / dq_path).is_file():
                findings.add("INFO", "G22", f"{gold_table}: dq_path -> {dq_path} does not exist")


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
        findings.add("CRITICAL", "PRE", "Could not locate latest LLD under chapter-4/outputs/lld/v*/")
        return findings

    status = extract_metadata_status(lld_path)
    if status and status.lower() != "approved":
        findings.add("INFO", "PRE", f"LLD status is '{status}' (not Approved) — findings advisory only")

    tasks = extract_lld_gold_tasks(lld_path)
    if not tasks:
        findings.add("CRITICAL", "PRE", "No Gold task rows parsed from LLD §5.3")
        return findings

    check_presence(project_root, tasks, findings)
    check_schema_alignment(project_root, tasks, dms_path, findings)
    check_scd2_read_pattern(project_root, tasks, findings)
    check_dq_gate(project_root, tasks, upstream_root, findings)
    check_join_correctness(project_root, tasks, findings)
    check_dag_wiring(project_root, tasks, findings)
    check_traceability(project_root, tasks, findings)

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--all", type=Path)
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
