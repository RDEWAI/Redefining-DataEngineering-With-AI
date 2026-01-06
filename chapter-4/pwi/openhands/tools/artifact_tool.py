"""Artifact generation tools for PWI OpenHands agents.

This module provides tools for generating and managing PWI artifacts:
- generate_artifact: Create a structured artifact
- save_artifact: Save artifact to file
- validate_artifact: Validate artifact format
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pwi.openhands.tools.base import create_tool, register_tool
from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.artifact")


# Artifact types and their formats
ARTIFACT_TYPES = {
    "drd": {"format": "markdown", "extension": ".md", "name": "Data Requirements Document"},
    "pad": {"format": "markdown", "extension": ".md", "name": "Pipeline Architecture Document"},
    "dmd": {"format": "csv", "extension": ".csv", "name": "Data Mapping Document"},
    "dqs": {"format": "yaml", "extension": ".yaml", "name": "Data Quality Specification"},
    "stories": {"format": "markdown", "extension": ".md", "name": "User Stories"},
    "package": {"format": "markdown", "extension": ".md", "name": "Delivery Package"},
}


# =============================================================================
# Tool Definitions
# =============================================================================

GenerateArtifactTool = create_tool(
    name="generate_artifact",
    description="Create a structured PWI artifact with proper metadata",
    parameters={
        "artifact_type": {
            "type": "string",
            "enum": list(ARTIFACT_TYPES.keys()),
            "description": "Type of artifact to generate",
        },
        "content": {
            "type": "string",
            "description": "Content of the artifact",
        },
        "metadata": {
            "type": "object",
            "description": "Additional metadata for the artifact",
        },
    },
    required=["artifact_type", "content"],
)

SaveArtifactTool = create_tool(
    name="save_artifact",
    description="Save an artifact to a file in the output directory",
    parameters={
        "artifact_type": {
            "type": "string",
            "enum": list(ARTIFACT_TYPES.keys()),
            "description": "Type of artifact",
        },
        "content": {
            "type": "string",
            "description": "Content to save",
        },
        "output_dir": {
            "type": "string",
            "description": "Output directory (default: output/)",
        },
        "session_id": {
            "type": "string",
            "description": "Session ID for organizing output",
        },
    },
    required=["artifact_type", "content"],
)

ValidateArtifactTool = create_tool(
    name="validate_artifact",
    description="Validate an artifact's format and structure",
    parameters={
        "artifact_type": {
            "type": "string",
            "enum": list(ARTIFACT_TYPES.keys()),
            "description": "Type of artifact to validate",
        },
        "content": {
            "type": "string",
            "description": "Content to validate",
        },
    },
    required=["artifact_type", "content"],
)

ListArtifactTypesTool = create_tool(
    name="list_artifact_types",
    description="List all available PWI artifact types and their formats",
    parameters={},
    required=[],
)


# =============================================================================
# Tool Executors
# =============================================================================

def execute_generate_artifact(
    artifact_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a structured artifact.

    Args:
        artifact_type: Type of artifact (drd, pad, etc.).
        content: Artifact content.
        metadata: Additional metadata.

    Returns:
        Generated artifact dictionary.
    """
    if artifact_type not in ARTIFACT_TYPES:
        return {
            "success": False,
            "error": f"Unknown artifact type: {artifact_type}",
            "valid_types": list(ARTIFACT_TYPES.keys()),
        }

    type_info = ARTIFACT_TYPES[artifact_type]

    artifact = {
        "success": True,
        "artifact": {
            "type": artifact_type,
            "name": type_info["name"],
            "format": type_info["format"],
            "extension": type_info["extension"],
            "content": content,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                **(metadata or {}),
            },
        },
    }

    logger.info(f"Generated {artifact_type} artifact")
    return artifact


