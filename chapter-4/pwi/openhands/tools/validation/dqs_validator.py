"""DQS (Data Quality Specification) validator.

This module validates Data Quality Specifications in YAML format,
checking for correct structure, quality dimensions, and content quality.
"""

from __future__ import annotations

import re

import yaml

from .base import ArtifactValidator, ValidationIssue


class DQSValidator(ArtifactValidator):
    """Validates Data Quality Specifications (DQS).

    DQS format requirements:
    - YAML format with version as first line
    - Required quality dimensions
    - Quality gates for layer transitions
    - No code fences or markdown formatting
    """

    artifact_type = "dqs"
    format = "yaml"

    REQUIRED_DIMENSIONS = [
        "completeness",
        "accuracy",
        "consistency",
        "uniqueness",
        "validity",
        "timeliness",
    ]

    def validate_format(self, content: str) -> list[ValidationIssue]:
        """Validate DQS YAML format."""
        issues: list[ValidationIssue] = []
        content = content.strip()

        # Check for code fences
        if content.startswith("```"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="DQS is wrapped in code fences (```)",
                    suggestion="Output raw YAML without ``` markers",
                )
            )
            # Try to extract content from fences
            match = re.search(r"```(?:ya?ml)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                return issues

        # Check for markdown prose
        if content.startswith("#") and not content.startswith("# "):
            # Markdown header, not YAML comment
            first_line = content.split("\n")[0]
            if re.match(r"^#{1,6}\s+\w", first_line):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="format",
                        message="DQS is markdown prose, not YAML format",
                        suggestion="Output YAML format starting with 'version: \"1.0\"'",
                    )
                )
                return issues

        # Check first line is version
        first_line = content.split("\n")[0].strip()
        if not first_line.startswith("version:"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"First line is '{first_line[:50]}', expected 'version: \"1.0\"'",
                    suggestion="DQS must start with version declaration",
                )
            )

        # Validate YAML syntax
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"Invalid YAML syntax: {e}",
                )
            )
            return issues

        if data is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="YAML content is empty",
                )
            )
            return issues

        if not isinstance(data, dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"DQS root must be a YAML object, got {type(data).__name__}",
                )
            )
            return issues

        return issues

    def validate_content(self, content: str) -> list[ValidationIssue]:
        """Validate DQS content quality."""
        issues: list[ValidationIssue] = []

        # Clean content if needed
        content = content.strip()
        if content.startswith("```"):
            match = re.search(r"```(?:ya?ml)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            return issues  # Format issues already caught

        if not isinstance(data, dict):
            return issues

        # Check for quality_dimensions or quality_rules
        has_dimensions = "quality_dimensions" in data
        has_rules = "quality_rules" in data

        if not has_dimensions and not has_rules:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="content",
                    message="Missing 'quality_dimensions' or 'quality_rules' section",
                    suggestion="Add quality_dimensions with completeness, accuracy, etc.",
                )
            )

        # Check all dimensions present
        if has_dimensions:
            dimensions = data.get("quality_dimensions", {})
            if not isinstance(dimensions, dict):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="content",
                        message="quality_dimensions must be a YAML object",
                    )
                )
            else:
                for dim in self.REQUIRED_DIMENSIONS:
                    if dim not in dimensions:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                category="content",
                                message=f"Missing quality dimension: {dim}",
                            )
                        )
                    else:
                        # Check dimension has rules
                        dim_config = dimensions[dim]
                        if isinstance(dim_config, dict) and "rules" not in dim_config:
                            issues.append(
                                ValidationIssue(
                                    severity="warning",
                                    category="content",
                                    message=f"Quality dimension '{dim}' has no rules",
                                )
                            )

        # Check for quality gates (optional but recommended)
        has_gates = "quality_gates" in data
        if not has_gates:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="content",
                    message="No quality_gates defined",
                    suggestion="Add quality gates for bronze→silver and silver→gold transitions",
                )
            )
        else:
            gates = data.get("quality_gates", [])
            if not gates:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="content",
                        message="quality_gates section is empty",
                    )
                )

        # Check for metadata
        if "metadata" not in data:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="content",
                    message="No metadata section (name, description)",
                )
            )

        # Check for placeholder content
        content_str = str(data)
        placeholder_patterns = [
            r"\[TBD\]",
            r"\[TODO\]",
            r"\[PLACEHOLDER\]",
            r"<insert",
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, content_str, re.IGNORECASE):
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
        """Validate DQS references DMD tables."""
        issues: list[ValidationIssue] = []

        dmd_content = context.get("dmd", "")
        if not dmd_content:
            return issues

        # Extract table names from DMD
        dmd_tables: set[str] = set()
        for line in dmd_content.split("\n")[1:]:  # Skip header
            parts = line.split(",")
            if len(parts) >= 5:
                target_table = parts[4].strip().lower()
                if target_table:
                    dmd_tables.add(target_table)

        if not dmd_tables:
            return issues

        # Check if DQS rules reference those tables
        content_lower = content.lower()
        referenced_tables = {t for t in dmd_tables if t in content_lower}

        if len(referenced_tables) < len(dmd_tables) * 0.5:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="cross_reference",
                    message=f"DQS references only {len(referenced_tables)} of {len(dmd_tables)} DMD tables",
                    suggestion="Ensure DQS rules cover all target tables from DMD",
                )
            )

        return issues
