"""DMD (Data Mapping Document) validator.

This module validates Data Mapping Documents in CSV format,
checking for correct column structure, layer values, and content quality.
"""

from __future__ import annotations

import csv
import io
import re

from .base import ArtifactValidator, ValidationIssue


class DMDValidator(ArtifactValidator):
    """Validates Data Mapping Documents (DMD).

    DMD format requirements:
    - CSV format with exactly 13 columns
    - Specific column order starting with source_system
    - Layer column as 13th column with values: bronze, silver, gold
    - No code fences or markdown formatting
    """

    artifact_type = "dmd"
    format = "csv"

    EXPECTED_COLUMNS = [
        "source_system",
        "source_table",
        "source_column",
        "source_type",
        "target_table",
        "target_column",
        "target_type",
        "transformation",
        "business_rule",
        "nullable",
        "default_value",
        "notes",
        "layer",
    ]
    VALID_LAYERS = {"bronze", "silver", "gold"}

    def validate_format(self, content: str) -> list[ValidationIssue]:
        """Validate DMD CSV format."""
        issues: list[ValidationIssue] = []
        content = content.strip()

        # Check for code fences
        if content.startswith("```"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="DMD is wrapped in code fences (```)",
                    suggestion="Output raw CSV without ``` markers",
                )
            )
            # Try to extract content from fences
            match = re.search(r"```(?:csv)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                return issues

        # Check for markdown prose
        if content.startswith("#"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="DMD is markdown prose, not CSV format",
                    suggestion="Output CSV format with header row, not markdown",
                )
            )
            return issues

        # Try to parse CSV
        try:
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
        except csv.Error as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"Invalid CSV syntax: {e}",
                )
            )
            return issues

        if not rows:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="CSV is empty",
                )
            )
            return issues

        # Check header
        header = [h.strip().lower() for h in rows[0]]
        expected_lower = [c.lower() for c in self.EXPECTED_COLUMNS]

        if len(header) != 13:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"Expected 13 columns, found {len(header)}",
                    suggestion=f"Required columns: {', '.join(self.EXPECTED_COLUMNS)}",
                )
            )

        # Check column order
        if len(header) > 0 and header[0] != "source_system":
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"First column is '{rows[0][0]}', expected 'source_system'",
                    suggestion="Columns must start with source_system, not target columns",
                )
            )

        if len(header) >= 13 and header[12] != "layer":
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"Column 13 is '{rows[0][12]}', expected 'layer'",
                    suggestion="The 13th column must be 'layer'",
                )
            )

        # Check for mismatched columns (common error: target columns first)
        if len(header) > 0 and header[0] in ("target_table", "target_column"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="Column order is wrong - target columns appear before source columns",
                    suggestion="Order must be: source_system, source_table, ... then target columns",
                )
            )

        return issues

    def validate_content(self, content: str) -> list[ValidationIssue]:
        """Validate DMD content quality."""
        issues: list[ValidationIssue] = []

        # Clean content if needed
        content = content.strip()
        if content.startswith("```"):
            match = re.search(r"```(?:csv)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

        try:
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
        except csv.Error:
            return issues  # Format issues already caught

        if len(rows) < 2:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message="DMD has no data rows (only header)",
                )
            )
            return issues

        # Validate layer values
        invalid_layers: list[tuple[int, str]] = []
        missing_layers: list[int] = []
        row_column_mismatches: list[tuple[int, int]] = []

        for i, row in enumerate(rows[1:], start=2):
            # Check column count
            if len(row) != len(rows[0]):
                row_column_mismatches.append((i, len(row)))

            if len(row) >= 13:
                layer = row[12].strip().lower()
                if not layer:
                    missing_layers.append(i)
                elif layer not in self.VALID_LAYERS:
                    invalid_layers.append((i, layer))

        # Report invalid layers (limit to first 5)
        for line_num, layer in invalid_layers[:5]:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="content",
                    message=f"Invalid layer value '{layer}' at row {line_num}",
                    suggestion="Layer must be: bronze, silver, or gold",
                    line_number=line_num,
                )
            )

        if len(invalid_layers) > 5:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="content",
                    message=f"... and {len(invalid_layers) - 5} more invalid layer values",
                )
            )

        # Report missing layers
        if missing_layers:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"{len(missing_layers)} rows have empty layer values",
                    suggestion="Every mapping row should have a layer (bronze/silver/gold)",
                )
            )

        # Report column mismatches
        if row_column_mismatches:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"{len(row_column_mismatches)} rows have incorrect column count",
                )
            )

        # Check for placeholder content
        placeholder_patterns = [
            r"\[TBD\]",
            r"\[TODO\]",
            r"\[PLACEHOLDER\]",
            r"<insert",
            r"xxx",
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="content",
                        message=f"Content contains placeholder text matching '{pattern}'",
                        suggestion="Replace placeholder text with actual values",
                    )
                )
                break

        return issues

    def validate_cross_reference(
        self, content: str, context: dict[str, str]
    ) -> list[ValidationIssue]:
        """Validate DMD against DRD entities."""
        issues: list[ValidationIssue] = []

        drd_content = context.get("drd", "")
        if not drd_content:
            return issues

        # Extract table names from DRD (simple heuristic)
        drd_tables: set[str] = set()
        for line in drd_content.split("\n"):
            # Look for table definitions like "synthea.patients" or "| patients |"
            table_matches = re.findall(r"\b(\w+\.)?(\w+)\b", line.lower())
            for _, table in table_matches:
                if table in ("patients", "encounters", "conditions", "medications", "observations"):
                    drd_tables.add(table)

        if not drd_tables:
            return issues

        # Check if DMD maps those tables
        content_clean = content.strip()
        if content_clean.startswith("```"):
            match = re.search(r"```(?:csv)?\s*\n(.*?)\n```", content_clean, re.DOTALL)
            if match:
                content_clean = match.group(1).strip()

        try:
            reader = csv.reader(io.StringIO(content_clean))
            rows = list(reader)
            if len(rows) < 2:
                return issues

            # Get source_table column index
            header = [h.strip().lower() for h in rows[0]]
            if "source_table" not in header:
                return issues

            table_idx = header.index("source_table")
            dmd_tables = {row[table_idx].strip().lower() for row in rows[1:] if len(row) > table_idx}

            # Check coverage
            missing_tables = drd_tables - dmd_tables
            if missing_tables:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="cross_reference",
                        message=f"DRD tables not mapped in DMD: {', '.join(sorted(missing_tables))}",
                        suggestion="Ensure all source tables from DRD are mapped",
                    )
                )

        except (csv.Error, ValueError):
            pass

        return issues
