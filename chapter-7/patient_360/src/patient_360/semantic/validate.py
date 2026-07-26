"""Validate a :class:`SemanticModel` against the physical Gold contracts.

This is the anti-drift gate: pydantic guarantees the model is structurally sound, and this
module additionally proves every column the model references still exists (with a compatible
type) in ``contracts/*.yml`` — the same contracts the pipeline builds against. It needs no
live Spark/UC stack, so it runs in unit CI. Relationship, metric, and verified-query
integrity are checked too.

Exit codes (via :func:`main`): 0 when there are no CRITICAL findings, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from patient_360.semantic.loader import DEFAULT_SEMANTIC_DIR, load_model
from patient_360.semantic.schema import AggKind, Entity, SemanticModel

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACTS_DIR = _PROJECT_ROOT / "contracts"

# Metadata columns present in the physical contract that the semantic model deliberately omits.
_INTERNAL_COLUMNS = {"_ingested_at"}

# Tokens to ignore when scanning a custom measure expression for column references.
_SQL_KEYWORDS = {
    "case", "when", "then", "else", "end", "and", "or", "not", "null", "is", "distinct",
    "count", "sum", "avg", "min", "max", "cast", "as", "coalesce", "true", "false", "on",
    "by", "over", "partition", "in", "like", "between", "round",
}
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FROM_JOIN_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z0-9_.]+)", re.IGNORECASE)


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    location: str
    message: str

    def format(self) -> str:
        return f"[{self.severity.value}] {self.location}: {self.message} ({self.code})"


def _bare_table(fqn: str) -> str:
    """`unity.gold.patient_summary` -> `patient_summary`."""
    return fqn.split(".")[-1]


def _base_type(t: str) -> str:
    """Normalize a physical/declared type to its base (`decimal(12,2)` -> `decimal`)."""
    return re.split(r"[(<]", t.strip().lower(), maxsplit=1)[0]


def _load_contract_columns(contracts_dir: Path, table_fqn: str) -> dict[str, str] | None:
    """Return {column_name: base_type} for a Gold table's contract, or None if absent."""
    path = contracts_dir / f"{_bare_table(table_fqn)}.yml"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cols: dict[str, str] = {}
    for field in data.get("schema", []):
        cols[field["name"]] = _base_type(str(field.get("type", "")))
    return cols


def _measure_columns(expr: str) -> set[str]:
    """Identifiers referenced in a measure expression, excluding SQL keywords."""
    return {tok for tok in _IDENT_RE.findall(expr) if tok.lower() not in _SQL_KEYWORDS}