def execute_save_artifact(
    artifact_type: str,
    content: str,
    output_dir: str = "output",
    session_id: str | None = None,
) -> dict[str, Any]:
    """Save an artifact to a file.

    Args:
        artifact_type: Type of artifact.
        content: Content to save.
        output_dir: Output directory.
        session_id: Session ID for organizing.

    Returns:
        Save result dictionary.
    """
    if artifact_type not in ARTIFACT_TYPES:
        return {
            "success": False,
            "error": f"Unknown artifact type: {artifact_type}",
        }

    type_info = ARTIFACT_TYPES[artifact_type]

    # Build output path
    base_dir = Path(output_dir)
    if session_id:
        base_dir = base_dir / session_id

    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{artifact_type}{type_info['extension']}"
    file_path = base_dir / filename

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved artifact to {file_path}")

        return {
            "success": True,
            "file_path": str(file_path),
            "artifact_type": artifact_type,
            "size_bytes": len(content.encode("utf-8")),
        }

    except Exception as e:
        logger.error(f"Failed to save artifact: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def execute_validate_artifact(
    artifact_type: str,
    content: str,
) -> dict[str, Any]:
    """Validate an artifact's format.

    Args:
        artifact_type: Type of artifact.
        content: Content to validate.

    Returns:
        Validation result dictionary.
    """
    if artifact_type not in ARTIFACT_TYPES:
        return {
            "success": False,
            "valid": False,
            "error": f"Unknown artifact type: {artifact_type}",
        }

    type_info = ARTIFACT_TYPES[artifact_type]
    issues: list[str] = []

    # Validate based on format
    if type_info["format"] == "markdown":
        issues.extend(_validate_markdown(content, artifact_type))
    elif type_info["format"] == "csv":
        issues.extend(_validate_csv(content))
    elif type_info["format"] == "yaml":
        issues.extend(_validate_yaml(content))

    return {
        "success": True,
        "valid": len(issues) == 0,
        "artifact_type": artifact_type,
        "format": type_info["format"],
        "issues": issues,
        "issue_count": len(issues),
    }


def _validate_markdown(content: str, artifact_type: str) -> list[str]:
    """Validate markdown content."""
    issues = []

    # Check for expected headers based on artifact type
    expected_headers = {
        "drd": "# Data Requirements Document",
        "pad": "# Pipeline Architecture Document",
        "stories": "# User Stories",
        "package": "# Data Engineering Delivery Package",
    }

    if artifact_type in expected_headers:
        if expected_headers[artifact_type] not in content:
            issues.append(f"Missing expected header: {expected_headers[artifact_type]}")

    # Check for code fence wrapping (should not be wrapped)
    if content.strip().startswith("```markdown"):
        issues.append("Content should not be wrapped in ```markdown code fences")

    # Check for ASCII art (should use Mermaid)
    ascii_chars = ["┌", "─", "┐", "│", "└", "┘", "►", "▶"]
    for char in ascii_chars:
        if char in content:
            issues.append(f"ASCII art character found: '{char}' - use Mermaid diagrams instead")
            break

    return issues


def _validate_csv(content: str) -> list[str]:
    """Validate CSV content."""
    import csv
    import io

    issues = []

    try:
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        if not rows:
            issues.append("CSV is empty")
        elif len(rows) == 1:
            issues.append("CSV has only header row, no data")

        # Check for consistent column count
        if rows:
            expected_cols = len(rows[0])
            for i, row in enumerate(rows[1:], 2):
                if len(row) != expected_cols:
                    issues.append(f"Row {i} has {len(row)} columns, expected {expected_cols}")
                    break

    except csv.Error as e:
        issues.append(f"Invalid CSV format: {e}")

    return issues


def _validate_yaml(content: str) -> list[str]:
    """Validate YAML content."""
    import yaml

    issues = []

    try:
        data = yaml.safe_load(content)
        if data is None:
            issues.append("YAML is empty or invalid")
    except yaml.YAMLError as e:
        issues.append(f"Invalid YAML format: {e}")

    return issues


def execute_list_artifact_types() -> dict[str, Any]:
    """List all artifact types.

    Returns:
        Dictionary of artifact types and their info.
    """
    return {
        "success": True,
        "artifact_types": ARTIFACT_TYPES,
        "count": len(ARTIFACT_TYPES),
    }


# =============================================================================
# Register Tools
# =============================================================================

def register_artifact_tools() -> None:
    """Register all artifact tools with the global registry."""
    register_tool(GenerateArtifactTool, execute_generate_artifact)
    register_tool(SaveArtifactTool, execute_save_artifact)
    register_tool(ValidateArtifactTool, execute_validate_artifact)
    register_tool(ListArtifactTypesTool, execute_list_artifact_types)
    logger.info("Artifact tools registered")


# Auto-register on import
register_artifact_tools()
