#!/usr/bin/env python3
"""Generate per-table Spark-Expectations YAML rule files from a DQS markdown.

Parses a Data Quality Specification (DQS) markdown document, groups rules by
target table, reads a Spark-Expectations config template YAML, and generates
one SE-compatible YAML file per table.

Usage:
    python generate_se_rules.py <dqs.md> [--config se-config.yaml] [-o output-dir/]

Exit Codes:
    0: Success — all SE YAML files generated
    1: Parse error — DQS could not be parsed
    2: Config error — SE config template missing or invalid
    3: Output error — could not write output files
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlparse
import yaml
from sqlparse import tokens as stypes

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

# SCD Type-2 metadata columns are MANUFACTURED by the `apply_scd2` helper
# (effective_from/to, is_current, _record_hash) AFTER the inline DQ gate runs
# on the cleansed business DataFrame. A field rule on one of these columns
# cannot be evaluated inline (the column does not exist on the pre-MERGE
# DataFrame → `UNRESOLVED_COLUMN`) and is redundant anyway (the helper
# guarantees them non-null by construction). Such rules are emitted INACTIVE
# so they stay documented in the DQS lineage but do not run in the inline
# Spark-Expectations gate. (They belong to a post-MERGE / dimension-audit
# stage if validated at all.)
SCD2_METADATA_COLUMNS = frozenset(
    {"effective_from", "effective_to", "is_current", "_record_hash"}
)

# A FLD rule whose expression contains one of these TABLE-LEVEL aggregate
# functions (evaluated over the whole table, e.g. a grain/row-count/uniqueness
# check) must be emitted as `agg_dq`, not `row_dq`. A bare aggregate inside a
# row_dq expectation is passed to F.expr() per row and raises
# [MISSING_GROUP_BY] at runtime. CARDINALITY()/SIZE() (ARRAY length) are
# DELIBERATELY absent: they are per-row scalar functions on an array column, so
# a rule like `CARDINALITY(allergies) <= 50` stays a per-row row_dq check.
_AGG_FUNC_RE = re.compile(
    r"\b(count|sum|avg|min|max|stddev|variance)\s*\(", re.IGNORECASE
)


@dataclass
class DqsRule:
    """A single DQS rule extracted from the DQS markdown."""

    rule_id: str
    table: str
    column: str
    check_type: str
    expression: str
    severity: str
    action: str
    layer: str = ""
    description: str = ""

    @property
    def se_rule_name(self) -> str:
        """SE-safe rule identifier (no hyphens).

        Spark-Expectations builds DataFrame column names from the rule name
        (e.g. ``row_dq_<rule>``) and references them UNQUOTED in generated
        SQL. A hyphenated id like ``DQ-FLD-077`` becomes ``row_dq_DQ-FLD-077``,
        which Spark parses as arithmetic (``row_dq_DQ - FLD - 077``) and fails
        with ``UNRESOLVED_COLUMN``. Emit the ``rule:`` field with underscores
        (``DQ_FLD_077``) so SE's column generation is valid. The human-facing
        DQS keeps the hyphenated ids; this is the SE-internal form only.
        """
        return self.rule_id.replace("-", "_")

    @property
    def rule_type(self) -> str:
        """Map DQS rule category to Spark-Expectations rule type."""
        prefix = self.rule_id.split("-")[1].upper() if "-" in self.rule_id else ""
        if prefix == "FLD":
            # Most FLD rules are per-row predicates (row_dq). But a FLD rule
            # whose expression is a TABLE-LEVEL aggregate (COUNT/SUM/... over the
            # whole table — e.g. a grain row-count or uniqueness check) must be
            # agg_dq: a bare aggregate in a row_dq expectation raises
            # [MISSING_GROUP_BY]. A subquery-based expression belongs to
            # query_dq, so only classify NON-subquery aggregates as agg_dq. A
            # per-row scalar such as CARDINALITY(arr) is NOT an aggregate (it is
            # not in _AGG_FUNC_RE) and correctly stays row_dq.
            expr = self.expression or ""
            if _AGG_FUNC_RE.search(expr) and "select" not in expr.lower():
                return "agg_dq"
            return "row_dq"
        elif prefix == "STA":
            return "agg_dq"
        elif prefix in ("REF", "REC"):
            return "query_dq"
        elif prefix == "FRS":
            return "agg_dq"
        # Default: row-level for unknown
        return "row_dq"

    @property
    def is_scd2_metadata_rule(self) -> bool:
        """True when this rule targets an SCD2 metadata column.

        These columns are added by `apply_scd2` AFTER the inline DQ gate, so
        the rule must not run inline (see SCD2_METADATA_COLUMNS).
        """
        return (self.column or "").strip() in SCD2_METADATA_COLUMNS

    @property
    def is_drop_action(self) -> bool:
        """True when the DQS Action column directs a pre-write row drop/filter.

        A row_dq rule whose Action text says "Drop record" or "filter out"
        signals an expected, bounded set of rows that must be physically
        removed before the write (e.g. standalone null-encounter observations),
        rather than rejected/halted. Only valid for row_dq rules.
        """
        if self.rule_type != "row_dq":
            return False
        action = self.action.lower()
        return "drop record" in action or "filter out" in action

    @property
    def action_if_failed(self) -> str:
        """Map DQS severity/action to SE action_if_failed.

        A "Drop record"/"filter out" Action overrides severity and emits
        `drop` so spark-expectations physically removes the failing rows.

        Severity model (medallion DQ):
          - Field validations (row_dq / FLD): HARD GATE — fail (CRITICAL) or
            ignore (else). A null PK / bad type is unambiguously broken data.
          - Referential (query_dq / REF) and Statistical (agg_dq / STA):
            MONITOR/ALERT, never a hard stop. A handful of orphan FKs or a
            statistical drift must not halt the whole pipeline — they are
            observability signals recorded to the SE stats table. So they map
            to `ignore` regardless of DQS severity. (Tighten to `fail` in a
            PROD-specific generation if/when the data is full + consistent.)
        """
        if self.is_drop_action:
            return "drop"
        prefix = self.rule_id.split("-")[1].upper() if "-" in self.rule_id else ""
        if prefix in ("REF", "STA"):
            return "ignore"
        # Bronze is a RAW LANDING ZONE: it must land every source row as-is and
        # only MONITOR quality — it never rejects/halts on a raw-data quality
        # issue (e.g. a nullable FK like a standalone observation's ENCOUNTER).
        # Hard enforcement (fail/drop) is the Silver layer's job, after the data
        # is conformed. So Bronze row_dq field validations map to `ignore`
        # (recorded to the SE stats table) regardless of DQS severity. Drop
        # rules (handled above) still drop; REF/STA already monitor.
        if self.rule_type == "row_dq" and self.layer == "bronze":
            return "ignore"
        return "fail" if self.severity.upper() == "CRITICAL" else "ignore"

    @property
    def tag(self) -> str:
        """Map rule category to SE tag."""
        prefix = self.rule_id.split("-")[1].upper() if "-" in self.rule_id else ""
        tag_map = {
            "FLD": "field_validation",
            "REF": "referential_integrity",
            "STA": "statistical_distribution",
            "REC": "reconciliation",
            "FRS": "freshness_sla",
        }
        return tag_map.get(prefix, "custom")

    @property
    def enable_querydq_custom_output(self) -> bool:
        """Enable custom output for query_dq rules."""
        return self.rule_type == "query_dq"

    @property
    def enable_error_drop_alert(self) -> bool:
        """Enable error drop alert for statistical and reconciliation rules."""
        prefix = self.rule_id.split("-")[1].upper() if "-" in self.rule_id else ""
        return prefix in ("STA", "REC")

    @property
    def priority(self) -> str:
        """Map DQS severity to SE priority."""
        return "high" if self.severity.upper() == "CRITICAL" else "medium"

    def error_drop_threshold(self, default: int = 0) -> int:
        """Extract integer percentage threshold from expression, or use default.

        SE stores error_drop_threshold as an integer representing a percentage.
        E.g., 5 means "alert if >5% of rows are dropped".
        """
        # Try to find percentage in expression like "±20%" or "< 5%"
        match = re.search(r"(?:±|\+/-)\s*(\d+(?:\.\d+)?)\s*%", self.expression)
        if match:
            return int(float(match.group(1)))
        match = re.search(r"<\s*(\d+(?:\.\d+)?)\s*%", self.expression)
        if match:
            return int(float(match.group(1)))
        return default


# ---------------------------------------------------------------------------
# DQS parser
# ---------------------------------------------------------------------------


def _normalize_table_name(raw: str) -> str:
    """Extract clean schema.table from a DQS cell that may contain qualifiers.

    DQS markdown may embed SQL qualifiers in table references, e.g.:
      analytics.dim_patient (WHERE is_current = TRUE)
      clinical.patients (COUNT DISTINCT patient_id)
      analytics.fact_encounter (SUM base_encounter_cost)

    These parenthetical parts are DQS documentation — not part of the table
    name. SE needs only the fully-qualified table reference: schema.table
    """
    cleaned = raw.strip()
    # Strip parenthetical qualifiers: everything from first '(' onwards
    paren_idx = cleaned.find("(")
    if paren_idx > 0:
        cleaned = cleaned[:paren_idx].strip()
    # Strip backticks after paren removal (handles `table` (qualifier) case)
    return cleaned.strip("`").strip()


def _parse_table_rows(content: str) -> list[list[str]]:
    """Parse markdown table rows into lists of cell strings."""
    rows = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Skip separator rows
        inner = stripped.strip("|")
        if re.match(r"^[\s\-:|]+$", inner):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


def _parse_field_level_rules(section_content: str) -> list[DqsRule]:
    """Parse Section 2: Field-Level Validation Rules."""
    rules: list[DqsRule] = []
    current_layer = ""

    for line in section_content.split("\n"):
        # Track layer subsections
        if line.startswith("### "):
            layer_text = line.lstrip("# ").strip()
            if "bronze" in layer_text.lower():
                current_layer = "bronze"
            elif "silver" in layer_text.lower():
                current_layer = "silver"
            elif "gold" in layer_text.lower():
                current_layer = "gold"
            else:
                current_layer = layer_text.lower()
            continue

        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        inner = stripped.strip("|")
        if re.match(r"^[\s\-:|]+$", inner):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        rule_id = cells[0]
        if not re.match(r"DQ-[A-Z]{2,4}-\d{3}", rule_id):
            continue

        table = _normalize_table_name(cells[1])
        column = cells[2].strip() if len(cells) > 2 else ""
        # Support both 7-col and 5-col formats
        if len(cells) >= 7:
            check_type = cells[3].strip()
            expression = cells[4].strip()
            severity = cells[5].strip()
            action = cells[6].strip()
        elif len(cells) >= 5:
            expression = cells[3].strip()
            severity = cells[4].strip()
            check_type = expression
            action = ""
        else:
            expression = cells[3].strip() if len(cells) > 3 else ""
            severity = "WARNING"
            check_type = expression
            action = ""

        # Strip backticks from expressions — SE F.expr() doesn't want them
        expression = expression.strip("`").strip()

        rules.append(
            DqsRule(
                rule_id=rule_id,
                table=table,
                column=column,
                check_type=check_type,
                expression=expression,
                severity=severity,
                action=action,
                layer=current_layer,
                description=f"{check_type} on {column}",
            )
        )

    return rules


def _parse_referential_integrity_rules(section_content: str) -> list[DqsRule]:
    """Parse Section 3: Referential Integrity Rules."""
    rules: list[DqsRule] = []
    rows = _parse_table_rows(section_content)

    for cells in rows:
        if len(cells) < 4:
            continue
        rule_id = cells[0]
        if not re.match(r"DQ-[A-Z]{2,4}-\d{3}", rule_id):
            continue

        # Support both 8-col and 5-col formats
        child_table = _normalize_table_name(cells[1])
        child_col = cells[2].strip() if len(cells) > 2 else ""
        parent_table = _normalize_table_name(cells[3]) if len(cells) > 3 else ""
        parent_col = cells[4].strip() if len(cells) > 4 else child_col
        layer = cells[5].strip().lower() if len(cells) > 5 else ""
        severity = (
            cells[7].strip()
            if len(cells) > 7
            else cells[4].strip()
            if len(cells) > 4
            else "WARNING"
        )

        if child_col and parent_table and parent_col:
            # SE wraps query_dq as SELECT (expectation) AS OUTPUT
            # and casts result to int: non-zero = pass, zero = fail.
            # Return a scalar: 1 if no orphans, 0 if orphans exist.
            #
            # Table references must resolve at runtime (REF runs at TARGET,
            # post-row_dq-drop):
            #  - the CHILD (self) table is SE's post-drop temp view,
            #    named `<bare_table>_view` (SE registers it as
            #    `{target_table.split('.')[-1]}_view`), so the FK check
            #    validates the CLEANED rows, not the pre-drop input.
            #  - the PARENT (FK target) is referenced by BARE name; the SE
            #    runner pre-registers every `unity.silver/bronze.*` table as a
            #    bare-name TEMP VIEW so a 1-part name resolves under
            #    `defaultCatalog=unity` (where it otherwise would not).
            child_view = f"{child_table.split('.')[-1]}_view"
            parent_ref = parent_table.split(".")[-1]
            # The expectation MUST be a BOOLEAN scalar — spark-expectations
            # wraps it as `CASE WHEN <expectation> THEN <pass> ELSE <fail>`,
            # which requires BOOLEAN (an INT 1/0 raises DATATYPE_MISMATCH:
            # "first parameter requires BOOLEAN, has INT"). Emit the orphan
            # check directly as a boolean: TRUE (pass) when there are no
            # orphans, FALSE (fail) when an FK is unmatched.
            expression = (
                f"(SELECT COUNT(*) FROM {child_view} c "
                f"LEFT JOIN {parent_ref} p "
                f"ON c.{child_col} = p.{parent_col} "
                f"WHERE p.{parent_col} IS NULL) = 0"
            )
        else:
            expression = f"FK check on {child_table}"

        rules.append(
            DqsRule(
                rule_id=rule_id,
                table=child_table,
                column="",
                check_type="REFERENTIAL_INTEGRITY",
                expression=expression,
                severity=severity,
                action=cells[6].strip() if len(cells) > 6 else "Reject",
                layer=layer,
                description=(f"FK check: {child_table}.{child_col} -> {parent_table}.{parent_col}"),
            )
        )

    return rules


def _parse_statistical_rules(section_content: str) -> list[DqsRule]:
    """Parse Section 4: Statistical Distribution Tests.

    Handles two sub-table formats:
    - Row Count (8 cols): Rule ID | Table | Metric | Baseline |
      Threshold | Frequency | Layer | Alert
    - Null Rate (9 cols): Rule ID | Table | Column | Metric |
      Baseline | Threshold | Frequency | Layer | Alert
    """
    rules: list[DqsRule] = []
    rows = _parse_table_rows(section_content)

    for cells in rows:
        if len(cells) < 4:
            continue
        rule_id = cells[0]
        if not re.match(r"DQ-[A-Z]{2,4}-\d{3}", rule_id):
            continue

        table = _normalize_table_name(cells[1])

        # Detect format: 9-col null rate tables have "Null rate" in cells[3]
        is_null_rate = len(cells) >= 9 and "null" in cells[3].lower()

        if is_null_rate:
            # 9-col: rule_id, table, column, metric, baseline, threshold, frequency, layer, alert
            col = cells[2].strip()
            metric = cells[3].strip()
            baseline = cells[4].strip()
            threshold = cells[5].strip()
            layer = cells[7].strip().lower() if len(cells) > 7 else ""
            severity = cells[8].strip() if len(cells) > 8 else "WARNING"
        else:
            # 8-col: rule_id, table, metric, baseline, threshold, frequency, layer, alert
            col = ""
            metric = cells[2].strip() if len(cells) > 2 else ""
            baseline = cells[3].strip() if len(cells) > 3 else ""
            threshold = cells[4].strip() if len(cells) > 4 else ""
            layer = cells[6].strip().lower() if len(cells) > 6 else ""
            severity = cells[7].strip() if len(cells) > 7 else "WARNING"

        # Build aggregate expression from metric and threshold
        if is_null_rate:
            # Parse threshold like "WARNING if < 80% or > 93%"
            lower_pct_match = re.search(r"<\s*(\d+(?:\.\d+)?)\s*%", threshold)
            upper_pct_match = re.search(r">\s*(\d+(?:\.\d+)?)\s*%", threshold)
            if lower_pct_match and upper_pct_match:
                lo = float(lower_pct_match.group(1))
                hi = float(upper_pct_match.group(1))
                expression = (
                    f"(sum(case when {col} is null then 1 else 0 end) "
                    f"* 100.0 / nullif(count(*), 0)) > {lo} and "
                    f"(sum(case when {col} is null then 1 else 0 end) "
                    f"* 100.0 / nullif(count(*), 0)) < {hi}"
                )
            else:
                expression = (
                    f"(sum(case when {col} is null then 1 else 0 end) "
                    f"* 100.0 / nullif(count(*), 0)) < 5"
                )
        elif "row count" in metric.lower() or "row_count" in metric.lower():
            expression = "count(*) > 0"
            if baseline and re.match(r"[\d,]+", baseline):
                base_val = int(baseline.replace(",", ""))
                pct_match = re.search(r"(?:±|\+/-)\s*(\d+)\s*%", threshold)
                if pct_match:
                    pct = int(pct_match.group(1))
                    lower_bound = int(base_val * (1 - pct / 100))
                    upper_bound = int(base_val * (1 + pct / 100))
                    expression = f"count(*) > {lower_bound} and count(*) < {upper_bound}"
        else:
            expression = "count(*) > 0"

        # Extract primary severity from alert text like "CRITICAL if below; WARNING if above"
        sev_match = re.match(r"(CRITICAL|WARNING|INFO)", severity, re.IGNORECASE)
        resolved_severity = sev_match.group(1).upper() if sev_match else "WARNING"

        rules.append(
            DqsRule(
                rule_id=rule_id,
                table=table,
                column=col,
                check_type="STATISTICAL",
                expression=expression,
                severity=resolved_severity,
                action="",
                layer=layer,
                description=f"Statistical check: {metric} baseline={baseline}",
            )
        )

    return rules


def _parse_reconciliation_rules(section_content: str) -> list[DqsRule]:
    """Parse Section 5: Reconciliation Rules."""
    rules: list[DqsRule] = []
    rows = _parse_table_rows(section_content)

    for cells in rows:
        if len(cells) < 4:
            continue
        rule_id = cells[0]
        if not re.match(r"DQ-[A-Z]{2,4}-\d{3}", rule_id):
            continue

        raw_source = cells[1].strip()
        raw_target = cells[2].strip()
        comparison = cells[3].strip() if len(cells) > 3 else ""
        tolerance = cells[4].strip() if len(cells) > 4 else ""
        severity_raw = cells[6].strip() if len(cells) > 6 else "CRITICAL"

        # Extract severity from escalation field (e.g., "CRITICAL -- PagerDuty")
        sev_match = re.match(r"(CRITICAL|WARNING|INFO)", severity_raw, re.IGNORECASE)
        severity = sev_match.group(1).upper() if sev_match else "CRITICAL"

        # Extract numeric tolerance (e.g., "±0.1%" → 0.1, "0%" → 0)
        tol_pct = "0.1"
        tol_match = re.search(r"(\d+\.?\d*)\s*%", tolerance)
        if tol_match:
            tol_pct = tol_match.group(1)

        # Handle special reconciliation types:
        # SUM aggregate (DQ-REC-009): source is "SUM(table.col)", target is "SUM(table.col)"
        # DISTINCT count (DQ-REC-010): source is "COUNT(DISTINCT table.col)", target is similar
        is_sum_recon = "SUM(" in raw_source.upper()
        is_distinct_recon = "DISTINCT" in raw_source.upper()

        if is_sum_recon:
            # Extract table.column from SUM(schema.table.column)
            src_match = re.search(r"SUM\((\w+\.\w+)\.(\w+)\)", raw_source, re.IGNORECASE)
            tgt_match = re.search(r"SUM\((\w+\.\w+)\.(\w+)\)", raw_target, re.IGNORECASE)
            if src_match and tgt_match:
                src_tbl = src_match.group(1)
                src_col = src_match.group(2)
                tgt_tbl = tgt_match.group(1)
                tgt_col = tgt_match.group(2)
                expression = (
                    f"CASE WHEN ABS(s.val - t.val) * 100.0 "
                    f"/ NULLIF(s.val, 0) <= {tol_pct} "
                    f"THEN 1 ELSE 0 END "
                    f"FROM (SELECT SUM({src_col}) AS val FROM {src_tbl}) s, "
                    f"(SELECT SUM({tgt_col}) AS val FROM {tgt_tbl}) t"
                )
                target_table = _normalize_table_name(tgt_tbl)
            else:
                continue  # Skip unparseable SUM reconciliation
        elif is_distinct_recon:
            # Extract from COUNT(DISTINCT schema.table.column [WHERE ...])
            src_match = re.search(r"COUNT\(DISTINCT\s+(\w+\.\w+)\.(\w+)", raw_source, re.IGNORECASE)
            tgt_match = re.search(r"COUNT\(DISTINCT\s+(\w+\.\w+)\.(\w+)", raw_target, re.IGNORECASE)
            if src_match and tgt_match:
                src_tbl = src_match.group(1)
                src_col = src_match.group(2)
                tgt_tbl = tgt_match.group(1)
                tgt_col = tgt_match.group(2)
                # Check for WHERE clause in target
                where_match = re.search(r"WHERE\s+(.+?)(?:\)|$)", raw_target, re.IGNORECASE)
                where_clause = f" WHERE {where_match.group(1).rstrip(')')}" if where_match else ""
                expression = (
                    f"CASE WHEN ABS(s.cnt - t.cnt) * 100.0 "
                    f"/ NULLIF(s.cnt, 0) <= {tol_pct} "
                    f"THEN 1 ELSE 0 END "
                    f"FROM (SELECT COUNT(DISTINCT {src_col}) AS cnt FROM {src_tbl}) s, "
                    f"(SELECT COUNT(DISTINCT {tgt_col}) AS cnt FROM {tgt_tbl}{where_clause}) t"
                )
                target_table = _normalize_table_name(tgt_tbl)
            else:
                continue  # Skip unparseable DISTINCT reconciliation
        else:
            # Standard COUNT(*) reconciliation
            source_table = _normalize_table_name(raw_source)
            target_table = _normalize_table_name(raw_target)

            # Handle WHERE clause in target
            # e.g., "analytics.dim_patient (WHERE is_current = TRUE)"
            where_match = re.search(r"\(WHERE\s+(.+?)\)", raw_target, re.IGNORECASE)
            target_where = f" WHERE {where_match.group(1)}" if where_match else ""

            expression = (
                f"CASE WHEN ABS(s.cnt - t.cnt) * 100.0 "
                f"/ NULLIF(s.cnt, 0) <= {tol_pct} "
                f"THEN 1 ELSE 0 END "
                f"FROM (SELECT COUNT(*) AS cnt FROM {source_table}) s, "
                f"(SELECT COUNT(*) AS cnt FROM {target_table}{target_where}) t"
            )

        rules.append(
            DqsRule(
                rule_id=rule_id,
                table=target_table,
                column="",
                check_type="RECONCILIATION",
                expression=expression,
                severity=severity,
                action="",
                layer="gold",
                description=(
                    f"Reconciliation: {raw_source.strip()} vs {raw_target.strip()}"
                    f" ({comparison}), tolerance={tolerance}"
                ),
            )
        )

    return rules


def parse_dqs(dqs_path: Path) -> list[DqsRule]:
    """Parse a DQS markdown file and return all rules."""
    content = dqs_path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current_heading = ""
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    rules: list[DqsRule] = []

    field_key = next(
        (k for k in sections if "Field-Level" in k or "Field Level" in k),
        None,
    )
    if field_key:
        rules.extend(_parse_field_level_rules(sections[field_key]))

    ref_key = next(
        (k for k in sections if "Referential" in k),
        None,
    )
    if ref_key:
        rules.extend(_parse_referential_integrity_rules(sections[ref_key]))

    stat_key = next(
        (k for k in sections if "Statistical" in k),
        None,
    )
    if stat_key:
        rules.extend(_parse_statistical_rules(sections[stat_key]))

    rec_key = next(
        (k for k in sections if "Reconciliation" in k),
        None,
    )
    if rec_key:
        rules.extend(_parse_reconciliation_rules(sections[rec_key]))

    return rules


# ---------------------------------------------------------------------------
# SE config loader
# ---------------------------------------------------------------------------


_DEFAULT_DQ_ENV = {
    "DEV": {
        # ENV-AGNOSTIC 3-part FQN `unity.<layer>.<table>` (resolved via
        # layer_schemas). All envs (DEV/QA/PROD) run against ONE local Unity
        # Catalog OSS metastore (LLD §1), so table_name is IDENTICAL across envs
        # — only per-env POLICY (action_if_failed / thresholds / priority) varies.
        # The schema IS required: SE filters the rule set on
        # `table_name == target_table` and derives its `<t>_stats`/`<t>_error`
        # audit-table FQNs from it. What breaks SE is an ENV-DB PREFIX like
        # `dev_analytics.<t>` — that catalog.schema does not exist in UC, so the
        # stats/error saveAsTable fails. `unity.<layer>` DOES exist, so use it.
        "table_name": "{schema}.{table}",
        "action_if_failed": "ignore",  # permissive — log but don't block
        "enable_for_source_dq_validation": True,
        "enable_for_target_dq_validation": True,
        "is_active": True,
        "enable_error_drop_alert": False,
        "error_drop_threshold": 0,  # integer % — alert on any drop
        "priority": "medium",
    },
    "QA": {
        "table_name": "{schema}.{table}",  # env-agnostic — see DEV note
        "action_if_failed": "ignore",  # NOT drop — drop only valid for row_dq
        "enable_for_source_dq_validation": True,
        "enable_for_target_dq_validation": True,
        "is_active": True,
        "enable_error_drop_alert": True,
        "error_drop_threshold": 5,  # integer % — alert if >5% dropped
        "priority": "medium",
    },
    "PROD": {
        "table_name": "{schema}.{table}",  # env-agnostic — see DEV note
        "action_if_failed": "fail",  # strictest — halt pipeline on failures
        "enable_for_source_dq_validation": True,
        "enable_for_target_dq_validation": True,
        "is_active": True,
        "enable_error_drop_alert": True,
        "error_drop_threshold": 2,  # integer % — alert if >2% dropped
        "priority": "high",
    },
}

_DEFAULT_LAYER_SCHEMAS = {
    # Authoritative runtime schemas: every Medallion layer lives under the single
    # local Unity Catalog OSS `unity` catalog (LLD §1 / ddl/migrations/*.sql).
    "bronze": "unity.bronze",
    "silver": "unity.silver",
    "gold": "unity.gold",
    "source": "synthea",
    # Stale-alias resolution: the DQS still addresses reconciliation TARGETS by
    # their documented-stale 3-part FQNs (unity.analytics.*, unity.clinical.*,
    # unity.raw.*). After `_canonicalize_table` strips the leading `unity.`, the
    # middle segment (analytics/clinical/raw) resolves here to the SAME
    # `unity.<layer>` key as the field-rule group, so recon rules MERGE into the
    # correct per-table file instead of splitting into a stale `analytics.*` file.
    "raw": "unity.bronze",
    "clinical": "unity.silver",
    "analytics": "unity.gold",
}


def load_se_config(config_path: Path | None) -> dict[str, Any]:
    """Load SE config template or return defaults.

    Returns dict with keys: product_id, dq_env, and optionally _generator.
    The _generator key contains layer_schemas for table name resolution.
    """
    if config_path and config_path.exists():
        with config_path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data
    return {
        "product_id": "patient-360",
        "dq_env": _DEFAULT_DQ_ENV,
        "_generator": {"layer_schemas": _DEFAULT_LAYER_SCHEMAS},
    }


def _resolve_table_name(
    table: str,
    template: str,
    layer_schemas: dict[str, str],
) -> str:
    """Resolve a fully-qualified table name from a template.

    Substitutes {schema} and {table} in the template string.
    The schema is looked up from layer_schemas using the table's schema prefix.
    """
    parts = table.split(".", 1)
    if len(parts) == 2:
        schema = layer_schemas.get(parts[0], parts[0])
        tbl = parts[1]
    else:
        # No schema prefix — infer from table naming convention
        tbl = parts[0]
        schema = _infer_schema_from_table(tbl, layer_schemas)
    return template.replace("{schema}", schema).replace("{table}", tbl)


def _infer_schema_from_table(
    table: str,
    layer_schemas: dict[str, str],
) -> str:
    """Infer the schema from the table name using naming conventions.

    Uses prefixes to determine the Medallion layer:
    - synthea_* -> bronze (raw)
    - clinical_*, billing_*, reference_* -> silver (clinical)
    - dim_*, fact_*, patient_* (aggregates) -> gold (analytics)
    """
    if table.startswith("synthea_"):
        return layer_schemas.get("bronze", "raw")
    elif table.startswith(("clinical_", "billing_", "reference_")):
        return layer_schemas.get("silver", "clinical")
    elif table.startswith(("dim_", "fact_", "patient_")):
        return layer_schemas.get("gold", "analytics")
    return table  # fallback: use table name as schema


# ---------------------------------------------------------------------------
# SE YAML generator
# ---------------------------------------------------------------------------


def _build_se_rule_entry(
    rule: DqsRule,
    default_threshold: int,
) -> dict[str, Any]:
    """Build a single SE rule entry dict with per-rule fields only.

    SE field semantics (from source code research):
    - enable_for_source_dq_validation: True for query_dq (reconciliation checks
      both source and target), False for row_dq/agg_dq (validate after load)
    - error_drop_threshold: Integer percentage (e.g., 5 = alert if >5% dropped)
    - enable_error_drop_alert: True for statistical/reconciliation rules (STA/REC)
    - action_if_failed: Per-rule override; dq_env provides the fallback default
    """
    is_query = rule.rule_type == "query_dq"
    prefix = rule.rule_id.split("-")[1].upper() if "-" in rule.rule_id else ""
    is_statistical = prefix in ("STA", "REC")
    is_drop = rule.is_drop_action

    # A drop rule physically filters rows BEFORE the write, so it must run as a
    # source DQ validation; it also gets a bounded drop alert so an unexpected
    # spike in dropped rows is surfaced.
    drop_threshold = 5

    # query_dq referential (REF) checks must run AFTER the row_dq drop stage,
    # i.e. at TARGET only — not SOURCE. At source the rows a `drop` rule is
    # meant to remove (e.g. null-FK records) are still present, so a
    # referential FK check with action=fail would fail on the very rows we
    # intend to drop. Reconciliation (REC) query_dq legitimately checks both
    # sides. Row-level `drop` rules filter in the row_dq stage; they do not
    # need source validation.
    is_referential = prefix == "REF"
    is_reconciliation = prefix == "REC"
    source_dq = (is_query and is_reconciliation) and not is_referential

    return {
        "rule": rule.se_rule_name,
        "rule_type": rule.rule_type,
        "column_name": rule.column,
        "expectation": rule.expression,
        "action_if_failed": rule.action_if_failed,
        "tag": rule.tag,
        "description": rule.description,
        # source validation: only for reconciliation query_dq (checks both
        # sides). Referential query_dq runs at TARGET (post-drop) so FK checks
        # validate the cleaned rows. row_dq/agg_dq validate the loaded data.
        "enable_for_source_dq_validation": source_dq,
        "enable_for_target_dq_validation": True,
        # A rule is INACTIVE inline when it cannot run in the per-row SE gate:
        #  - Reconciliation (REC): cross-system/cross-table count match whose
        #    source (e.g. raw `synthea.*`) is not a table in the pipeline Spark
        #    session — runs in the dedicated `reconciliation_<layer>` task.
        #  - SCD2 metadata-column rules: the column is manufactured by
        #    `apply_scd2` AFTER the gate, so it is absent on the pre-MERGE
        #    DataFrame (would raise UNRESOLVED_COLUMN) and is redundant.
        # All other rule types run inline.
        "is_active": not is_reconciliation and not rule.is_scd2_metadata_rule,
        # alert on drops: true for statistical/reconciliation rules and drop rules
        "enable_error_drop_alert": is_statistical or is_drop,
        # integer percentage threshold
        "error_drop_threshold": (
            drop_threshold if is_drop else int(rule.error_drop_threshold(default_threshold))
        ),
        "query_dq_delimiter": "@",
        "enable_querydq_custom_output": rule.enable_querydq_custom_output,
        "priority": rule.priority,
    }


def _canonicalize_table(table: str, layer_schemas: dict[str, str] | None = None) -> str:
    """Canonicalize table name to resolved_schema.table format.

    If the table already has a schema prefix (e.g., 'analytics.dim_patient'),
    resolve the schema through layer_schemas (bronze->raw, gold->analytics).
    If not, infer the schema from naming conventions.
    """
    schemas = layer_schemas or _DEFAULT_LAYER_SCHEMAS
    cleaned = table.strip()
    # Strip the Unity Catalog catalog segment from 3-part FQNs
    # (`unity.<schema>.<table>`) so they collapse to the SAME
    # `<schema>.<table>` grouping — and therefore the same output filename —
    # as the bare / 2-part references used elsewhere in the DQS.
    #
    # DQS v2.2 addresses reconciliation targets by their UC three-part FQN
    # (e.g. `unity.analytics.patient_summary`), while field-level rules name
    # the table bare (`patient_summary`). Without this strip the recon rule
    # forms a SEPARATE group keyed `unity.analytics.patient_summary` whose
    # basename-derived filename (`se-rules-patient-summary.yaml`) is IDENTICAL
    # to the field-rule group's file. Because `analytics.*` sorts before
    # `unity.*`, the recon-only group is written LAST and CLOBBERS the
    # field-rule file, leaving a 1-rule stub. The UC catalog is always `unity`
    # on this stack (see SKILL.md), so dropping the leading `unity.` segment is
    # safe and restores a single per-table file containing both field and
    # reconciliation rules.
    if cleaned.lower().startswith("unity.") and cleaned.count(".") >= 2:
        cleaned = cleaned.split(".", 1)[1]
    if "." in cleaned:
        parts = cleaned.split(".", 1)
        schema = parts[0]
        tbl = parts[1]
        # Resolve layer aliases (bronze->raw, silver->clinical, gold->analytics)
        resolved = schemas.get(schema, schema)
        return f"{resolved}.{tbl}"
    schema = _infer_schema_from_table(cleaned, schemas)
    return f"{schema}.{cleaned}"


def group_rules_by_table(
    rules: list[DqsRule],
    layer_schemas: dict[str, str] | None = None,
) -> dict[str, list[DqsRule]]:
    """Group rules by their target table name, canonicalized to schema.table."""
    grouped: dict[str, list[DqsRule]] = {}
    for rule in rules:
        key = _canonicalize_table(rule.table, layer_schemas)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(rule)
    return grouped


def generate_se_yaml_for_table(
    table_name: str,
    rules: list[DqsRule],
    config: dict[str, Any],
    dqs_filename: str,
) -> str:
    """Generate SE YAML content for a single table."""
    product_id = config.get("product_id", "patient-360")
    dq_env_template = config.get("dq_env", _DEFAULT_DQ_ENV)
    generator = config.get("_generator", {"layer_schemas": _DEFAULT_LAYER_SCHEMAS})
    layer_schemas = generator.get("layer_schemas", _DEFAULT_LAYER_SCHEMAS)
    prod_threshold = dq_env_template.get("PROD", {}).get("error_drop_threshold", 2)

    # Build resolved dq_env with real table names
    resolved_dq_env: dict[str, Any] = {}
    for env_name, env_config in dq_env_template.items():
        env_copy = dict(env_config)
        template = env_copy.get("table_name", "{schema}.{table}")
        env_copy["table_name"] = _resolve_table_name(table_name, template, layer_schemas)
        resolved_dq_env[env_name] = env_copy

    se_rules = [_build_se_rule_entry(r, prod_threshold) for r in rules]

    doc: dict[str, Any] = {
        "product_id": product_id,
        "dq_env": resolved_dq_env,
        "rules": se_rules,
    }

    header = (
        f"# SE Rules for {table_name}\n"
        f"# Generated from: {dqs_filename}\n"
        f"# Compatible with spark-expectations >= 2.6.0\n"
        f'# Load with: load_rules_from_yaml(this_file, spark, options={{"dq_env": "PROD"}})\n'
        f"# Product: {product_id}\n"
        f"# Rules: {len(se_rules)}\n\n"
    )

    return header + yaml.dump(
        doc,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


# ---------------------------------------------------------------------------
# SE validation (ported from spark_expectations.rules.plugins._flatten)
# ---------------------------------------------------------------------------

# Constants from SE source — keep in sync with spark-expectations >= 2.6.0
SE_VALID_RULE_TYPES = {"row_dq", "agg_dq", "query_dq"}
SE_RULES_SCHEMA_COLUMNS = [
    "product_id",
    "table_name",
    "rule_type",
    "rule",
    "column_name",
    "expectation",
    "action_if_failed",
    "tag",
    "description",
    "enable_for_source_dq_validation",
    "enable_for_target_dq_validation",
    "is_active",
    "enable_error_drop_alert",
    "error_drop_threshold",
    "query_dq_delimiter",
    "enable_querydq_custom_output",
    "priority",
]
SE_REQUIRED_RULE_FIELDS = {"rule", "expectation"}
SE_BOOLEAN_COLUMNS = {
    "enable_for_source_dq_validation",
    "enable_for_target_dq_validation",
    "is_active",
    "enable_error_drop_alert",
    "enable_querydq_custom_output",
}
SE_INT_COLUMNS = {"error_drop_threshold"}
SE_ACTION_CONSTRAINTS = {
    "row_dq": {"drop", "ignore", "fail"},
    "agg_dq": {"ignore", "fail"},
    "query_dq": {"ignore", "fail"},
}


# ---------------------------------------------------------------------------
# sqlparse-powered expectation validation
# ---------------------------------------------------------------------------

_AGGREGATE_FUNCTIONS = {"count", "sum", "avg", "min", "max", "stddev", "variance"}

# SE regex patterns for agg_dq (from spark_expectations/config/user_config.py)
_SE_AGG_STD_PATTERN = r"(\(.+?\)|\w+\(.+?\))(\s*[<>!=]+\s*.+|\s*between\s*.+)$"
_SE_AGG_RANGE_PATTERN = (
    r"(\w+\(\*\)|\w+\(\w+\)|\w+)(\s*[><]\s*\d+)"
    r"(\s+and\s+)"
    r"(\w+\(\*\)|\w+\(\w+\)|\w+)(\s*[><]\s*\d+)"
)


def _has_balanced_parens(sql: str) -> bool:
    """Check that parentheses are balanced in a SQL expression."""
    depth = 0
    for ch in sql:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


def _get_token_types(sql: str) -> set[str]:
    """Extract flattened token type names from a SQL expression."""
    parsed = sqlparse.parse(sql)
    if not parsed:
        return set()
    types: set[str] = set()
    for token in parsed[0].flatten():
        types.add(str(token.ttype))
    return types


def _contains_keyword(sql: str, keyword: str) -> bool:
    """Check if a SQL expression contains a specific keyword token."""
    parsed = sqlparse.parse(sql)
    if not parsed:
        return False
    upper_kw = keyword.upper()
    for token in parsed[0].flatten():
        if token.ttype in (stypes.Keyword, stypes.Keyword.DML, stypes.Keyword.DDL):
            if token.normalized == upper_kw:
                return True
    return False


def _validate_row_dq_expression(expectation: str) -> list[str]:
    """Validate a row_dq expectation using sqlparse.

    row_dq expectations are passed to F.expr() per row and must return boolean.
    They must NOT contain SELECT, CASE, or subqueries.
    """
    errors: list[str] = []
    upper = expectation.upper().strip()

    if not _has_balanced_parens(expectation):
        errors.append("row_dq: unbalanced parentheses in expectation")

    parsed = sqlparse.parse(expectation)
    if not parsed:
        errors.append("row_dq: could not parse expectation")
        return errors

    # Check for forbidden keywords
    for token in parsed[0].flatten():
        if token.ttype is stypes.Keyword.DML and token.normalized in (
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
        ):
            errors.append(
                f"row_dq: expectation must not contain {token.normalized} "
                f"— SE passes it to F.expr() per row. Use query_dq instead."
            )
        elif token.ttype is stypes.Keyword.DDL:
            errors.append(f"row_dq: expectation must not contain DDL ({token.normalized})")
        elif token.ttype is stypes.Keyword and token.normalized == "CASE":
            errors.append(
                "row_dq: expectation must not contain CASE WHEN "
                "— F.expr() needs a boolean. Use query_dq for CASE logic."
            )

    # Warn if no comparison operator found (should return boolean)
    has_comparison = any(
        kw in upper
        for kw in (
            "IS NOT NULL",
            "IS NULL",
            " IN ",
            " IN(",
            " NOT IN ",
            " LIKE ",
            " BETWEEN ",
            " > ",
            " < ",
            " = ",
            " >= ",
            " <= ",
            " != ",
            " <> ",
            ">",
            "<",
            "=",
        )
    )
    if not has_comparison:
        errors.append(
            "row_dq: expectation has no comparison operator "
            "— F.expr() must return boolean (e.g., col IS NOT NULL, col > 0)"
        )

    return errors


def _validate_agg_dq_expression(expectation: str) -> list[str]:
    """Validate an agg_dq expectation using sqlparse.

    agg_dq expectations are parsed by SE via regex:
      agg_func(col) operator value  (standard)
      agg_func(col) op val and agg_func(col) op val  (range)
    """
    errors: list[str] = []

    if not _has_balanced_parens(expectation):
        errors.append("agg_dq: unbalanced parentheses in expectation")

    # Check for forbidden keywords
    if _contains_keyword(expectation, "SELECT"):
        errors.append(
            "agg_dq: expectation must not contain SELECT "
            "— SE parses it via regex. Use query_dq for SQL queries."
        )

    # Check SE regex match (authoritative)
    if not re.match(_SE_AGG_STD_PATTERN, expectation, re.IGNORECASE) and not re.match(
        _SE_AGG_RANGE_PATTERN, expectation, re.IGNORECASE
    ):
        errors.append(
            "agg_dq: expectation may not match SE regex. "
            "Use format: agg_func(col) op value "
            "(e.g., count(*) > 0, sum(sales) > 10000)"
        )

    # Check for aggregate function presence
    parsed = sqlparse.parse(expectation)
    if parsed:
        has_agg = False
        for token in parsed[0].flatten():
            if token.ttype is stypes.Name and token.value.lower() in _AGGREGATE_FUNCTIONS:
                has_agg = True
                break
            # sqlparse may also classify functions differently
            if token.value.lower() in _AGGREGATE_FUNCTIONS:
                has_agg = True
                break
        if not has_agg:
            errors.append(
                "agg_dq: no aggregate function found "
                f"(expected one of: {', '.join(sorted(_AGGREGATE_FUNCTIONS))})"
            )

    return errors


def _validate_query_dq_expression(expectation: str) -> list[str]:
    """Validate a query_dq expectation using sqlparse.

    query_dq expectations are wrapped as SELECT (expectation) AS OUTPUT.
    They must return a scalar integer (non-zero = pass, zero = fail).
    They must NOT start with SELECT (SE adds it).
    """
    errors: list[str] = []
    upper = expectation.upper().strip()

    if not _has_balanced_parens(expectation):
        errors.append("query_dq: unbalanced parentheses in expectation")

    # Must not start with SELECT (SE wraps it)
    if upper.startswith("SELECT"):
        errors.append(
            "query_dq: expectation must not start with SELECT "
            "— SE wraps it as 'SELECT (exp) AS OUTPUT'. "
            "Use: CASE WHEN condition THEN 1 ELSE 0 END"
        )

    # Extract table identifiers and check they're qualified
    parsed = sqlparse.parse(expectation)
    if parsed:
        # Look for FROM keyword followed by table references
        from_found = False
        for token in parsed[0].flatten():
            if token.ttype is stypes.Keyword and token.normalized == "FROM":
                from_found = True
            elif from_found and token.ttype is stypes.Name:
                # This is a table name after FROM — check if qualified
                # But we need to handle schema.table which sqlparse
                # may split into Name.Name
                pass

        # Use regex to find table references after FROM/JOIN keywords
        # Pattern: FROM/JOIN word (no dot = unqualified)
        table_refs = re.findall(
            r"(?:FROM|JOIN)\s+(\w+)(?:\s|$|\))",
            expectation,
            re.IGNORECASE,
        )
        for tbl in table_refs:
            # Skip SQL keywords and aliases
            if tbl.upper() in (
                "SELECT",
                "WHERE",
                "ON",
                "AND",
                "OR",
                "AS",
                "CASE",
                "WHEN",
                "THEN",
                "ELSE",
                "END",
                "NULL",
                "TRUE",
                "FALSE",
                "NOT",
                "IN",
                "BETWEEN",
                "LIKE",
                "GROUP",
                "ORDER",
                "BY",
                "HAVING",
                "LIMIT",
            ):
                continue
            # Check if this looks like a bare table name (no dot)
            # Find the actual reference in context
            pattern = rf"(?:FROM|JOIN)\s+({re.escape(tbl)}(?:\.\w+)?)"
            match = re.search(pattern, expectation, re.IGNORECASE)
            if match and "." not in match.group(1):
                errors.append(
                    f"query_dq: unqualified table '{tbl}' — use schema.table (e.g., clinical.{tbl})"
                )

    return errors


def validate_se_yaml(yaml_content: str) -> list[str]:
    """Validate SE YAML against spark-expectations loading rules.

    Ports the validation logic from SE's flatten_rules_list() without
    requiring PySpark. Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]

    if not isinstance(data, dict):
        return ["Top level must be a mapping"]

    # 1. product_id required
    product_id = data.get("product_id")
    if not product_id:
        errors.append("'product_id' is required at the top level")

    # 2. dq_env validation
    dq_env = data.get("dq_env")
    if dq_env is not None:
        if not isinstance(dq_env, dict) or not dq_env:
            errors.append("'dq_env' must be a non-empty mapping")
        else:
            for env_name, env_config in dq_env.items():
                if not isinstance(env_config, dict):
                    errors.append(f"dq_env.{env_name} must be a mapping")
                    continue
                # 3. table_name required per env
                if not env_config.get("table_name"):
                    errors.append(f"dq_env.{env_name} missing 'table_name'")

    # 4. rules validation
    rules_list = data.get("rules")
    if not rules_list or not isinstance(rules_list, list):
        errors.append("'rules' must be a non-empty list")
        return errors

    for i, rule_def in enumerate(rules_list):
        rule_name = (
            rule_def.get("rule", f"<rule_{i}>") if isinstance(rule_def, dict) else f"<rule_{i}>"
        )

        if not isinstance(rule_def, dict):
            errors.append(f"Rule {rule_name}: must be a mapping")
            continue

        # 5. Required fields
        missing = SE_REQUIRED_RULE_FIELDS - set(rule_def.keys())
        if missing:
            errors.append(f"Rule {rule_name}: missing required fields {sorted(missing)}")

        # 6. rule_type validation
        rule_type = rule_def.get("rule_type", "")
        if not rule_type:
            errors.append(f"Rule {rule_name}: missing 'rule_type'")
        elif rule_type not in SE_VALID_RULE_TYPES:
            errors.append(
                f"Rule {rule_name}: invalid rule_type '{rule_type}', "
                f"must be one of {sorted(SE_VALID_RULE_TYPES)}"
            )

        # 7. Boolean type check
        for col in SE_BOOLEAN_COLUMNS:
            val = rule_def.get(col)
            if val is not None and not isinstance(val, bool):
                if isinstance(val, str) and val.lower() in ("true", "false", "1", "0", "yes", "no"):
                    continue  # SE will cast these
                errors.append(
                    f"Rule {rule_name}: '{col}' must be boolean, got {type(val).__name__}"
                )

        # 8. Integer type check
        for col in SE_INT_COLUMNS:
            val = rule_def.get(col)
            if val is not None:
                try:
                    int(val)
                except (ValueError, TypeError):
                    errors.append(f"Rule {rule_name}: '{col}' must be integer, got {val!r}")

        # 9. action_if_failed per rule_type
        action = rule_def.get("action_if_failed")
        if action and rule_type in SE_ACTION_CONSTRAINTS:
            valid_actions = SE_ACTION_CONSTRAINTS[rule_type]
            if action not in valid_actions:
                errors.append(
                    f"Rule {rule_name}: action_if_failed '{action}' invalid for "
                    f"{rule_type} (must be one of {sorted(valid_actions)})"
                )

        # 10. Warn on non-SE fields (not blocking)
        known_fields = set(SE_RULES_SCHEMA_COLUMNS) | {"product_id", "table_name"}
        unknown = set(rule_def.keys()) - known_fields
        if unknown:
            errors.append(
                f"Rule {rule_name}: unknown fields {sorted(unknown)} (SE will ignore these)"
            )

        # 11. Expectation format checks per rule_type (sqlparse-powered)
        exp = str(rule_def.get("expectation", "")).strip()
        if exp and rule_type in SE_VALID_RULE_TYPES:
            if rule_type == "row_dq":
                errors.extend(f"Rule {rule_name}: {e}" for e in _validate_row_dq_expression(exp))
            elif rule_type == "agg_dq":
                errors.extend(f"Rule {rule_name}: {e}" for e in _validate_agg_dq_expression(exp))
            elif rule_type == "query_dq":
                errors.extend(f"Rule {rule_name}: {e}" for e in _validate_query_dq_expression(exp))

    return errors