def _check_entity(entity: Entity, columns: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    loc = entity.table

    if entity.primary_key not in columns:
        findings.append(Finding(Severity.CRITICAL, "SM-PK-MISSING", loc,
                                f"primary_key '{entity.primary_key}' not in contract"))

    referenced: set[str] = {entity.primary_key}
    for dim in entity.dimensions:
        referenced.add(dim.column)
        if dim.column not in columns:
            findings.append(Finding(Severity.CRITICAL, "SM-COL-MISSING", f"{loc}.{dim.name}",
                                    f"dimension column '{dim.column}' not in contract"))
            continue
        if dim.type and _base_type(dim.type) != columns[dim.column]:
            findings.append(Finding(Severity.WARNING, "SM-TYPE-MISMATCH", f"{loc}.{dim.name}",
                                    f"declared type '{dim.type}' != contract "
                                    f"'{columns[dim.column]}' for '{dim.column}'"))

    for measure in entity.measures:
        cols = _measure_columns(measure.expr) if measure.expr else set()
        if measure.agg is AggKind.COUNT and not measure.expr:
            continue  # COUNT(*) references no column
        mloc = f"{loc}.{measure.name}"
        for col in cols:
            if col in columns:
                referenced.add(col)
            else:
                findings.append(Finding(Severity.CRITICAL, "SM-MEASURE-COL", mloc,
                                        f"measure references unknown column '{col}'"))

    uncovered = sorted(set(columns) - referenced - _INTERNAL_COLUMNS)
    if uncovered:
        cols_txt = ", ".join(uncovered)
        findings.append(Finding(Severity.INFO, "SM-COVERAGE", loc,
                                f"contract columns not surfaced in the model: {cols_txt}"))
    return findings


def _check_relationships(model: SemanticModel) -> list[Finding]:
    findings: list[Finding] = []
    for rel in model.relationships:
        loc = rel.name or f"{rel.from_entity}->{rel.to_entity}"
        src = model.entity(rel.from_entity)
        dst = model.entity(rel.to_entity)
        if src is None:
            findings.append(Finding(Severity.CRITICAL, "SM-REL-ENTITY", loc,
                                    f"unknown from_entity '{rel.from_entity}'"))
        elif not src.has_column(rel.from_column):
            findings.append(Finding(Severity.CRITICAL, "SM-REL-COL", loc,
                                    f"from_column '{rel.from_column}' not a dimension/PK of "
                                    f"'{rel.from_entity}'"))
        if dst is None:
            findings.append(Finding(Severity.CRITICAL, "SM-REL-ENTITY", loc,
                                    f"unknown to_entity '{rel.to_entity}'"))
        elif not dst.has_column(rel.to_column):
            findings.append(Finding(Severity.CRITICAL, "SM-REL-COL", loc,
                                    f"to_column '{rel.to_column}' not a dimension/PK of "
                                    f"'{rel.to_entity}'"))
    return findings


def _check_metrics(model: SemanticModel) -> list[Finding]:
    findings: list[Finding] = []
    for metric in model.metrics:
        entity = model.entity(metric.entity)
        if entity is None:
            findings.append(Finding(Severity.CRITICAL, "SM-METRIC-ENTITY", metric.name,
                                    f"unknown entity '{metric.entity}'"))
            continue
        if entity.measure(metric.measure) is None:
            findings.append(Finding(Severity.CRITICAL, "SM-METRIC-MEASURE", metric.name,
                                    f"measure '{metric.measure}' not defined on '{metric.entity}'"))
        for dim in metric.group_by:
            if entity.dimension(dim) is None:
                findings.append(Finding(Severity.CRITICAL, "SM-METRIC-GROUPBY", metric.name,
                                        f"group_by '{dim}' not a dimension of '{metric.entity}'"))
    return findings


def _check_verified_queries(model: SemanticModel) -> list[Finding]:
    findings: list[Finding] = []
    known = set(model.tables())
    for i, vq in enumerate(model.verified_queries):
        for table in _FROM_JOIN_RE.findall(vq.sql):
            if table not in known:
                findings.append(Finding(Severity.WARNING, "SM-VQ-TABLE", f"verified_queries[{i}]",
                                        f"references table '{table}' not in the model"))
    return findings


def validate_model(
    model: SemanticModel,
    contracts_dir: str | Path | None = None,
) -> list[Finding]:
    """Return all findings for ``model`` cross-checked against the Gold contracts."""
    cdir = Path(contracts_dir) if contracts_dir is not None else DEFAULT_CONTRACTS_DIR
    findings: list[Finding] = []
    for entity in model.entities:
        columns = _load_contract_columns(cdir, entity.table)
        if columns is None:
            bare = _bare_table(entity.table)
            findings.append(Finding(Severity.CRITICAL, "SM-CONTRACT-MISSING", entity.table,
                                    f"no contract found under {cdir} for '{bare}'"))
            continue
        findings.extend(_check_entity(entity, columns))
    findings.extend(_check_relationships(model))
    findings.extend(_check_metrics(model))
    findings.extend(_check_verified_queries(model))
    return findings


def _rank(findings: list[Finding]) -> list[Finding]:
    order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return sorted(findings, key=lambda f: order[f.severity])


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: validate the default model and print a ranked report."""
    semantic_dir = argv[0] if argv else str(DEFAULT_SEMANTIC_DIR)
    model = load_model(semantic_dir)
    findings = _rank(validate_model(model))

    counts = {sev: sum(1 for f in findings if f.severity is sev) for sev in Severity}
    print(f"Semantic model '{model.name}' v{model.version}: "
          f"{len(model.entities)} entities, {len(model.metrics)} metrics, "
          f"{len(model.verified_queries)} verified queries")
    for finding in findings:
        print(finding.format())
    print(f"\n{counts[Severity.CRITICAL]} CRITICAL, {counts[Severity.WARNING]} WARNING, "
          f"{counts[Severity.INFO]} INFO")
    return 1 if counts[Severity.CRITICAL] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
