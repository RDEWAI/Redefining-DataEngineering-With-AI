"""Base classes for artifact validation tools.

This module provides the foundation for artifact-specific validators,
enabling modular validation with consistent result formats.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ValidationIssue:
    """A single validation issue.

    Attributes:
        severity: Issue severity level (error, warning, info).
        category: Category of issue (format, content, cross_reference).
        message: Human-readable description of the issue.
        suggestion: Optional suggestion for how to fix the issue.
        line_number: Optional line number where issue was found.
    """

    severity: Literal["error", "warning", "info"]
    category: Literal["format", "content", "cross_reference"]
    message: str
    suggestion: str | None = None
    line_number: int | None = None

    def __str__(self) -> str:
        """Return formatted string representation."""
        loc = f" (line {self.line_number})" if self.line_number else ""
        sug = f" - {self.suggestion}" if self.suggestion else ""
        return f"[{self.severity.upper()}] {self.message}{loc}{sug}"


@dataclass
class ValidationResult:
    """Complete validation result for an artifact.

    Attributes:
        artifact_type: Type of artifact validated (drd, pad, etc.).
        is_valid: True if no errors found (warnings allowed).
        errors: List of error-level issues.
        warnings: List of warning-level issues.
        info: List of info-level messages.
        coverage: Optional coverage metrics for cross-reference validation.
    """

    artifact_type: str
    is_valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)
    coverage: dict[str, float] | None = None

    @property
    def error_count(self) -> int:
        """Return count of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Return count of warnings."""
        return len(self.warnings)

    @property
    def all_issues(self) -> list[ValidationIssue]:
        """Return all issues sorted by severity."""
        return self.errors + self.warnings + self.info

    def to_report(self) -> str:
        """Generate a human-readable validation report."""
        status = "PASS" if self.is_valid else "FAIL"
        lines = [
            f"Validation Result: {status}",
            f"Artifact Type: {self.artifact_type.upper()}",
            f"Errors: {self.error_count}, Warnings: {self.warning_count}",
            "",
        ]

        if self.errors:
            lines.append("ERRORS:")
            for issue in self.errors:
                lines.append(f"  - {issue.message}")
                if issue.suggestion:
                    lines.append(f"    Fix: {issue.suggestion}")
            lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            for issue in self.warnings:
                lines.append(f"  - {issue.message}")
            lines.append("")

        if self.coverage:
            lines.append("COVERAGE:")
            for key, value in self.coverage.items():
                lines.append(f"  - {key}: {value:.1%}")

        return "\n".join(lines)


class ArtifactValidator(ABC):
    """Base class for artifact validators.

    Subclasses must implement:
    - artifact_type: str class attribute
    - format: str class attribute
    - validate_format(): Check artifact format
    - validate_content(): Check artifact content quality

    Optionally override:
    - validate_cross_reference(): Check references to other artifacts
    """

    artifact_type: str
    format: str

    @abstractmethod
    def validate_format(self, content: str) -> list[ValidationIssue]:
        """Validate artifact format.

        Args:
            content: Raw artifact content.

        Returns:
            List of format-related validation issues.
        """
        pass

    @abstractmethod
    def validate_content(self, content: str) -> list[ValidationIssue]:
        """Validate artifact content quality.

        Args:
            content: Raw artifact content.

        Returns:
            List of content-related validation issues.
        """
        pass

    def validate_cross_reference(
        self, content: str, context: dict[str, str]
    ) -> list[ValidationIssue]:
        """Validate cross-references with other artifacts.

        Args:
            content: Raw artifact content.
            context: Dictionary of other artifacts {type: content}.

        Returns:
            List of cross-reference validation issues.
        """
        return []

    def validate(
        self, content: str, context: dict[str, str] | None = None
    ) -> ValidationResult:
        """Run all validations on the artifact.

        Args:
            content: Raw artifact content.
            context: Optional dictionary of other artifacts for cross-reference.

        Returns:
            Complete validation result.
        """
        issues: list[ValidationIssue] = []

        # Run format validation first
        format_issues = self.validate_format(content)
        issues.extend(format_issues)

        # Only run content validation if format is acceptable
        format_errors = [i for i in format_issues if i.severity == "error"]
        if not format_errors:
            content_issues = self.validate_content(content)
            issues.extend(content_issues)

            # Run cross-reference validation if context provided
            if context:
                xref_issues = self.validate_cross_reference(content, context)
                issues.extend(xref_issues)

        # Categorize issues by severity
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        info = [i for i in issues if i.severity == "info"]

        return ValidationResult(
            artifact_type=self.artifact_type,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info,
        )
