"""Validate the Gold layer implementation against the latest approved LLD.

Implements rules G1..G23 from
``developer-plugin/skills/validate-gold/SKILL.md``.

Usage:
    python validate_gold.py --project-root patient_360/
    python validate_gold.py --all <project-roots-glob>
    python validate_gold.py --project-root patient_360/ --format json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
# skills/validate-gold/scripts/ -> skills/validate-gold/ -> skills/ -> developer-plugin/
_PLUGIN_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts"))

from silver_gold_utils import (  # noqa: E402
    Findings,
    call_kwargs,
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
)

SCD2_TABLES = {
    "clinical_patients",
    "reference_organizations",
    "reference_providers",
    "reference_payers",
}


# ---------------------------------------------------------------------------
# Gold-specific parsers (DMS Gold schemas are fenced YAML, not pipe tables;
# DQS se-rules are hyphenated YAML with a dq_env block + rules subtree).
# ---------------------------------------------------------------------------


def extract_dms_gold_columns(dms_path: Path, table: str) -> list[str]:
    """Return the column names for a Gold table from a fenced YAML block in
    DMS §4.

    DMS Gold schemas are expressed as ```yaml blocks with ``table: <name>``
    and a ``columns:`` list, NOT markdown pipe tables. We scan every fenced
    YAML block, parse it, and return the column-name list for the block whose
    ``table`` matches.
    """
    text = dms_path.read_text(encoding="utf-8")
    cols: list[str] = []
    for block in re.findall(r"```ya?ml\s*\n(.*?)```", text, re.DOTALL):
        try:
            doc = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if not isinstance(doc, dict) or doc.get("table") != table:
            continue
        for col in doc.get("columns") or []:
            if isinstance(col, dict) and "name" in col:
                cols.append(str(col["name"]))
        if cols:
            break
    return cols


def se_rules_path(dqs_dir: Path, gold_table: str) -> Path:
    """Upstream se-rules file is hyphenated: se-rules-<table-with-hyphens>.yaml."""
    return dqs_dir / f"se-rules-{gold_table.replace('_', '-')}.yaml"


def load_se_rules(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def env_action(se_doc: dict | None, env: str) -> str | None:
    """Resolve the env-level action_if_failed from the se-rules dq_env block."""
    if not isinstance(se_doc, dict):
        return None
    dq_env = se_doc.get("dq_env")
    if isinstance(dq_env, dict):
        block = dq_env.get(env)
        if isinstance(block, dict):
            action = block.get("action_if_failed")
            if isinstance(action, str):
                return action
    return None


def _norm_rules(doc: dict | None) -> list:
    """Return a normalized (sorted-by-rule-id) rules subtree for semantic compare."""
    if not isinstance(doc, dict):
        return []
    rules = doc.get("rules")
    if not isinstance(rules, list):
        return []
    return sorted(
        (r for r in rules if isinstance(r, dict)),
        key=lambda r: str(r.get("rule", "")),
    )


def rules_differ(local_path: Path, upstream_path: Path) -> bool:
    """True if the ``rules:`` subtrees differ semantically (or either missing)."""
    if not local_path.is_file() or not upstream_path.is_file():
        return True
    return _norm_rules(load_se_rules(local_path)) != _norm_rules(load_se_rules(upstream_path))


def find_upstream_root(start: Path) -> Path | None:
    """Walk up from start to find the workspace root containing ``outputs/``.

    In the consolidated workspace every upstream artifact (lld, dms, stm, dqs)
    lives under the workspace's own ``outputs/`` directory, so the root is the
    nearest ancestor that has one.
    """
    here = start.resolve()
    for cand in (here, *here.parents):
        if (cand / "outputs").is_dir():
            return cand
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
        dms_cols = set(extract_dms_gold_columns(dms_path, gold_table))
        if not dms_cols:
            findings.add("INFO", "G6", f"DMS §4 YAML column block not found for '{gold_table}'; skipping")
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

        # G8/G9: every read_silver_delta(table=<scd2_table>) read must have an
        # is_current filter associated with THAT read, not merely present
        # somewhere in the file. Best-effort: locate each read_silver_delta
        # call whose table= kwarg names an SCD2 dim, then require an
        # `is_current` reference within a small line window after the read.
        lines = mod_path.read_text(encoding="utf-8").splitlines()
        scd2_reads: dict[str, list[int]] = {t: [] for t in SCD2_TABLES}
        for call in find_calls(tree, "read_silver_delta"):
            kw = call_kwargs(call)
            tbl_node = kw.get("table")
            if isinstance(tbl_node, ast.Constant) and isinstance(tbl_node.value, str):
                if tbl_node.value in SCD2_TABLES:
                    scd2_reads[tbl_node.value].append(first_line(call))

        # Window: from the read line up to the next read_silver_delta or
        # end of an assignment chain. Use a 12-line lookahead as a pragmatic bound.
        WINDOW = 12
        for scd2, read_lines in scd2_reads.items():
            for ln in read_lines:
                if ln <= 0:
                    continue
                window_text = "\n".join(lines[ln - 1 : ln - 1 + WINDOW])
                if "is_current" not in window_text:
                    findings.add(
                        "CRITICAL",
                        "G8",
                        f"{table}: reads SCD2 '{scd2}' but no is_current filter near the read",
                    )
                    continue
                # G9: ensure the form is `F.col("is_current") == True` (heuristic)
                if (
                    'F.col("is_current") == True' not in window_text
                    and "F.col('is_current') == True" not in window_text
                ):
                    findings.add(
                        "WARNING",
                        "G9",
                        f"{table}: SCD2 '{scd2}' is_current filter present but not in F.col(...) == True form",
                    )


def check_path_based_write(project_root: Path, tasks: list[dict], findings: Findings) -> None:
    """G23: Gold builders write via insertInto("unity.gold.<table>") into the
    Liquibase-pre-created EXTERNAL Delta table — no staged-create / catalog DDL.
    `saveAsTable`, `createOrReplace*`, `createTable`, and raw `CREATE TABLE`
    remain banned; `insertInto` is the required (and explicitly NOT banned)
    write path (LLD v1.13 UC write pattern)."""
    banned_attrs = {"saveAsTable", "createOrReplace", "createOrReplaceTempView", "createTable"}
    for task in tasks:
        table = task["module_table"]
        gold_table = _gold_table_name(task)
        mod_path = project_root / "src/patient_360/gold" / f"build_{table}.py"
        tree = parse_python(mod_path)
        if tree is None:
            continue
        src = mod_path.read_text(encoding="utf-8")

        # Banned catalog-write APIs (UC registration is deploy-time, Decision 15).
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and (
                node.attr in banned_attrs or node.attr.startswith("createOrReplace")
            ):
                findings.add(
                    "CRITICAL",
                    "G23",
                    f"{table}: builder uses '.{node.attr}(...)' — Gold must write path-based "
                    f"Delta only; catalog registration is deploy-time (LLD Decision 15)",
                )
        # Raw CREATE TABLE DDL in any string literal.
        if re.search(r"\bCREATE\s+TABLE\b", src, re.IGNORECASE):
            findings.add(
                "CRITICAL",
                "G23",
                f"{table}: builder contains a CREATE TABLE DDL — Gold must write "
                f"path-based Delta only (LLD Decision 15)",
            )

        # The builder writes via insertInto("unity.gold.<table>"). Assert that an
        # insertInto call targets the expected unity.gold.<table> FQN. (Path-arg
        # /gold/ checks no longer apply — Gold uses no .save(path).)
        expected_fqn = f"unity.gold.{gold_table}"
        insert_calls = find_calls(tree, "insertInto")
        insert_targets: list[str] = []
        for call in insert_calls:
            if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
                insert_targets.append(call.args[0].value)
        if not insert_calls:
            findings.add(
                "WARNING",
                "G23",
                f"{table}: no insertInto(...) call found — Gold must write via "
                f"insertInto('{expected_fqn}') into the Liquibase-pre-created "
                f"EXTERNAL Delta table (LLD v1.13 UC write pattern)",
            )
        elif insert_targets and expected_fqn not in insert_targets:
            findings.add(
                "WARNING",
                "G23",
                f"{table}: insertInto target(s) {insert_targets} do not include "
                f"the expected '{expected_fqn}'",
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

        # G12: the PROD-env resolved action_if_failed for this Gold table
        # must be `fail` — read it from the upstream SE-rules dq_env block,
        # NOT a literal action_if_failed="fail" kwarg on run_dq. If the
        # builder DOES pass an explicit literal, it must not contradict
        # the env-resolved PROD action.
        prod_action = None
        if upstream_dqs_dir is not None:
            prod_action = env_action(
                load_se_rules(se_rules_path(upstream_dqs_dir, gold_table)), "PROD"
            )
        if prod_action is not None and prod_action != "fail":
            findings.add(
                "CRITICAL",
                "G12",
                f"{gold_table}: SE-rules PROD action_if_failed='{prod_action}' "
                f"(Gold consumer table must resolve to 'fail' at PROD)",
            )
        for call in run_dq_calls:
            kw = call_kwargs(call)
            action = kw.get("action_if_failed")
            if isinstance(action, ast.Constant) and isinstance(action.value, str):
                # A hardcoded literal that contradicts the PROD env action is wrong.
                if prod_action is not None and action.value != prod_action:
                    findings.add(
                        "WARNING",
                        "G12",
                        f"{table}: run_dq hardcodes action_if_failed='{action.value}' "
                        f"but SE-rules resolve PROD to '{prod_action}'; "
                        f"prefer env-resolved action over a literal",
                    )

        # G13: run_dq before write_gold_delta
        write_calls = find_calls(tree, "write_gold_delta")
        if write_calls:
            if min(first_line(c) for c in run_dq_calls) >= min(first_line(c) for c in write_calls):
                findings.add(
                    "CRITICAL",
                    "G13",
                    f"{table}: run_dq must precede write_gold_delta",
                )

        # G14: local dq_rules `rules:` subtree matches the hyphenated upstream
        # se-rules file, compared semantically (not byte-for-byte; the local
        # copy may carry only the rules subtree + dq_env block).
        if upstream_dqs_dir is not None:
            local_yml = project_root / "dq_rules" / f"{gold_table}.yml"
            upstream_yml = se_rules_path(upstream_dqs_dir, gold_table)
            if upstream_yml.exists() and rules_differ(local_yml, upstream_yml):
                findings.add(
                    "WARNING",
                    "G14",
                    f"{gold_table}: dq_rules 'rules:' subtree diverged from upstream "
                    f"{upstream_yml.name}",
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

    # G20: scope the PythonOperator ban to the gold_build BUILDER tasks only.
    # Other Gold-stage tasks (e.g. reconciliation_gold) may legitimately be a
    # PythonOperator. A builder is identified by its LLD §5.3 task_id.
    builder_task_ids = {t["task_id"] for t in tasks if t["task_id"]}
    spark_count = 0
    bad_builders: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        op = node.func.id
        if op == "SparkSubmitOperator":
            spark_count += 1
        if op == "PythonOperator":
            kw = call_kwargs(node)
            tid_node = kw.get("task_id")
            tid = tid_node.value if isinstance(tid_node, ast.Constant) else None
            if isinstance(tid, str) and tid in builder_task_ids:
                bad_builders.append(tid)
    if bad_builders:
        findings.add(
            "CRITICAL",
            "G20",
            f"Gold builder task(s) declared as PythonOperator: {sorted(bad_builders)}; "
            f"builders must use SparkSubmitOperator (IL-011)",
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
        findings.add("CRITICAL", "PRE", "Could not locate latest LLD under outputs/lld/v*/")
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
    check_path_based_write(project_root, tasks, findings)
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
