"""DRD (Data Requirements Document) validator.

This module validates Data Requirements Documents in markdown format,
checking for required sections and content quality.
"""

from __future__ import annotations

import re

from .base import ArtifactValidator, ValidationIssue


class DRDValidator(ArtifactValidator):
    """Validates Data Requirements Documents (DRD).

    DRD format requirements:
    - Markdown format
    - Must start with # Data Requirements Document
    - Required sections for data sources, entities, business rules
    - No code fences around entire document
    """

    artifact_type = "drd"
    format = "markdown"

    REQUIRED_SECTIONS = [
        ("overview", ["overview", "executive summary", "project overview"]),
        ("data sources", ["data sources", "source systems", "sources"]),
        ("entities", ["entities", "entity definitions", "data entities", "tables"]),
        ("business rules", ["business rules", "rules", "business logic"]),
    ]

    def validate_format(self, content: str) -> list[ValidationIssue]:
        """Validate DRD markdown format."""
        issues: list[ValidationIssue] = []
        content = content.strip()

        # Check for code fences wrapping entire document
        if content.startswith("```"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="DRD is wrapped in code fences (```)",
                    suggestion="Output raw markdown without ``` markers",
                )
            )
            # Try to extract content from fences
            match = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                return issues

        # Check for proper markdown header
        first_line = content.split("\n")[0].strip()

        if not first_line.startswith("#"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message=f"DRD must start with a markdown header, got: '{first_line[:50]}'",
                    suggestion="Start with: # Data Requirements Document",
                )
            )
            return issues

        # Check header content
        header_text = first_line.lstrip("#").strip().lower()
        expected_headers = ["data requirements document", "drd"]
        if not any(h in header_text for h in expected_headers):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="format",
                    message=f"Header is '{first_line}', expected '# Data Requirements Document'",
                )
            )

        # Check for ASCII art (should use Mermaid instead)
        ascii_art_chars = ["┌", "┐", "└", "┘", "│", "─", "►", "▶", "─►"]
        for char in ascii_art_chars:
            if char in content:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="format",
                        message="Document contains ASCII art diagrams",
                        suggestion="Use Mermaid diagrams instead of ASCII art",
                    )
                )
                break

        return issues

    def validate_content(self, content: str) -> list[ValidationIssue]:
        """Validate DRD content quality."""
        issues: list[ValidationIssue] = []

        # Clean content if needed
        content = content.strip()
        if content.startswith("```"):
            match = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()

        content_lower = content.lower()

        # Check for required sections
        for section_name, variants in self.REQUIRED_SECTIONS:
            found = False
            for variant in variants:
                # Look for ## header or ### header with this text
                pattern = rf"#+\s*\d*\.?\s*{re.escape(variant)}"
                if re.search(pattern, content_lower):
                    found = True
                    break
            if not found:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="content",
                        message=f"Missing section: {section_name}",
                        suggestion=f"Add a section with heading containing: {variants[0]}",
                    )
                )

        # Check for placeholder content
        placeholder_patterns = [
            (r"\[TBD\]", "TBD"),
            (r"\[TODO\]", "TODO"),
            (r"\[PLACEHOLDER\]", "PLACEHOLDER"),
            (r"<insert.*?>", "<insert>"),
            (r"xxx+", "xxx"),
        ]
        for pattern, name in placeholder_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        category="content",
                        message=f"Content contains {len(matches)} placeholder(s) matching '{name}'",
                        suggestion="Replace placeholder text with actual values",
                    )
                )

        # Check for minimal content (not just a stub)
        line_count = len([l for l in content.split("\n") if l.strip()])
        if line_count < 20:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"Document has only {line_count} non-empty lines",
                    suggestion="DRD should comprehensively document data requirements",
                )
            )

        # Check for entity definitions (should have tables or lists)
        if "entities" in content_lower or "table" in content_lower:
            # Look for markdown tables
            table_pattern = r"\|.*\|"
            tables = re.findall(table_pattern, content)
            if len(tables) < 3:  # At minimum header, separator, one row
                issues.append(
                    ValidationIssue(
                        severity="info",
                        category="content",
                        message="Few or no markdown tables found for entity definitions",
                        suggestion="Use markdown tables to define entity attributes",
                    )
                )

        return issues
