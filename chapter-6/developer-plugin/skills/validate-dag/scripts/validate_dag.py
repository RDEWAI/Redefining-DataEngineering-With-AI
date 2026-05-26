#!/usr/bin/env python3
"""Static validator for generated Airflow DAGs and Bronze runners.

Implements the regression rules introduced after spokane's first green
Bronze run exposed three recurring code-generation bugs:

- ``DAG-PATHS-001`` — `application="run_local.py"` (relative path) is
  rejected. The path doesn't resolve when Airflow runs from
  ``/opt/airflow/`` in the cookiecutter container.
- ``DAG-PATHS-002`` — `configs_dir="airflow/configs"` (relative) is
  rejected for the same reason. Both paths must come from env vars
  (``BRONZE_RUNNER_APP``, ``AIRFLOW_CONFIGS_DIR``, ...) with absolute
  ``/opt/airflow/`` defaults.
- ``UC-WIRING-001`` — any Bronze runner under ``src/**/bronze/**.py``
  that uses ``saveAsTable("unity.bronze.<table>")`` or imports
  ``UCSingleCatalog`` is rejected. Decision 12 (UC-managed Bronze writes
  via UCSingleCatalog) was REVOKED 2026-05-12; Decision 15 was revised
  2026-05-20 to use external Delta paths via ``.option("path", ...)``;
  Decision 17 (2026-05-23) moved UC registration to deploy-time
  ``scripts/bootstrap_uc_tables.py`` via the UC REST API. The runtime
  contract is now: path-based ``.format("delta").save()`` with
  ``.option("path", …)``, NO ``saveAsTable`` in Bronze, and NO
  ``UCSingleCatalog`` wiring (IL-002 + IL-003 forbid it on Spark 4.x).

Usage:
    python validate_dag.py <file>
    python validate_dag.py --all <project_root>
    python validate_dag.py --format json <file>

Exit codes:
    0  no findings (or only INFO)
    1  CRITICAL findings present
    2  WARNING findings present (no criticals)
    3  file/dir not found, parse error, or invalid invocation
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Level(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Finding:
    level: Level
    rule: str
    file: str
    line: int
    message: str
    suggestion: str


@dataclass
class Report:
    target: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.level == Level.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.level == Level.WARNING)


# DAG-PATHS-001: literal `application="run_local.py"` (no env-var resolution).
# Allow `application=...os.environ...` patterns (the canonical fix).
RUN_LOCAL_LITERAL = re.compile(
    r"""application\s*=\s*['"]run_local\.py['"]""",
)
# DAG-PATHS-002: literal `configs_dir="airflow/configs"` (relative).
CONFIGS_DIR_LITERAL = re.compile(
    r"""configs_dir\s*=\s*['"]airflow/configs['"]""",
)
# UC-WIRING-001 (Decision 17, replaces revoked Decision 12): the FORBIDDEN
# pattern is the UC-managed write — `saveAsTable("unity.bronze.…")` and
# the `UCSingleCatalog` import that backed it. Path-based `.save()` is the
# REQUIRED runtime path now; UC table registration happens at deploy time
# via the REST client in `scripts/bootstrap_uc_tables.py`.
SAVE_AS_UNITY_BRONZE = re.compile(
    r'\.saveAsTable\(\s*[fr]?[\'"]unity\.bronze\.',
)
UC_SINGLE_CATALOG_IMPORT = re.compile(
    r"(?:from\s+\S+\s+import\s+UCSingleCatalog|UCSingleCatalog\s*[\(\.])",
)
# Bronze-runner detection: any path containing /bronze/ — Silver/Gold may
# legitimately use path-based writes for ad-hoc dumps.
IS_BRONZE_PATH = re.compile(r"(?:^|/)src/.+/bronze/.+\.py$")


def _is_anti_pattern_comment(line: str) -> bool:
    """Skip pure comment lines (Python `#`) — documentation about the bug."""
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    # Inline string literal in a docstring/log message documenting the pattern.
    lower = line.lower()
    negative_markers = (
        "never ",
        "don't",
        "do not",
        "instead",
        "deprecated",
        "forbid",
        "reject",
        "pitfall",
    )
    return any(k in lower for k in negative_markers)


