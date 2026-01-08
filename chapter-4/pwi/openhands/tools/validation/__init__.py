"""Artifact validation tools for PWI.

This module provides artifact-specific validators that can be used
by the Validator Agent to check artifact quality and format.

Usage:
    from pwi.openhands.tools.validation import validate_artifact, get_validator

    # Validate DMD content
    result = validate_artifact("dmd", dmd_content)
    print(result.to_report())

    # Validate with cross-reference context
    result = validate_artifact("dmd", dmd_content, context={"drd": drd_content})
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ArtifactValidator, ValidationIssue, ValidationResult
from .dmd_validator import DMDValidator
from .dqs_validator import DQSValidator
from .drd_validator import DRDValidator
from .pad_validator import PADValidator

if TYPE_CHECKING:
    pass

__all__ = [
    "ArtifactValidator",
    "ValidationIssue",
    "ValidationResult",
    "DMDValidator",
    "DQSValidator",
    "DRDValidator",
    "PADValidator",
    "VALIDATORS",
    "get_validator",
    "validate_artifact",
]

# Registry of validators by artifact type
VALIDATORS: dict[str, type[ArtifactValidator]] = {
    "drd": DRDValidator,
    "pad": PADValidator,
    "dmd": DMDValidator,
    "dqs": DQSValidator,
}


def get_validator(artifact_type: str) -> ArtifactValidator:
    """Get validator instance for artifact type.

    Args:
        artifact_type: Type of artifact (drd, pad, dmd, dqs).

    Returns:
        Validator instance for the artifact type.

    Raises:
        ValueError: If no validator exists for the artifact type.
    """
    validator_class = VALIDATORS.get(artifact_type.lower())
    if not validator_class:
        available = ", ".join(VALIDATORS.keys())
        raise ValueError(
            f"No validator for artifact type '{artifact_type}'. "
            f"Available: {available}"
        )
    return validator_class()


def validate_artifact(
    artifact_type: str,
    content: str,
    context: dict[str, str] | None = None,
) -> ValidationResult:
    """Validate artifact content.

    This is the main entry point for artifact validation.

    Args:
        artifact_type: Type of artifact to validate (drd, pad, dmd, dqs).
        content: Raw artifact content.
        context: Optional dictionary of other artifacts for cross-reference.

    Returns:
        ValidationResult with validation status and issues.

    Example:
        >>> result = validate_artifact("dmd", csv_content)
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(f"Error: {error.message}")
    """
    validator = get_validator(artifact_type)
    return validator.validate(content, context)
