"""PAD (Pipeline Architecture Document) validator.

This module validates Pipeline Architecture Documents in markdown format,
checking for required sections, Mermaid diagrams, and content quality.
"""

from __future__ import annotations

import re

from .base import ArtifactValidator, ValidationIssue


class PADValidator(ArtifactValidator):
    """Validates Pipeline Architecture Documents (PAD).

    PAD format requirements:
    - Markdown format
    - Must start with # Pipeline Architecture Document
    - Required sections for architecture, layers, components
    - Must use Mermaid diagrams (not ASCII art)
    - No code fences around entire document
    """

    artifact_type = "pad"
    format = "markdown"

    REQUIRED_SECTIONS = [
        ("architecture overview", ["architecture overview", "overview", "high-level design"]),
        ("data layers", ["data layers", "layers", "medallion", "bronze", "silver", "gold"]),
        ("pipeline components", ["pipeline components", "components", "pipeline"]),
        ("technology stack", ["technology stack", "tech stack", "technologies"]),
        ("data quality", ["data quality", "quality framework", "quality"]),
    ]

    def validate_format(self, content: str) -> list[ValidationIssue]:
        """Validate PAD markdown format."""
        issues: list[ValidationIssue] = []
        content = content.strip()

        # Check for code fences wrapping entire document
        if content.startswith("```"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="PAD is wrapped in code fences (```)",
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
                    message=f"PAD must start with a markdown header, got: '{first_line[:50]}'",
                    suggestion="Start with: # Pipeline Architecture Document",
                )
            )
            return issues

        # Check header content
        header_text = first_line.lstrip("#").strip().lower()
        expected_headers = ["pipeline architecture document", "pad", "pipeline architecture"]
        if not any(h in header_text for h in expected_headers):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="format",
                    message=f"Header is '{first_line}', expected '# Pipeline Architecture Document'",
                )
            )

        # Check for ASCII art (should use Mermaid instead)
        ascii_art_chars = ["┌", "┐", "└", "┘", "│", "─", "►", "▶", "─►", "┬", "┴", "├", "┤"]
        ascii_found = False
        for char in ascii_art_chars:
            if char in content:
                ascii_found = True
                break

        if ascii_found:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="format",
                    message="Document contains ASCII art diagrams",
                    suggestion="Use Mermaid diagrams instead of ASCII art characters",
                )
            )

        return issues

    def validate_content(self, content: str) -> list[ValidationIssue]:
        """Validate PAD content quality."""
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

        # Check for Mermaid diagrams
        mermaid_pattern = r"```mermaid"
        mermaid_count = len(re.findall(mermaid_pattern, content_lower))

        if mermaid_count == 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message="No Mermaid diagrams found",
                    suggestion="Add Mermaid diagrams for data flow and architecture visualization",
                )
            )
        elif mermaid_count < 2:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="content",
                    message=f"Only {mermaid_count} Mermaid diagram(s) found",
                    suggestion="Consider adding flowchart for data flow and ERD for data model",
                )
            )

        # Check for placeholder content
        placeholder_patterns = [
            (r"\[TBD\]", "TBD"),
            (r"\[TODO\]", "TODO"),
            (r"\[PLACEHOLDER\]", "PLACEHOLDER"),
            (r"<insert.*?>", "<insert>"),
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

        # Check for minimal content
        line_count = len([l for l in content.split("\n") if l.strip()])
        if line_count < 30:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"Document has only {line_count} non-empty lines",
                    suggestion="PAD should comprehensively document pipeline architecture",
                )
            )

        # Check for technology mentions
        tech_keywords = ["duckdb", "spark", "airflow", "python", "sql", "kafka", "aws", "gcp", "azure"]
        tech_found = sum(1 for tech in tech_keywords if tech in content_lower)
        if tech_found < 2:
            issues.append(
                ValidationIssue(
                    severity="info",
                    category="content",
                    message="Few technology-specific details found",
                    suggestion="Include specific technology choices and rationale",
                )
            )

        # Check for layer definitions (bronze, silver, gold)
        layers = ["bronze", "silver", "gold"]
        layers_found = [l for l in layers if l in content_lower]
        if len(layers_found) < 3:
            missing = set(layers) - set(layers_found)
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="content",
                    message=f"Missing data layer definitions: {', '.join(missing)}",
                    suggestion="Define all three medallion layers: bronze, silver, gold",
                )
            )

        return issues

    def validate_cross_reference(
        self, content: str, context: dict[str, str]
    ) -> list[ValidationIssue]:
        """Validate PAD addresses DRD requirements."""
        issues: list[ValidationIssue] = []

        drd_content = context.get("drd", "")
        if not drd_content:
            return issues

        # Extract key entities from DRD
        drd_lower = drd_content.lower()
        content_lower = content.lower()

        # Check if PAD mentions entities from DRD
        entity_keywords = ["patients", "encounters", "conditions", "medications", "observations"]
        drd_entities = [e for e in entity_keywords if e in drd_lower]
        pad_entities = [e for e in drd_entities if e in content_lower]

        if len(pad_entities) < len(drd_entities) * 0.5:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    category="cross_reference",
                    message=f"PAD references only {len(pad_entities)} of {len(drd_entities)} DRD entities",
                    suggestion="Ensure PAD architecture covers all entities defined in DRD",
                )
            )

        return issues