def table_name_to_filename(table_name: str) -> str:
    """Convert schema.table_name to se-rules-table-name.yaml."""
    # Strip schema prefix (e.g., analytics.dim_patient -> dim_patient)
    base = table_name.split(".")[-1]
    # Replace underscores with hyphens for file naming
    slug = base.replace("_", "-")
    return f"se-rules-{slug}.yaml"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=("Generate per-table Spark-Expectations YAML from a DQS markdown")
    )
    parser.add_argument("dqs", help="Path to the DQS markdown file")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to SE config template YAML (optional)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Output directory for generated YAML files (default: .)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print YAML to stdout without writing files",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip SE compatibility validation after generation",
    )

    args = parser.parse_args()

    dqs_path = Path(args.dqs)
    if not dqs_path.exists():
        print(f"Error: DQS file not found: {dqs_path}", file=sys.stderr)
        return 1

    config_path = Path(args.config) if args.config else None
    if config_path and not config_path.exists():
        print(
            f"Warning: SE config not found at {config_path}, using defaults",
            file=sys.stderr,
        )
        config_path = None

    output_dir = Path(args.output_dir)

    # Parse DQS
    try:
        rules = parse_dqs(dqs_path)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Error reading DQS: {exc}", file=sys.stderr)
        return 1

    if not rules:
        print(
            f"Warning: No rules found in {dqs_path}",
            file=sys.stderr,
        )
        return 1

    # Load SE config
    config = load_se_config(config_path)

    # Group by table (canonicalize using layer_schemas from config)
    generator = config.get("_generator", {"layer_schemas": _DEFAULT_LAYER_SCHEMAS})
    layer_schemas = generator.get("layer_schemas", _DEFAULT_LAYER_SCHEMAS)
    grouped = group_rules_by_table(rules, layer_schemas)

    print(f"Found {len(rules)} rules across {len(grouped)} tables.")

    # Generate YAML per table
    if not args.dry_run:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"Error creating output dir: {exc}", file=sys.stderr)
            return 3

    for table_name, table_rules in sorted(grouped.items()):
        yaml_content = generate_se_yaml_for_table(
            table_name=table_name,
            rules=table_rules,
            config=config,
            dqs_filename=dqs_path.name,
        )

        filename = table_name_to_filename(table_name)

        if args.dry_run:
            print(f"\n--- {filename} ---")
            print(yaml_content)
        else:
            out_file = output_dir / filename
            try:
                out_file.write_text(yaml_content, encoding="utf-8")
                print(f"  Written: {out_file} ({len(table_rules)} rules)")
            except OSError as exc:
                print(
                    f"Error writing {out_file}: {exc}",
                    file=sys.stderr,
                )
                return 3

            if not args.no_validate:
                validation_errors = validate_se_yaml(yaml_content)
                if validation_errors:
                    print(f"  SE validation issues for {filename}:", file=sys.stderr)
                    for err in validation_errors:
                        print(f"    - {err}", file=sys.stderr)

    print(f"\nDone. {len(grouped)} SE YAML file(s) generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