def check_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings

    is_bronze = bool(IS_BRONZE_PATH.search(str(path).replace("\\", "/")))

    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_anti_pattern_comment(line):
            continue
        if RUN_LOCAL_LITERAL.search(line):
            findings.append(
                Finding(
                    level=Level.CRITICAL,
                    rule="DAG-PATHS-001",
                    file=str(path),
                    line=lineno,
                    message=(
                        'application="run_local.py" (relative path) — Airflow '
                        "runs from /opt/airflow/ in the container; the path "
                        "won't resolve."
                    ),
                    suggestion=(
                        'Use `application=os.environ.get("<TYPE>_RUNNER_APP", '
                        '"/opt/airflow/jobs/run_<task_type>.py")` so the wrapper '
                        "is auto-generated by /developer-plugin:create-dag from "
                        "LLD §4.2 task inventory."
                    ),
                )
            )
        if CONFIGS_DIR_LITERAL.search(line):
            findings.append(
                Finding(
                    level=Level.CRITICAL,
                    rule="DAG-PATHS-002",
                    file=str(path),
                    line=lineno,
                    message=(
                        'configs_dir="airflow/configs" (relative path) — same '
                        "problem as DAG-PATHS-001."
                    ),
                    suggestion=(
                        'Use `os.environ.get("AIRFLOW_CONFIGS_DIR", '
                        '"/opt/airflow/configs")` so the path resolves both in '
                        "the container and in local pytest runs."
                    ),
                )
            )
        if is_bronze and SAVE_AS_UNITY_BRONZE.search(line):
            findings.append(
                Finding(
                    level=Level.CRITICAL,
                    rule="UC-WIRING-001",
                    file=str(path),
                    line=lineno,
                    message=(
                        '`saveAsTable("unity.bronze.…")` in a Bronze runner — '
                        "Decision 12 (UC-managed runtime writes) was REVOKED "
                        "2026-05-12. Bronze must write to external Delta paths "
                        "and let UC registration happen at deploy-time "
                        "(Decision 17 / scripts/bootstrap_uc_tables.py)."
                    ),
                    suggestion=(
                        'Replace `.saveAsTable(f"unity.bronze.{table}")` with '
                        '`.format("delta").mode("append")'
                        '.option("replaceWhere", f"ds = \'{ds}\'")'
                        '.option("path", f"{warehouse}/bronze/{table}").save()`. '
                        "UC table registration is performed by "
                        "`scripts/bootstrap_uc_tables.py` at deploy-time."
                    ),
                )
            )
        if is_bronze and UC_SINGLE_CATALOG_IMPORT.search(line):
            findings.append(
                Finding(
                    level=Level.CRITICAL,
                    rule="UC-WIRING-001",
                    file=str(path),
                    line=lineno,
                    message=(
                        "`UCSingleCatalog` in a Bronze runner — IL-002 forbids "
                        "wiring `spark.sql.catalog.spark_catalog` to "
                        "UCSingleCatalog on local-FS dev (Spark 4.x). Use "
                        "DeltaCatalog plus Spark's built-in Hive metastore."
                    ),
                    suggestion=(
                        "Remove the `UCSingleCatalog` wiring. Set "
                        "`spark.sql.catalog.spark_catalog = "
                        "org.apache.spark.sql.delta.catalog.DeltaCatalog` and "
                        "`spark.sql.catalogImplementation = hive` (IL-003) in "
                        "the SparkSession builder."
                    ),
                )
            )

    return findings


def collect_targets(root: Path) -> list[Path]:
    """Files validate-dag inspects when invoked with --all <project_root>."""
    if root.is_file():
        return [root]
    targets: list[Path] = []
    for sub in ("airflow/dags", "airflow/jobs", "src"):
        d = root / sub
        if d.is_dir():
            targets.extend(p for p in d.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(targets)


def render_text(report: Report) -> str:
    by_level: dict[Level, list[Finding]] = {Level.CRITICAL: [], Level.WARNING: [], Level.INFO: []}
    for f in report.findings:
        by_level[f.level].append(f)
    lines = [f"validate-dag report for {report.target}"]
    for level in (Level.CRITICAL, Level.WARNING, Level.INFO):
        bucket = by_level[level]
        if not bucket:
            continue
        lines.append(f"  {level.value} ({len(bucket)})")
        for f in bucket:
            lines.append(f"    {f.rule} {f.file}:{f.line}")
            lines.append(f"      {f.message}")
            lines.append(f"      Fix: {f.suggestion}")
    if not report.findings:
        lines.append("  All checks passed.")
    lines.append(f"Summary: {report.critical_count} critical, {report.warning_count} warnings")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(
        {
            "target": report.target,
            "critical_count": report.critical_count,
            "warning_count": report.warning_count,
            "findings": [
                {
                    "level": f.level.value,
                    "rule": f.rule,
                    "file": f.file,
                    "line": f.line,
                    "message": f.message,
                    "suggestion": f.suggestion,
                }
                for f in report.findings
            ],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated Airflow DAGs / Bronze runners",
    )
    parser.add_argument("path", type=Path, help="File or project root (with --all)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Recurse under <project_root>/{airflow,src}",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"Error: {args.path} does not exist.", file=sys.stderr)
        return 3

    if args.all:
        if not args.path.is_dir():
            print("Error: --all requires a directory.", file=sys.stderr)
            return 3
        targets = collect_targets(args.path)
    else:
        targets = [args.path]

    findings: list[Finding] = []
    for t in targets:
        findings.extend(check_file(t))

    report = Report(target=str(args.path), findings=findings)
    out = render_json(report) if args.format == "json" else render_text(report)
    print(out)

    if report.critical_count:
        return 1
    if report.warning_count:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
